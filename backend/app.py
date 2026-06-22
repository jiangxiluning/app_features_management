from flask import Flask, jsonify, request, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, decode_token
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import shutil
import time
import threading
import schedule
import yaml
import hashlib
import sqlite3
import json
import queue
from flask import request, send_from_directory
from werkzeug.utils import secure_filename
from sqlalchemy import event
from sqlalchemy.engine import Engine

from consistency import (
    admin_required,
    apply_content_to_feature,
    auth_required,
    bump_revision,
    check_maintenance,
    check_revision_conflict,
    dump_audit_content,
    feature_snapshot,
    feature_to_dict,
    get_auth_context,
    get_pending_audit,
    merge_draft_into_dict,
    parse_audit_content,
    resolve_feature_view,
    emit_data_change,
)

# 密码哈希函数（与前端兼容）
def hash_password(password):
    # 尝试使用与前端相同的哈希方法
    # 前端使用的是 Web Crypto API 的 SHA-256 实现
    # 后端使用 Python 的 hashlib.sha256 实现
    # 两者应该是兼容的
    hashed = hashlib.sha256(password.encode()).hexdigest()
    print(f"哈希密码: {password} -> {hashed}")
    return hashed

# 验证密码（与前端兼容）
def verify_password(plain_password, hashed_password):
    # 尝试使用与前端相同的哈希方法
    # 前端使用的是 Web Crypto API 的 SHA-256 实现
    # 后端使用 Python 的 hashlib.sha256 实现
    # 两者应该是兼容的
    return hash_password(plain_password) == hashed_password

# 版本比较函数
def compare_versions(version1, version2):
    """比较两个版本号，返回-1（version1 < version2）, 0（相等）, 1（version1 > version2）"""
    v1_parts = list(map(int, version1.split('.')))
    v2_parts = list(map(int, version2.split('.')))
    
    # 补全版本号位数
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))
    
    for i in range(max_len):
        if v1_parts[i] < v2_parts[i]:
            return -1
        elif v1_parts[i] > v2_parts[i]:
            return 1
    return 0

# 读取配置文件
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            # 验证并设置默认值
            if 'backup' in config:
                # 验证 interval (0=1h, 1=1d, 2=1w, 3=1m)
                interval_map = {
                    0: '1 hour',
                    1: '1 day',
                    2: '1 week',
                    3: '1 month'
                }
                if 'interval' in config['backup']:
                    interval = config['backup']['interval']
                    if interval in interval_map:
                        config['backup']['interval'] = interval_map[interval]
                    else:
                        # 无效值，使用默认值 1 (1 day)
                        config['backup']['interval'] = interval_map[1]
                else:
                    # 未设置，使用默认值 1 (1 day)
                    config['backup']['interval'] = interval_map[1]
                # 设置默认值
                if 'enabled' not in config['backup']:
                    config['backup']['enabled'] = True
                if 'keep_latest' not in config['backup']:
                    config['backup']['keep_latest'] = 10
                if 'path' not in config['backup']:
                    config['backup']['path'] = './backups'
            return config
    return {}

# 加载配置
config = load_config()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey1234567890abcdefghijklmnopqrstuvwxyz'
app.config['JWT_SECRET_KEY'] = 'supersecretkey1234567890abcdefghijklmnopqrstuvwxyz'
app.config['JWT_ERROR_MESSAGE_KEY'] = 'message'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)
import os
# 使用绝对路径来指定数据库文件的位置（测试时可通过环境变量指向独立库）
_test_db_uri = os.environ.get('PLAN_TEST_DATABASE_URI')
if _test_db_uri:
    app.config['SQLALCHEMY_DATABASE_URI'] = _test_db_uri
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
        os.path.dirname(__file__), 'instance', 'app_knowledge.db'
    )
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 服务器配置
SERVER_HOST = config.get('server', {}).get('host', '0.0.0.0')
SERVER_PORT = config.get('server', {}).get('port', 5001)

# 备份配置
BACKUP_PATH = config.get('backup', {}).get('path', './backups')
BACKUP_INTERVAL = config.get('backup', {}).get('interval', '1 day')
BACKUP_KEEP_LATEST = config.get('backup', {}).get('keep_latest', 10)
BACKUP_ENABLED = config.get('backup', {}).get('enabled', True)

db = SQLAlchemy(app)
jwt = JWTManager(app)
CORS(app)

# 维护模式（restore/import 期间阻断写入）
maintenance_mode = False


@event.listens_for(Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA busy_timeout=5000')
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


@app.before_request
def before_request_maintenance():
    blocked = check_maintenance(maintenance_mode)
    if blocked:
        return blocked

# 数据库模型
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, developer


class UserApp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    app_id = db.Column(db.Integer, db.ForeignKey('feature.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('user_apps', lazy=True))
    app = db.relationship('Feature', backref=db.backref('user_apps', lazy=True))


class Feature(db.Model):
    __tablename__ = 'feature'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    use_cases = db.Column(db.Text, nullable=True)
    videos = db.Column(db.Text, nullable=True)  # 视频URL列表，用逗号分隔
    version_range = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('feature.id'), nullable=True)
    parent = db.relationship('Feature', remote_side=[id], backref=db.backref('children', lazy=True))
    node_type = db.Column(db.String(20), nullable=False, default='function')  # app, category, function
    status = db.Column(db.String(20), nullable=False, default='approved')  # pending, approved, rejected
    is_guide_supported = db.Column(db.Boolean, nullable=False, default=False)
    devices = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.String(50), nullable=True)
    updated_by = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    revision = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=True)


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    device_model = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    release_name = db.Column(db.String(100), nullable=True)
    release_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feature_id = db.Column(db.Integer, db.ForeignKey('feature.id'), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # create, update, delete
    status = db.Column(db.String(20), nullable=False)  # pending, approved, rejected
    created_by = db.Column(db.String(50), nullable=False)
    approved_by = db.Column(db.String(50), nullable=True)
    before_content = db.Column(db.Text, nullable=True)  # 修改前内容
    after_content = db.Column(db.Text, nullable=True)  # 修改后内容
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)


class AppVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey('feature.id'), nullable=False)
    version = db.Column(db.String(50), nullable=False)
    changelog = db.Column(db.Text, nullable=True)  # Markdown格式的更新日志
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    app = db.relationship('Feature', backref=db.backref('versions', lazy=True))


class SchemaVersion(db.Model):
    __tablename__ = 'schema_version'
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class LLMConfig(db.Model):
    __tablename__ = 'llm_config'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default='default')
    base_url = db.Column(db.Text, nullable=False)
    api_key = db.Column(db.Text, nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    enable_search = db.Column(db.Boolean, nullable=False, default=False)
    system_prompt = db.Column(db.Text, nullable=True)
    user_prompt = db.Column(db.Text, nullable=True)
    http_proxy = db.Column(db.Text, nullable=True)
    https_proxy = db.Column(db.Text, nullable=True)
    no_proxy = db.Column(db.Boolean, nullable=False, default=False)  # 新增：不使用代理
    same_proxy = db.Column(db.Boolean, nullable=False, default=False)  # 新增：HTTP和HTTPS代理一致
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'base_url': self.base_url,
            'api_key': self.api_key,
            'model_name': self.model_name,
            'enable_search': self.enable_search,
            'system_prompt': self.system_prompt,
            'user_prompt': self.user_prompt,
            'http_proxy': self.http_proxy,
            'https_proxy': self.https_proxy,
            'no_proxy': self.no_proxy,
            'same_proxy': self.same_proxy,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }




# 确保instance目录存在
import os
instance_dir = os.path.join(os.path.dirname(__file__), 'instance')
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)
    print(f"Created instance directory: {instance_dir}")

# 创建数据库
with app.app_context():
    db.create_all()
    
    # 尝试添加新字段（兼容性处理）
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'feature' in inspector.get_table_names():
            feature_cols = [c['name'] for c in inspector.get_columns('feature')]
            if 'revision' not in feature_cols:
                with db.engine.connect() as conn:
                    conn.execute(db.text(
                        'ALTER TABLE feature ADD COLUMN revision INTEGER NOT NULL DEFAULT 1'
                    ))
                    conn.commit()
            if 'updated_at' not in feature_cols:
                with db.engine.connect() as conn:
                    conn.execute(db.text(
                        'ALTER TABLE feature ADD COLUMN updated_at DATETIME'
                    ))
                    conn.execute(db.text(
                        'UPDATE feature SET updated_at = created_at WHERE updated_at IS NULL'
                    ))
                    conn.commit()
        columns = []
        if 'llm_config' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('llm_config')]
        
        if 'no_proxy' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE llm_config ADD COLUMN no_proxy BOOLEAN DEFAULT 0'))
                conn.commit()
                print('Added no_proxy column')
        
        if 'same_proxy' not in columns:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE llm_config ADD COLUMN same_proxy BOOLEAN DEFAULT 0'))
                conn.commit()
                print('Added same_proxy column')
    except Exception as e:
        print(f'Database schema update: {e}')
    
    # 创建默认管理员用户（集成测试使用独立库时由测试脚本自行 seed）
    if not _test_db_uri and not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=hash_password('admin'), role='admin')
        db.session.add(admin)
        db.session.commit()
    # 创建默认schema版本
    if not SchemaVersion.query.first():
        schema_version = SchemaVersion(version='1.0.1')
        db.session.add(schema_version)
        db.session.commit()
    # 创建默认LLM配置（只有在表存在的情况下）
    try:
        if not LLMConfig.query.first():
            default_llm_config = LLMConfig(
                name='default',
                base_url='https://api.openai.com/v1',
                api_key='',
                model_name='gpt-3.5-turbo',
                enable_search=False,
                system_prompt='你是一个专业的功能描述优化助手，帮助用户完善功能描述内容。',
                user_prompt='请优化以下功能描述，使其更加清晰、专业、完整：\n应用名称：{{app_name}}\n应用描述：{{app_description}}\n功能名称：{{feature_name}}\n功能描述：{{feature_description}}',
                no_proxy=False,
                same_proxy=False
            )
            db.session.add(default_llm_config)
            db.session.commit()
            print('Created default LLM config')
        else:
            # 确保现有配置有新字段
            config = LLMConfig.query.first()
            if not hasattr(config, 'no_proxy'):
                # 尝试直接更新数据库（使用原始 SQL）
                try:
                    with db.engine.connect() as conn:
                        conn.execute(db.text('UPDATE llm_config SET no_proxy = 0 WHERE no_proxy IS NULL'))
                        conn.execute(db.text('UPDATE llm_config SET same_proxy = 0 WHERE same_proxy IS NULL'))
                        conn.commit()
                except:
                    pass
    except Exception as e:
        # 如果表不存在，忽略错误
        print(f'Could not create default LLM config: {e}')



# 导入 get_jwt
from flask_jwt_extended import get_jwt

# 获取当前用户信息
def get_current_user():
    # 从 JWT claims 中获取用户信息
    try:
        claims = get_jwt()
        if 'role' in claims and 'user_id' in claims:
            identity = get_jwt_identity()
            return {
                'username': identity,
                'role': claims['role'],
                'user_id': claims['user_id']
            }
    except:
        pass
    
    # 兼容旧格式
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity
    return identity

# API路由
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    print(f"收到登录请求: {data}")
    
    # 尝试查询用户
    try:
        user = User.query.filter_by(username=data['username']).first()
        print(f"查询用户结果: {user}")
        
        # 检查用户是否存在
        if not user:
            print(f"用户不存在: {data['username']}")
            return jsonify(message='用户名或密码错误'), 401
        
        print(f"用户存在: {user.username}, 数据库密码: {user.password}, 前端密码: {data['password']}")
        
        # 计算默认密码的哈希值，用于调试
        default_admin_hash = hash_password('admin')
        print(f"admin 的哈希值: {default_admin_hash}")
        
        # 检查密码是否匹配
        # 前端已经对密码进行了哈希处理，直接比较哈希值
        if user.password == data['password']:
            print("密码匹配: 前端发送的是哈希值")
            # 使用 identity=用户名（字符串），并使用 additional_claims 传递额外信息
            access_token = create_access_token(
                identity=user.username,
                additional_claims={'role': user.role, 'user_id': user.id}
            )
            return jsonify(access_token=access_token, role=user.role, username=user.username, user_id=user.id)
        
        # 尝试使用前端的哈希方法验证密码
        # 前端使用的是 Web Crypto API 的 SHA-256 实现
        # 后端使用 Python 的 hashlib.sha256 实现
        # 两者应该是兼容的
        # 这里尝试将前端发送的密码视为明文，重新哈希后比较
        hashed_password = hash_password(data['password'])
        print(f"尝试将前端密码视为明文，哈希后: {hashed_password}")
        if hashed_password == user.password:
            print("密码匹配: 前端发送的是明文")
            access_token = create_access_token(
                identity=user.username,
                additional_claims={'role': user.role, 'user_id': user.id}
            )
            return jsonify(access_token=access_token, role=user.role, username=user.username, user_id=user.id)
        
        # 密码不匹配，返回错误
        print("密码不匹配")
        return jsonify(message='用户名或密码错误'), 401
    except Exception as e:
        print(f"登录过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(message='登录失败，请稍后重试'), 500


@app.route('/api/events')
def data_events_stream():
    """SSE 数据变更推送（EventSource 通过 query token 鉴权）。"""
    from sse_hub import subscribe, unsubscribe, format_sse

    token = request.args.get('token')
    if not token:
        return jsonify(message='未授权访问'), 401
    try:
        decode_token(token)
    except Exception:
        return jsonify(message='无效或已过期的令牌'), 401

    @stream_with_context
    def generate():
        q = subscribe()
        try:
            yield format_sse('connected', {'type': 'connected'})
            while True:
                try:
                    event = q.get(timeout=25)
                    yield format_sse('data_change', event)
                except queue.Empty:
                    yield ': keepalive\n\n'
        except GeneratorExit:
            pass
        finally:
            unsubscribe(q)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@app.route('/api/auth/register', methods=['POST'])
@admin_required
def register():
    data = request.get_json()
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify(message='用户名已存在'), 400
    
    # 管理员创建用户
    # 前端已经对密码进行了哈希处理，直接使用哈希值
    password = data['password']
    user = User(username=data['username'], password=password, role=data.get('role', 'developer'))
    db.session.add(user)
    db.session.commit()
    return jsonify(message='用户添加成功')


@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    users = User.query.all()
    return jsonify([{'id': user.id, 'username': user.username, 'role': user.role} for user in users])


@app.route('/api/users/<int:id>', methods=['PUT'])
@admin_required
def update_user(id):
    user = User.query.get(id)
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json()
    if 'password' in data:
        # 前端已经对密码进行了哈希处理，直接使用哈希值
        user.password = data['password']
    if 'role' in data:
        user.role = data['role']
    db.session.commit()
    return jsonify(message='用户信息更新成功')


@app.route('/api/users/<int:id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    user = User.query.get(id)
    if not user:
        return jsonify(message='用户不存在'), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify(message='用户删除成功')


@app.route('/api/auth/change-password', methods=['POST'])
@auth_required
def change_password():
    data = request.get_json()
    ctx = get_auth_context()
    user = User.query.filter_by(username=ctx['username']).first()
    
    # 检查用户是否存在
    if not user:
        return jsonify(message='用户名或旧密码错误'), 401
    
    # 检查旧密码是否匹配
    # 前端已经对密码进行了哈希处理，直接比较哈希值
    if user.password == data['old_password']:
        # 前端已经对新密码进行了哈希处理，直接使用哈希值
        user.password = data['new_password']
        db.session.commit()
        return jsonify(message='密码修改成功')
    
    # 尝试使用前端的哈希方法验证密码
    # 前端使用的是 Web Crypto API 的 SHA-256 实现
    # 后端使用 Python 的 hashlib.sha256 实现
    # 两者应该是兼容的
    # 这里尝试将前端发送的密码视为明文，重新哈希后比较
    if hash_password(data['old_password']) == user.password:
        # 尝试将新密码视为明文，重新哈希后存储
        user.password = hash_password(data['new_password'])
        db.session.commit()
        return jsonify(message='密码修改成功')
    
    return jsonify(message='用户名或旧密码错误'), 401


@app.route('/api/user-apps', methods=['GET'])
@admin_required
def get_user_apps():
    user_apps = UserApp.query.all()
    return jsonify([{'id': ua.id, 'user_id': ua.user_id, 'app_id': ua.app_id} for ua in user_apps])


@app.route('/api/user-apps/<int:user_id>', methods=['GET'])
@auth_required
def get_user_apps_by_user(user_id):
    ctx = get_auth_context()
    if ctx['role'] != 'admin' and ctx['user_id'] != user_id:
        return jsonify(message='没有权限访问'), 403
    user = User.query.get(user_id)
    if user.role == 'admin':
        # 管理员拥有所有应用的权限
        apps = Feature.query.filter_by(node_type='app').all()
        return jsonify([{'id': i, 'app_id': app.id} for i, app in enumerate(apps, 1)])
    else:
        # 开发者只能访问分配的应用
        user_apps = UserApp.query.filter_by(user_id=user_id).all()
        return jsonify([{'id': ua.id, 'app_id': ua.app_id} for ua in user_apps])


@app.route('/api/user-apps', methods=['POST'])
@admin_required
def add_user_app():
    data = request.get_json()
    user_id = data['user_id']
    app_id = data['app_id']
    # 检查是否已存在
    if UserApp.query.filter_by(user_id=user_id, app_id=app_id).first():
        return jsonify(message='已存在该分配关系'), 400
    user_app = UserApp(user_id=user_id, app_id=app_id)
    db.session.add(user_app)
    db.session.commit()
    return jsonify(message='应用分配成功')


@app.route('/api/user-apps/<int:id>', methods=['DELETE'])
@admin_required
def delete_user_app(id):
    user_app = UserApp.query.get(id)
    if not user_app:
        return jsonify(message='分配关系不存在'), 404
    db.session.delete(user_app)
    db.session.commit()
    return jsonify(message='应用分配删除成功')


@app.route('/api/audit-logs', methods=['GET'])
@auth_required
def get_audit_logs():
    feature_id = request.args.get('feature_id', type=int)
    created_by = request.args.get('created_by')
    date = request.args.get('date')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = AuditLog.query
    
    if feature_id:
        query = query.filter_by(feature_id=feature_id)
    
    if created_by:
        # 如果指定了创建者，则返回该用户的所有审核记录（包括已通过和已驳回的）
        query = query.filter_by(created_by=created_by)
    # 移除默认只返回待审核记录的限制，允许获取所有状态的记录
    
    if date:
        # 过滤指定日期的记录
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d')
            # 过滤当天的记录
            query = query.filter(
                db.func.date(AuditLog.created_at) == target_date.date()
            )
        except ValueError:
            # 日期格式错误，忽略过滤
            pass
    elif start_date and end_date:
        # 过滤日期范围的记录
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            # 过滤日期范围内的记录
            query = query.filter(
                db.func.date(AuditLog.created_at) >= start.date(),
                db.func.date(AuditLog.created_at) <= end.date()
            )
        except ValueError:
            # 日期格式错误，忽略过滤
            pass
    
    logs = query.all()
    result = []
    for log in logs:
        try:
            # 尝试获取功能名称
            feature = Feature.query.get(log.feature_id)
            feature_name = feature.name if feature else '未知功能'
            # 尝试获取应用名称
            app_name = get_app_root_name(log.feature_id)
            
            result.append({
                'id': log.id,
                'feature_id': log.feature_id,
                'feature_name': feature_name,
                'app_name': app_name,
                'action': log.action,
                'status': log.status,
                'created_by': log.created_by,
                'approved_by': log.approved_by,
                'before_content': log.before_content,
                'after_content': log.after_content,
                'created_at': log.created_at.isoformat(),
                'approved_at': log.approved_at.isoformat() if log.approved_at else None
            })
        except Exception as e:
            # 如果出现错误，仍然添加记录，但使用默认值
            result.append({
                'id': log.id,
                'feature_id': log.feature_id,
                'feature_name': '未知功能',
                'app_name': '未知应用',
                'action': log.action,
                'status': log.status,
                'created_by': log.created_by,
                'approved_by': log.approved_by,
                'before_content': log.before_content,
                'after_content': log.after_content,
                'created_at': log.created_at.isoformat(),
                'approved_at': log.approved_at.isoformat() if log.approved_at else None
            })
    return jsonify(result)


def _find_pending_audit_log(id):
    log = AuditLog.query.filter_by(feature_id=id, status='pending').first()
    if not log:
        log = AuditLog.query.get(id)
    return log


def _reject_or_withdraw_feature(log, feature, final_status):
    if not feature:
        return
    if log.action == 'create':
        delete_feature_recursive(feature)
    elif log.action in ('update', 'move') and log.before_content:
        before_content = parse_audit_content(log.before_content)
        if before_content:
            apply_content_to_feature(feature, before_content)
        feature.status = 'approved'
    elif log.action == 'delete':
        feature.status = 'approved'
    else:
        feature.status = final_status if final_status != 'approved' else 'approved'


@app.route('/api/audit-logs/<int:id>/approve', methods=['POST'])
@admin_required
def approve_audit(id):
    log = _find_pending_audit_log(id)
    if not log:
        return jsonify(message='审核记录不存在'), 404

    data = request.get_json() or {}
    ctx = get_auth_context()
    approved_by = data.get('approved_by') or ctx.get('username')

    updated = AuditLog.query.filter_by(id=log.id, status='pending').update({
        'status': 'approved',
        'approved_by': approved_by,
        'approved_at': datetime.utcnow(),
    })
    if not updated:
        return jsonify(message='该审核已失效'), 409

    db.session.expire(log)
    log = AuditLog.query.get(log.id)
    feature = Feature.query.get(log.feature_id)

    if feature:
        if log.action == 'delete':
            delete_feature_recursive(feature)
        else:
            after_content = parse_audit_content(log.after_content)
            if after_content and log.action in ('update', 'move'):
                apply_content_to_feature(feature, after_content)
            feature.status = 'approved'
            bump_revision(feature)

            def approve_ancestors(node):
                if node.parent_id:
                    parent = Feature.query.get(node.parent_id)
                    if parent and parent.status == 'pending':
                        parent.status = 'approved'
                        parent_logs = AuditLog.query.filter_by(
                            feature_id=parent.id, status='pending'
                        ).all()
                        for parent_log in parent_logs:
                            AuditLog.query.filter_by(
                                id=parent_log.id, status='pending'
                            ).update({
                                'status': 'approved',
                                'approved_by': approved_by,
                                'approved_at': datetime.utcnow(),
                            })
                        approve_ancestors(parent)

            approve_ancestors(feature)

    db.session.commit()
    emit_data_change('audit_approved', actor=approved_by, scope='audit', resource_id=log.feature_id)
    emit_data_change('features_changed', actor=approved_by, scope='features', resource_id=log.feature_id)
    return jsonify(message='审核通过')


@app.route('/api/audit-logs/<int:id>/reject', methods=['POST'])
@admin_required
def reject_audit(id):
    log = _find_pending_audit_log(id)
    if not log:
        return jsonify(message='审核记录不存在'), 404

    if log.status != 'pending':
        return jsonify(message='该审核已失效'), 400

    data = request.get_json() or {}
    ctx = get_auth_context()
    log.status = 'rejected'
    log.approved_by = data.get('approved_by') or ctx.get('username')
    log.approved_at = datetime.utcnow()

    feature = Feature.query.get(log.feature_id)
    _reject_or_withdraw_feature(log, feature, 'rejected')

    db.session.commit()
    emit_data_change('audit_rejected', actor=log.approved_by, scope='audit', resource_id=log.feature_id)
    emit_data_change('features_changed', actor=log.approved_by, scope='features', resource_id=log.feature_id)
    return jsonify(message='审核拒绝')


@app.route('/api/audit-logs/<int:id>/withdraw', methods=['POST'])
@auth_required
def withdraw_audit(id):
    log = _find_pending_audit_log(id)
    if not log:
        return jsonify(message='审核记录不存在'), 404

    if log.status != 'pending':
        return jsonify(message='该审核已失效'), 400

    ctx = get_auth_context()
    withdrawn_by = (request.get_json() or {}).get('withdrawn_by') or ctx.get('username')
    if log.created_by != withdrawn_by:
        return jsonify(message='只有创建者可以撤回审核'), 403

    log.status = 'withdrawn'
    log.approved_by = withdrawn_by
    log.approved_at = datetime.utcnow()

    feature = Feature.query.get(log.feature_id)
    _reject_or_withdraw_feature(log, feature, 'approved')

    db.session.commit()
    emit_data_change('audit_withdrawn', actor=withdrawn_by, scope='audit', resource_id=log.feature_id)
    emit_data_change('features_changed', actor=withdrawn_by, scope='features', resource_id=log.feature_id)
    return jsonify(message='审核撤回成功')

@app.route('/api/features', methods=['GET'])
@auth_required
def get_features():
    ctx = get_auth_context()
    user_role = ctx['role']
    user_id = ctx['user_id']
    viewer_username = ctx['username']
    include_pending = request.args.get('include_pending', 'false').lower() == 'true'
    if user_role != 'admin':
        include_pending = False

    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)

    all_features = Feature.query.all()
    feature_map = {}

    for feature in all_features:
        view_data = resolve_feature_view(
            feature, AuditLog, user_role, viewer_username, include_pending
        )
        if view_data is None:
            continue
        feature_map[feature.id] = view_data

    tree = []

    if user_role == 'admin':
        for feature_id, feature_data in feature_map.items():
            parent_id = feature_data['parent_id']
            if parent_id is None:
                tree.append(feature_data)
            elif parent_id in feature_map:
                feature_map[parent_id]['children'].append(feature_data)
    else:
        if user_id:
            user_apps = UserApp.query.filter_by(user_id=user_id).all()
            authorized_app_ids = [ua.app_id for ua in user_apps]
            authorized_feature_ids = set()

            for app_id in authorized_app_ids:
                if app_id in feature_map:
                    authorized_feature_ids.add(app_id)

                    def add_children(feature_id):
                        for child_id, child_data in feature_map.items():
                            if child_data['parent_id'] == feature_id:
                                authorized_feature_ids.add(child_id)
                                add_children(child_id)

                    add_children(app_id)

            for feature_id, feature_data in feature_map.items():
                if feature_id in authorized_feature_ids:
                    parent_id = feature_data['parent_id']
                    if parent_id is None:
                        tree.append(feature_data)
                    elif parent_id in authorized_feature_ids and parent_id in feature_map:
                        feature_map[parent_id]['children'].append(feature_data)

    return jsonify({
        'data': tree,
        'total': len(all_features),
        'page': page,
        'page_size': page_size,
    })

def get_app_root_id(node_id):
    node = Feature.query.get(node_id)
    while node and node.parent_id:
        node = Feature.query.get(node.parent_id)
    return node.id if node else None


@app.route('/api/features', methods=['POST'])
@auth_required
def create_feature():
    data = request.get_json()
    ctx = get_auth_context()
    user_role = ctx['role']
    user_id = ctx['user_id']
    created_by = data.get('created_by') or ctx['username']
    
    if not data.get('name'):
        return jsonify(message='节点名称是必选项'), 400
    if not data.get('description'):
        return jsonify(message='节点描述是必选项'), 400
    
    parent_id = data.get('parent_id')
    name = data['name']
    node_type = data.get('node_type', 'function')
    
    if node_type == 'function' and parent_id is None:
        return jsonify(message='功能节点不能是根节点'), 400
    
    if node_type == 'function':
        if not data.get('version_range'):
            return jsonify(message='版本范围是必选项'), 400
        if 'is_guide_supported' not in data:
            return jsonify(message='是否支持引导是必选项'), 400
    
    if node_type == 'app' and user_role != 'admin':
        return jsonify(message='只有管理员可以添加应用节点'), 403
    
    if user_role != 'admin' and user_id:
        user_apps = UserApp.query.filter_by(user_id=user_id).all()
        authorized_app_ids = [ua.app_id for ua in user_apps]
        if parent_id:
            app_id = get_app_root_id(parent_id)
            if app_id not in authorized_app_ids:
                return jsonify(message='您没有权限在该应用中创建节点'), 403
    
    if Feature.query.filter_by(parent_id=parent_id, name=name).first():
        return jsonify(message='同一层级已存在同名节点'), 400
    
    status = 'approved' if user_role == 'admin' else 'pending'
    is_guide_supported = bool(data.get('is_guide_supported', False)) if node_type == 'function' else False
    
    feature = Feature(
        name=name,
        description=data['description'],
        use_cases=data.get('use_cases'),
        videos=data.get('videos'),
        version_range=data.get('version_range', 'All'),
        parent_id=parent_id,
        node_type=node_type,
        status=status,
        is_guide_supported=is_guide_supported,
        devices=data.get('devices'),
        created_by=created_by,
        updated_by=created_by,
        revision=1,
        updated_at=datetime.utcnow(),
    )
    db.session.add(feature)
    db.session.flush()
    
    if node_type == 'app':
        if not AppVersion.query.filter_by(app_id=feature.id, version='0.0.0.0').first():
            db.session.add(AppVersion(
                app_id=feature.id, version='0.0.0.0', changelog='初始版本'
            ))
    
    if user_role != 'admin':
        AuditLog.query.filter_by(feature_id=feature.id, status='pending').delete()
        after_content = feature_snapshot(feature)
        db.session.add(AuditLog(
            feature_id=feature.id,
            action='create',
            status='pending',
            created_by=created_by,
            after_content=dump_audit_content(after_content),
        ))
    else:
        bump_revision(feature)
    
    db.session.commit()
    if user_role != 'admin':
        emit_data_change('audit_submitted', actor=created_by, scope='audit', resource_id=feature.id)
    emit_data_change('features_changed', actor=created_by, scope='features', resource_id=feature.id)
    return jsonify(id=feature.id, message='节点添加成功', revision=feature.revision)

def _build_after_content_from_data(feature, data, parent_id, node_type):
    after = feature_snapshot(feature)
    after['name'] = data.get('name', feature.name)
    after['description'] = data.get('description', feature.description)
    after['parent_id'] = parent_id
    after['node_type'] = node_type
    if feature.node_type == 'function' or node_type == 'function':
        after['use_cases'] = data.get('use_cases', feature.use_cases)
        after['videos'] = data.get('videos', feature.videos)
        after['version_range'] = data.get('version_range', feature.version_range)
        after['is_guide_supported'] = bool(
            data.get('is_guide_supported', feature.is_guide_supported)
        )
        after['devices'] = data.get('devices', feature.devices)
    elif node_type in ('app', 'category'):
        after['is_guide_supported'] = False
    return after


@app.route('/api/features/<int:id>', methods=['PUT'])
@auth_required
def update_feature(id):
    feature = Feature.query.get(id)
    if not feature:
        return jsonify(message='节点不存在'), 404

    data = request.get_json() or {}
    ctx = get_auth_context()
    user_role = ctx['role']
    user_id = ctx['user_id']
    updated_by = data.get('updated_by') or ctx['username']

    if get_pending_audit(AuditLog, feature.id) and user_role != 'admin':
        return jsonify(message='待审核的节点在未被审核前不允许编辑'), 400

    if 'name' in data and not data['name']:
        return jsonify(message='节点名称是必选项'), 400
    if 'description' in data and not data['description']:
        return jsonify(message='节点描述是必选项'), 400

    if feature.node_type == 'function':
        if 'version_range' in data and not data['version_range']:
            return jsonify(message='版本范围是必选项'), 400
        if 'is_guide_supported' in data and data['is_guide_supported'] is None:
            return jsonify(message='是否支持引导是必选项'), 400

    parent_id = data.get('parent_id', feature.parent_id)
    node_type = data.get('node_type', feature.node_type)

    if node_type == 'function' and parent_id is None:
        return jsonify(message='功能节点不能是根节点'), 400

    if user_role != 'admin' and user_id:
        user_apps = UserApp.query.filter_by(user_id=user_id).all()
        authorized_app_ids = [ua.app_id for ua in user_apps]
        app_id = get_app_root_id(feature.id)
        if app_id not in authorized_app_ids:
            return jsonify(message='您没有权限修改该节点'), 403

    if 'name' in data and data['name'] != feature.name:
        if Feature.query.filter_by(parent_id=parent_id, name=data['name']).filter(
            Feature.id != id
        ).first():
            return jsonify(message='同一层级已存在同名节点'), 400

    before_content = feature_snapshot(feature)
    after_content = _build_after_content_from_data(feature, data, parent_id, node_type)

    if user_role != 'admin':
        AuditLog.query.filter_by(feature_id=feature.id, status='pending').delete()
        feature.status = 'pending'
        feature.updated_by = updated_by
        db.session.add(AuditLog(
            feature_id=feature.id,
            action='update',
            status='pending',
            created_by=updated_by,
            before_content=dump_audit_content(before_content),
            after_content=dump_audit_content(after_content),
        ))
    else:
        conflict = check_revision_conflict(feature, data)
        if conflict:
            return conflict
        apply_content_to_feature(feature, after_content)
        if feature.node_type in ['app', 'category']:
            feature.is_guide_supported = False
        feature.status = 'approved'
        feature.updated_by = updated_by
        bump_revision(feature)

        if get_pending_audit(AuditLog, feature.id):
            pending_logs = AuditLog.query.filter_by(
                feature_id=feature.id, status='pending'
            ).all()
            for log in pending_logs:
                log.status = 'approved'
                log.approved_by = updated_by
                log.approved_at = datetime.utcnow()

    db.session.commit()
    if user_role != 'admin':
        emit_data_change('audit_submitted', actor=updated_by, scope='audit', resource_id=feature.id)
    emit_data_change('features_changed', actor=updated_by, scope='features', resource_id=feature.id)
    return jsonify(message='节点更新成功', revision=feature.revision)

def delete_feature_recursive(feature):
    # 递归删除子节点
    for child in feature.children:
        delete_feature_recursive(child)
    # 删除该节点的所有审核记录
    AuditLog.query.filter_by(feature_id=feature.id).delete()
    # 如果是应用节点，删除关联的版本记录
    if feature.node_type == 'app':
        AppVersion.query.filter_by(app_id=feature.id).delete()
    db.session.delete(feature)

@app.route('/api/features/<int:id>', methods=['DELETE'])
@auth_required
def delete_feature(id):
    feature = Feature.query.get(id)
    if not feature:
        return jsonify(message='节点不存在'), 404

    data = request.get_json() or {}
    ctx = get_auth_context()
    user_role = ctx['role']
    user_id = ctx['user_id']
    deleted_by = data.get('deleted_by') or ctx['username']

    if user_role != 'admin' and user_id:
        user_apps = UserApp.query.filter_by(user_id=user_id).all()
        authorized_app_ids = [ua.app_id for ua in user_apps]
        app_id = get_app_root_id(feature.id)
        if app_id not in authorized_app_ids:
            return jsonify(message='您没有权限删除该节点'), 403

    pending_log = get_pending_audit(AuditLog, feature.id)

    if user_role != 'admin':
        if pending_log and pending_log.action == 'create':
            pending_log.status = 'rejected'
            pending_log.approved_by = deleted_by
            pending_log.approved_at = datetime.utcnow()
            delete_feature_recursive(feature)
            db.session.commit()
            emit_data_change('features_changed', actor=deleted_by, scope='features', resource_id=id)
            return jsonify(message='节点删除成功，审核已驳回')
        if pending_log:
            return jsonify(message='待审核的节点在未被审核前不允许删除'), 400

        before_content = feature_snapshot(feature)
        AuditLog.query.filter_by(feature_id=feature.id, status='pending').delete()
        db.session.add(AuditLog(
            feature_id=feature.id,
            action='delete',
            status='pending',
            created_by=deleted_by,
            before_content=dump_audit_content(before_content),
        ))
        feature.status = 'pending'
        feature.updated_by = deleted_by
        db.session.commit()
        emit_data_change('audit_submitted', actor=deleted_by, scope='audit', resource_id=id)
        emit_data_change('features_changed', actor=deleted_by, scope='features', resource_id=id)
        return jsonify(message='删除请求已提交，等待审核')

    if pending_log:
        pending_log.status = 'rejected'
        pending_log.approved_by = deleted_by
        pending_log.approved_at = datetime.utcnow()

    delete_feature_recursive(feature)
    db.session.commit()
    emit_data_change('features_changed', actor=deleted_by, scope='features', resource_id=id)
    return jsonify(message='节点删除成功')

def get_app_root(node):
    # 获取节点所属的应用根节点
    current = node
    while current.parent:
        current = current.parent
    return current


def get_app_root_name(feature_id):
    # 获取功能所属的应用名称
    feature = Feature.query.get(feature_id)
    if not feature:
        return '未知应用'
    
    # 递归获取根节点（应用节点）
    current = feature
    while current.parent_id:
        current = Feature.query.get(current.parent_id)
        if not current:
            break
    
    return current.name if current else '未知应用'

@app.route('/api/features/<int:id>/move', methods=['POST'])
@auth_required
def move_feature(id):
    feature = Feature.query.get(id)
    if not feature:
        return jsonify(message='节点不存在'), 404

    if feature.node_type == 'app':
        return jsonify(message='应用节点不支持移动'), 400

    data = request.get_json() or {}
    ctx = get_auth_context()
    user_role = ctx['role']
    user_id = ctx['user_id']
    updated_by = data.get('updated_by') or ctx['username']
    new_parent_id = data.get('new_parent_id')

    if get_pending_audit(AuditLog, feature.id) and user_role != 'admin':
        return jsonify(message='待审核的节点在未被审核前不允许移动'), 400

    if user_role != 'admin' and user_id:
        user_apps = UserApp.query.filter_by(user_id=user_id).all()
        authorized_app_ids = [ua.app_id for ua in user_apps]
        app_root = get_app_root(feature)
        if app_root.id not in authorized_app_ids:
            return jsonify(message='您没有权限移动该节点'), 403

    if new_parent_id:
        new_parent = Feature.query.get(new_parent_id)
        if not new_parent:
            return jsonify(message='新父节点不存在'), 404
        if new_parent.node_type == 'function':
            return jsonify(message='功能节点不能有子节点'), 400
        current = new_parent
        while current:
            if current.id == id:
                return jsonify(message='不能将节点移动到其自身的子树中'), 400
            current = current.parent
        if feature.node_type in ('category', 'function'):
            current_app = get_app_root(feature)
            new_app = get_app_root(new_parent)
            if current_app.id != new_app.id:
                msg = '分类节点不能跨应用移动' if feature.node_type == 'category' else '功能节点不能跨应用移动'
                return jsonify(message=msg), 400
    elif feature.node_type == 'category':
        return jsonify(message='分类节点不能移动到顶层'), 400

    if Feature.query.filter_by(parent_id=new_parent_id, name=feature.name).filter(
        Feature.id != id
    ).first():
        return jsonify(message='目标层级已存在同名节点'), 400

    if feature.node_type == 'function' and new_parent_id is None:
        return jsonify(message='功能节点不能是根节点'), 400

    old_parent_id = feature.parent_id
    before_content = feature_snapshot(feature)

    if user_role != 'admin':
        after_content = feature_snapshot(feature)
        after_content['parent_id'] = new_parent_id
        AuditLog.query.filter_by(feature_id=feature.id, status='pending').delete()
        feature.status = 'pending'
        feature.updated_by = updated_by
        db.session.add(AuditLog(
            feature_id=feature.id,
            action='move',
            status='pending',
            created_by=updated_by,
            before_content=dump_audit_content(before_content),
            after_content=dump_audit_content(after_content),
        ))
    else:
        conflict = check_revision_conflict(feature, data)
        if conflict:
            return conflict
        feature.parent_id = new_parent_id
        feature.status = 'approved'
        feature.updated_by = updated_by
        bump_revision(feature)

    db.session.commit()
    if user_role != 'admin':
        emit_data_change('audit_submitted', actor=updated_by, scope='audit', resource_id=id)
    emit_data_change('features_changed', actor=updated_by, scope='features', resource_id=id)
    return jsonify(message='节点移动成功', revision=feature.revision)


# 应用版本管理API
@app.route('/api/app-versions/<int:app_id>', methods=['GET'])
@auth_required
def get_app_versions(app_id):
    # 检查应用是否存在
    app = Feature.query.get(app_id)
    if not app or app.node_type != 'app':
        return jsonify(message='应用不存在'), 404
    
    versions = AppVersion.query.filter_by(app_id=app_id).order_by(AppVersion.version.desc()).all()
    return jsonify([{
        'id': version.id,
        'version': version.version,
        'changelog': version.changelog,
        'created_at': version.created_at.isoformat()
    } for version in versions])


@app.route('/api/app-versions', methods=['POST'])
@admin_required
def add_app_version():
    data = request.get_json()
    app_id = data.get('app_id')
    version = data.get('version')
    changelog = data.get('changelog')
    
    app = Feature.query.get(app_id)
    if not app or app.node_type != 'app':
        return jsonify(message='应用不存在'), 404
    
    existing_version = AppVersion.query.filter_by(app_id=app_id, version=version).first()
    if existing_version:
        return jsonify(message='该版本已存在'), 400
    
    new_version = AppVersion(
        app_id=app_id,
        version=version,
        changelog=changelog
    )
    db.session.add(new_version)
    db.session.commit()
    return jsonify(message='版本添加成功', id=new_version.id)


@app.route('/api/app-versions/<int:id>', methods=['DELETE'])
@admin_required
def delete_app_version(id):
    version = AppVersion.query.get(id)
    if not version:
        return jsonify(message='版本不存在'), 404
    
    db.session.delete(version)
    db.session.commit()
    return jsonify(message='版本删除成功')


# 设备管理API
@app.route('/api/devices', methods=['GET'])
@auth_required
def get_devices():
    devices = Device.query.all()
    return jsonify([{
        'id': device.id,
        'name': device.name,
        'device_model': device.device_model,
        'description': device.description,
        'release_name': device.release_name,
        'release_year': device.release_year,
        'created_at': device.created_at.isoformat(),
        'updated_at': device.updated_at.isoformat() if device.updated_at else None
    } for device in devices])


@app.route('/api/devices', methods=['POST'])
@admin_required
def create_device():
    data = request.get_json()
    
    if Device.query.filter_by(device_model=data['device_model']).first():
        return jsonify(message='设备型号已存在'), 400
    
    # 检查设备名称是否已存在（如果提供了名称）
    if 'name' in data and data['name']:
        if Device.query.filter_by(name=data['name']).first():
            return jsonify(message='设备名称已存在'), 400
    
    device = Device(
        name=data.get('name'),
        device_model=data['device_model'],
        description=data.get('description'),
        release_name=data.get('release_name'),
        release_year=data['release_year']
    )
    db.session.add(device)
    db.session.commit()
    return jsonify(id=device.id, message='设备添加成功')


@app.route('/api/devices/<int:id>', methods=['PUT'])
@admin_required
def update_device(id):
    device = Device.query.get(id)
    if not device:
        return jsonify(message='设备不存在'), 404
    
    data = request.get_json()
    
    if 'device_model' in data and data['device_model'] != device.device_model:
        if Device.query.filter_by(device_model=data['device_model']).filter(Device.id != id).first():
            return jsonify(message='设备型号已存在'), 400
    
    # 检查设备名称是否已存在（如果提供了名称且与当前名称不同）
    if 'name' in data and data['name'] != device.name:
        if data['name']:
            if Device.query.filter_by(name=data['name']).filter(Device.id != id).first():
                return jsonify(message='设备名称已存在'), 400
    
    device.name = data.get('name', device.name)
    device.device_model = data.get('device_model', device.device_model)
    device.description = data.get('description', device.description)
    device.release_name = data.get('release_name', device.release_name)
    device.release_year = data.get('release_year', device.release_year)
    device.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify(message='设备更新成功')


@app.route('/api/devices/<int:id>', methods=['DELETE'])
@admin_required
def delete_device(id):
    device = Device.query.get(id)
    if not device:
        return jsonify(message='设备不存在'), 404
    
    db.session.delete(device)
    db.session.commit()
    return jsonify(message='设备删除成功')

@app.route('/api/statistics', methods=['GET'])
@auth_required
def get_statistics():
    # 获取所有功能节点
    features = Feature.query.all()
    
    # 计算全局统计（排除未审核的节点）
    total_features = 0
    total_categories = 0
    total_apps = 0
    total_videos = 0
    
    # 计算未审核节点的统计
    pending_features = 0
    pending_categories = 0
    pending_total = 0
    
    # 按应用分组的统计
    app_statistics = {}
    
    for feature in features:
        if feature.node_type == 'app':
            total_apps += 1
            app_statistics[feature.id] = {
                'id': feature.id,
                'name': feature.name,
                'total_features': 0,
                'total_categories': 0,
                'total_videos': 0,
                'pending_features': 0,
                'pending_categories': 0,
                'pending_total': 0
            }
        elif feature.node_type == 'category':
            if feature.status == 'approved':
                total_categories += 1
            else:
                pending_categories += 1
                pending_total += 1
        elif feature.node_type == 'function':
            if feature.status == 'approved':
                total_features += 1
                # 计算视频数
                if feature.videos:
                    videos = list(filter(lambda v: v.strip(), feature.videos.split(',')))
                    total_videos += len(videos)
            else:
                pending_features += 1
                pending_total += 1
    
    # 计算每个应用的统计信息
    for feature in features:
        if feature.node_type in ['category', 'function']:
            # 获取所属应用
            app_root = get_app_root(feature)
            app_id = app_root.id
            
            if app_id in app_statistics:
                if feature.node_type == 'category':
                    if feature.status == 'approved':
                        app_statistics[app_id]['total_categories'] += 1
                    else:
                        app_statistics[app_id]['pending_categories'] += 1
                        app_statistics[app_id]['pending_total'] += 1
                elif feature.node_type == 'function':
                    if feature.status == 'approved':
                        app_statistics[app_id]['total_features'] += 1
                        # 计算视频数
                        if feature.videos:
                            videos = list(filter(lambda v: v.strip(), feature.videos.split(',')))
                            app_statistics[app_id]['total_videos'] += len(videos)
                    else:
                        app_statistics[app_id]['pending_features'] += 1
                        app_statistics[app_id]['pending_total'] += 1
    
    # 转换为列表格式
    app_stats_list = list(app_statistics.values())
    
    return jsonify({
        'global': {
            'total_apps': total_apps,
            'total_features': total_features,
            'total_categories': total_categories,
            'total_videos': total_videos,
            'pending_total': pending_total,
            'pending_features': pending_features,
            'pending_categories': pending_categories
        },
        'apps': app_stats_list
    })

def get_db_file_path():
    return os.path.join(app.instance_path, 'app_knowledge.db')


def sqlite_backup_to_file(dest_path):
    """使用 SQLite backup API 创建一致性快照。"""
    src_path = get_db_file_path()
    if not os.path.exists(src_path):
        return False
    src = sqlite3.connect(src_path)
    dest = sqlite3.connect(dest_path)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()
    return True


# 备份功能相关函数
def backup_database():
    """备份数据库"""
    print("Starting backup...")
    try:
        with app.app_context():
            print("Got app context")
            # 重新加载配置以获取最新值
            current_config = load_config()
            backup_config = current_config.get('backup', {})
            print(f"Got backup config: {backup_config}")
            
            if not backup_config.get('enabled', True):
                print("Backup is disabled")
                return
            
            # 确保备份目录存在
            backup_dir = backup_config.get('path', './backups')
            print(f"Backup directory: {backup_dir}")
            if not os.path.exists(backup_dir):
                print(f"Creating backup directory: {backup_dir}")
                os.makedirs(backup_dir)
            
            # 生成备份文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'backup_{timestamp}.db')
            print(f"Backup file: {backup_file}")
            
            # 备份数据库文件
            print(f"Instance path: {app.instance_path}")
            # 在 Flask 应用中，SQLite 数据库文件默认存储在 instance 目录中
            db_path = get_db_file_path()
            print(f"Trying to backup database from: {db_path}")
            if os.path.exists(db_path):
                print(f"Database file exists, starting backup...")
                print(f"Database file size: {os.path.getsize(db_path)} bytes")
                if sqlite_backup_to_file(backup_file):
                    print(f"Backup completed: {backup_file}")
                else:
                    shutil.copy2(db_path, backup_file)
                    print(f"Fallback copy backup completed: {backup_file}")
                print(f"Backup file size: {os.path.getsize(backup_file)} bytes")
                
                # 设置备份文件的修改时间为当前时间，确保排序正确
                current_time = time.time()
                os.utime(backup_file, (current_time, current_time))
                print(f"Set backup file modification time to current time: {datetime.fromtimestamp(current_time).isoformat()}")
                
                # 清理旧备份
                cleanup_old_backups()
                print("Cleanup completed")
            else:
                print(f"Database file not found at: {db_path}")
                # 如果在 instance 目录中找不到数据库文件，尝试在应用根目录中查找
                db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                print(f"Trying to backup database from: {db_path}")
                if os.path.exists(db_path):
                    print(f"Database file exists, starting backup...")
                    print(f"Database file size: {os.path.getsize(db_path)} bytes")
                    shutil.copy2(db_path, backup_file)
                    print(f"Backup completed: {backup_file}")
                    print(f"Backup file size: {os.path.getsize(backup_file)} bytes")
                    
                    # 设置备份文件的修改时间为当前时间，确保排序正确
                    current_time = time.time()
                    os.utime(backup_file, (current_time, current_time))
                    print(f"Set backup file modification time to current time: {datetime.fromtimestamp(current_time).isoformat()}")
                    
                    # 清理旧备份
                    cleanup_old_backups()
                    print("Cleanup completed")
                else:
                    print(f"Database file not found at: {db_path}")
    except Exception as e:
        print(f"Error during backup: {e}")
        import traceback
        traceback.print_exc()

def cleanup_old_backups():
    """清理旧备份"""
    with app.app_context():
        # 重新加载配置以获取最新值
        current_config = load_config()
        backup_config = current_config.get('backup', {})
        
        backup_dir = backup_config.get('path', './backups')
        if not os.path.exists(backup_dir):
            return
        
        # 获取所有备份文件并按时间排序
        backup_files = []
        for file in os.listdir(backup_dir):
            if file.startswith('backup_') and file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
                if os.path.isfile(file_path):
                    backup_files.append((file_path, os.path.getmtime(file_path)))
        
        # 按修改时间排序，最新的在前
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        # 保留最新的N个备份
        keep_count = backup_config.get('keep_latest', 10)
        for file_path, _ in backup_files[keep_count:]:
            os.remove(file_path)

def get_backup_schedule_interval(interval_str):
    """根据配置的间隔字符串返回定时任务间隔"""
    if interval_str == '1 hour':
        return schedule.every(1).hour
    elif interval_str == '1 day':
        return schedule.every(1).day
    elif interval_str == '1 week':
        return schedule.every(1).week
    elif interval_str == '1 month':
        return schedule.every(30).days
    else:
        return schedule.every(1).day

def run_backup_schedule():
    """运行备份定时任务"""
    while True:
        schedule.run_pending()
        time.sleep(60)

# 初始化备份定时任务
with app.app_context():
    # 使用配置文件中的设置
    current_config = load_config()
    backup_config = current_config.get('backup', {})
    if backup_config.get('enabled', True):
        interval = backup_config.get('interval', '1 day')
        scheduler = get_backup_schedule_interval(interval)
        scheduler.do(backup_database)

# 启动备份定时任务线程
backup_thread = threading.Thread(target=run_backup_schedule, daemon=True)
backup_thread.start()

# 备份配置API接口
@app.route('/api/backup/config', methods=['GET'])
@admin_required
def get_backup_config():
    current_config = load_config()
    backup_config = current_config.get('backup', {})
    
    return jsonify({
        'backup_path': backup_config.get('path', './backups'),
        'backup_interval': backup_config.get('interval', '1 day'),
        'keep_latest': backup_config.get('keep_latest', 10),
        'is_enabled': backup_config.get('enabled', True),
        'last_backup_at': None  # 不再跟踪最后备份时间
    }), 200

@app.route('/api/features/<int:app_id>/export', methods=['POST'])
@auth_required
def export_features(app_id):
    import zipfile
    import io
    import json
    import re
    
    # 检查应用是否存在
    app_feature = Feature.query.get(app_id)
    if not app_feature or app_feature.node_type != 'app':
        return jsonify(message='应用不存在'), 404
    
    # 获取请求体中的模板内容
    data = request.get_json()
    template = data.get('template', '')
    
    # 获取应用下的所有已审核功能节点
    def get_approved_features_under_app(app_node):
        approved_features = []
        
        def traverse(node):
            for child in node.children:
                if child.status == 'approved' and child.node_type == 'function':
                    approved_features.append(child)
                # 继续遍历子节点
                traverse(child)
        
        traverse(app_node)
        return approved_features
    
    approved_features = get_approved_features_under_app(app_feature)

    feature_ids = data.get('feature_ids')
    if feature_ids:
        try:
            selected_ids = {int(fid) for fid in feature_ids}
        except (TypeError, ValueError):
            return jsonify(message='feature_ids 格式无效'), 400
        approved_features = [f for f in approved_features if f.id in selected_ids]

    if not approved_features:
        return jsonify(message='该应用下没有已审核的功能节点可导出'), 400
    
    # 创建内存中的 zip 文件
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for feature in approved_features:
            # 生成 markdown 内容
            if template:
                # 使用模板生成内容
                markdown_content = template
                
                # 替换单值字段
                markdown_content = markdown_content.replace('{{name}}', feature.name)
                markdown_content = markdown_content.replace('{{description}}', feature.description)
                markdown_content = markdown_content.replace('{{version_range}}', feature.version_range)
                # 处理是否支持引导字段
                is_guide_supported_text = '是' if feature.is_guide_supported else '否'
                markdown_content = markdown_content.replace('{{is_guide_supported}}', is_guide_supported_text)
                markdown_content = markdown_content.replace('{{is_guide_supported ? \'是\' : \'否\'}}', is_guide_supported_text)
                
                # 处理使用案例
                if feature.use_cases:
                    # 使用正则表达式匹配use_cases模板部分
                    import re
                    use_cases_match = re.search(r'\{\{#use_cases\}\}(.*?)\{\{/use_cases\}\}', markdown_content, re.DOTALL)
                    if use_cases_match:
                        use_cases_section = use_cases_match.group(0)
                        use_case_template = use_cases_match.group(1).lstrip()
                        try:
                            # 尝试解析use_cases为JSON数组
                            use_cases_str = feature.use_cases.strip()
                            # 处理可能的JSON格式问题
                            if use_cases_str.startswith('[') and use_cases_str.endswith(']'):
                                use_cases = json.loads(use_cases_str)
                                use_cases_content = ''
                                # 严格按照数组索引处理，从1开始
                                for i, use_case in enumerate(use_cases, 1):
                                    # 为每个use_case生成内容，使用用户定义的模板
                                    case_content = use_case_template.replace('{{index}}', str(i-1))
                                    case_content = case_content.replace('{{index + 1}}', str(i))
                                    case_content = case_content.replace('{{value}}', str(use_case))
                                    use_cases_content += case_content
                                # 替换use_cases部分
                                markdown_content = markdown_content.replace(use_cases_section, use_cases_content)
                            else:
                                # 如果不是JSON数组格式，按换行符分割处理
                                use_cases = [uc.strip() for uc in use_cases_str.split('\n') if uc.strip()]
                                use_cases_content = ''
                                for i, use_case in enumerate(use_cases, 1):
                                    # 为每个use_case生成内容，使用用户定义的模板
                                    case_content = use_case_template.replace('{{index}}', str(i-1))
                                    case_content = case_content.replace('{{index + 1}}', str(i))
                                    case_content = case_content.replace('{{value}}', str(use_case))
                                    use_cases_content += case_content
                                markdown_content = markdown_content.replace(use_cases_section, use_cases_content)
                        except Exception as e:
                            print(f"Error processing use_cases: {e}")
                            # 如果处理失败，按简单文本处理
                            use_cases_content = feature.use_cases or ''
                            markdown_content = markdown_content.replace(use_cases_section, use_cases_content)
                else:
                    # 如果没有使用案例，移除相关部分
                    import re
                    use_cases_match = re.search(r'\{\{#use_cases\}\}(.*?)\{\{/use_cases\}\}', markdown_content, re.DOTALL)
                    if use_cases_match:
                        use_cases_section = use_cases_match.group(0)
                        markdown_content = markdown_content.replace(use_cases_section, '')
                
                # 处理视频链接
                if feature.videos:
                    # 使用正则表达式匹配videos模板部分
                    import re
                    videos_match = re.search(r'\{\{#videos\}\}(.*?)\{\{/videos\}\}', markdown_content, re.DOTALL)
                    if videos_match:
                        videos_section = videos_match.group(0)
                        video_template = videos_match.group(1).lstrip()
                        # 解析videos为数组
                        videos = [v.strip() for v in feature.videos.split(',') if v.strip()]
                        videos_content = ''
                        # 严格按照数组索引处理，从1开始
                        for i, video in enumerate(videos, 1):
                            # 为每个video生成内容，使用用户定义的模板
                            video_content = video_template.replace('{{index}}', str(i-1))
                            video_content = video_content.replace('{{index + 1}}', str(i))
                            video_content = video_content.replace('{{url}}', str(video))
                            videos_content += video_content
                        # 替换videos部分
                        markdown_content = markdown_content.replace(videos_section, videos_content)
                else:
                    # 如果没有视频链接，移除相关部分
                    import re
                    videos_match = re.search(r'\{\{#videos\}\}(.*?)\{\{/videos\}\}', markdown_content, re.DOTALL)
                    if videos_match:
                        videos_section = videos_match.group(0)
                        markdown_content = markdown_content.replace(videos_section, '')
                
                # 处理支持设备
                if feature.devices:
                    # 使用正则表达式匹配devices模板部分
                    import re
                    devices_match = re.search(r'\{\{#devices\}\}(.*?)\{\{/devices\}\}', markdown_content, re.DOTALL)
                    if devices_match:
                        devices_section = devices_match.group(0)
                        device_template = devices_match.group(1).lstrip()
                        # 解析devices为数组
                        device_ids = [d.strip() for d in feature.devices.split(',') if d.strip()]
                        if device_ids and device_ids[0] != 'all':
                            # 获取设备信息并排序
                            devices = []
                            for device_id in device_ids:
                                try:
                                    device = Device.query.get(int(device_id))
                                    if device:
                                        devices.append(device)
                                except:
                                    pass
                            # 按发布年份降序，发布名称字母序升序排列
                            devices.sort(key=lambda x: (-x.release_year, x.release_name))
                            # 生成设备内容
                            devices_content = ''
                            for device in devices:
                                # 为每个device生成内容，使用用户定义的模板
                                device_content = device_template.replace('{{device_name}}', f"{device.release_name} {device.release_year}")
                                device_content = device_content.replace('{{device_model}}', device.device_model)
                                devices_content += device_content
                        else:
                            # 所有设备
                            device_content = device_template.replace('{{device_name}}', "所有设备")
                            device_content = device_content.replace('{{device_model}}', "所有设备")
                            devices_content = device_content
                        # 替换devices部分
                        markdown_content = markdown_content.replace(devices_section, devices_content)
                else:
                    # 如果没有支持设备，移除相关部分
                    import re
                    devices_match = re.search(r'\{\{#devices\}\}(.*?)\{\{/devices\}\}', markdown_content, re.DOTALL)
                    if devices_match:
                        devices_section = devices_match.group(0)
                        markdown_content = markdown_content.replace(devices_section, '')
                
                # 移除不需要的字段
                markdown_content = markdown_content.replace('{{node_type}}', '')
                markdown_content = markdown_content.replace('{{status}}', '')
                markdown_content = markdown_content.replace('{{created_at}}', '')
                markdown_content = markdown_content.replace('{{updated_at}}', '')
                markdown_content = markdown_content.replace('{{ancestor_path}}', '')
            else:
                # 使用默认模板
                markdown_content = f"# 功能名称\n{feature.name}\n\n"
                markdown_content += f"# 功能描述\n{feature.description}\n\n"
                
                # 添加使用案例
                if feature.use_cases:
                    markdown_content += "# 典型使用案例\n"
                    try:
                        use_cases = json.loads(feature.use_cases)
                        for i, use_case in enumerate(use_cases, 1):
                            markdown_content += f"## 案例 {i}\n{use_case}\n\n"
                    except:
                        markdown_content += f"{feature.use_cases}\n\n"
                
                # 添加视频链接
                if feature.videos:
                    markdown_content += "# 教学视频\n"
                    videos = [v.strip() for v in feature.videos.split(',') if v.strip()]
                    for i, video in enumerate(videos, 1):
                        markdown_content += f"## 视频 {i}\n{video}\n\n"
                
                # 添加版本范围
                markdown_content += f"# 版本范围\n{feature.version_range}\n\n"
                # 添加是否支持引导
                is_guide_supported_text = '是' if feature.is_guide_supported else '否'
                markdown_content += f"# 是否支持引导\n{is_guide_supported_text}\n\n"
                # 添加支持设备
                markdown_content += f"# 支持设备\n"
                if feature.devices:
                    device_ids = [d.strip() for d in feature.devices.split(',') if d.strip()]
                    if device_ids and device_ids[0] != 'all':
                        # 获取设备信息并排序
                        devices = []
                        for device_id in device_ids:
                            try:
                                device = Device.query.get(int(device_id))
                                if device:
                                    devices.append(device)
                            except:
                                pass
                        # 按发布年份降序，发布名称字母序升序排列
                        devices.sort(key=lambda x: (-x.release_year, x.release_name))
                        # 生成设备内容
                        for device in devices:
                            markdown_content += f"{device.release_name} {device.release_year}\n"
                    else:
                        markdown_content += "所有设备\n"
                else:
                    markdown_content += "无\n"
                markdown_content += "\n"
            
            # 生成文件名（确保文件名安全）
            safe_name = feature.name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            file_name = f"{safe_name}.md"
            
            # 将 markdown 内容添加到 zip 文件中
            zip_file.writestr(file_name, markdown_content)
    
    # 重置缓冲区位置到开始
    zip_buffer.seek(0)
    
    # 生成响应
    from flask import send_file
    
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{app_feature.name}_导出.zip"
    )


@app.route('/api/backup/config', methods=['PUT'])
@admin_required
def update_backup_config():
    return jsonify(message='配置只能通过配置文件修改，服务启动前修改'), 403

@app.route('/api/backup/trigger', methods=['POST'])
@admin_required
def trigger_backup():
    backup_database()
    return jsonify(message='备份已触发'), 200

@app.route('/api/backup/list', methods=['GET'])
@admin_required
def list_backups():
    current_config = load_config()
    backup_config = current_config.get('backup', {})
    
    backup_dir = backup_config.get('path', './backups')
    backups = []
    
    if os.path.exists(backup_dir):
        for file in os.listdir(backup_dir):
            if file.startswith('backup_') and file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
                if os.path.isfile(file_path):
                    backups.append({
                        'filename': file,
                        'size': os.path.getsize(file_path),
                        'created_at': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
    
    # 按创建时间排序，最新的在前
    backups.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify(backups), 200

@app.route('/api/backup/delete/<filename>', methods=['DELETE'])
@admin_required
def delete_backup(filename):
    current_config = load_config()
    backup_config = current_config.get('backup', {})
    
    backup_dir = backup_config.get('path', './backups')
    file_path = os.path.join(backup_dir, filename)
    
    # 验证文件存在且是备份文件
    if not os.path.exists(file_path):
        return jsonify(message='备份文件不存在'), 404
    
    if not (filename.startswith('backup_') and filename.endswith('.db')):
        return jsonify(message='无效的备份文件名'), 400
    
    try:
        # 删除文件
        os.remove(file_path)
        print(f"Deleted backup: {filename}")
        
        # 运行清理以保持备份数量限制
        cleanup_old_backups()
        print("Ran cleanup after deletion")
        
        return jsonify(message='备份删除成功'), 200
    except Exception as e:
        print(f"Error deleting backup: {e}")
        return jsonify(message=f'删除备份失败: {str(e)}'), 500

@app.route('/api/backup/restore/<filename>', methods=['POST'])
@admin_required
def restore_backup(filename):
    global maintenance_mode
    current_config = load_config()
    backup_config = current_config.get('backup', {})
    
    backup_dir = backup_config.get('path', './backups')
    backup_path = os.path.join(backup_dir, filename)
    
    # 验证文件存在且是备份文件
    if not os.path.exists(backup_path):
        return jsonify(message='备份文件不存在'), 404
    
    if not (filename.startswith('backup_') and filename.endswith('.db')):
        return jsonify(message='无效的备份文件名'), 400
    
    try:
        maintenance_mode = True
        print(f"Restoring backup: {filename}")
        
        db_path = get_db_file_path()
        print(f"Restoring to: {db_path}")
        
        db.session.remove()
        db.engine.dispose()
        
        shutil.copy2(backup_path, db_path)
        print(f"Restore completed: {filename}")
        
        os.chmod(db_path, 0o644)
        db.engine.dispose()
        
        return jsonify(message='备份恢复成功'), 200
    except Exception as e:
        print(f"Error restoring backup: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(message=f'恢复备份失败: {str(e)}'), 500
    finally:
        maintenance_mode = False

@app.route('/api/backup/import', methods=['POST'])
@admin_required
def import_database():
    global maintenance_mode
    maintenance_mode = True
    try:
        if 'file' not in request.files:
            return jsonify(message='请选择要导入的数据库文件'), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify(message='请选择要导入的数据库文件'), 400
        
        # 验证文件类型
        if not file.filename.endswith('.db'):
            return jsonify(message='只能导入.db文件'), 400
        
        # 保存上传的文件
        upload_dir = os.path.join(app.instance_path, 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        print(f"Uploaded file: {file_path}")
        
        # 实现schema版本检查
        # 获取当前数据库的schema版本
        current_version = SchemaVersion.query.order_by(SchemaVersion.id.desc()).first().version
        print(f"Current schema version: {current_version}")
        
        # 从导入的数据库文件中获取schema版本
        imported_version = None
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            # 检查是否存在schema_version表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';")
            if cursor.fetchone():
                cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1;")
                result = cursor.fetchone()
                if result:
                    imported_version = result[0]
                    print(f"Imported schema version: {imported_version}")
            conn.close()
        except Exception as e:
            print(f"Error reading imported database version: {e}")
            return jsonify(message='无法读取导入文件的版本信息'), 400
        
        # 如果导入的数据库没有版本信息，默认视为旧版本
        if not imported_version:
            imported_version = '1.0.0'
            print(f"Imported database has no version info, assuming: {imported_version}")
        
        # 比较版本
        if compare_versions(imported_version, current_version) > 0:
            os.remove(file_path)
            return jsonify(message=f'只能导入小于等于当前版本({current_version})的schema，导入文件版本为{imported_version}'), 400
        
        # 实现数据适配逻辑
        print("Starting data adaptation...")
        
        # 确定数据库文件路径
        db_path = os.path.join(app.instance_path, 'app_knowledge.db')
        temp_db_path = os.path.join(upload_dir, 'temp_import.db')
        new_db_path = os.path.join(upload_dir, 'new_import.db')
        
        try:
            # 1. 复制上传的文件到临时位置
            shutil.copy2(file_path, temp_db_path)
            print(f"Created temporary database: {temp_db_path}")
            
            # 2. 创建新的数据库结构（使用当前版本的模型）
            print("Creating new database structure...")
            # 先创建一个空的数据库文件
            open(new_db_path, 'w').close()
            
            # 直接使用sqlite3创建表结构
            new_conn = sqlite3.connect(new_db_path)
            new_cursor = new_conn.cursor()
            
            # 创建user表
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS user (
                    id INTEGER NOT NULL,
                    username VARCHAR(50) NOT NULL,
                    password VARCHAR(100) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE (username)
                )
            ''')
            
            # 创建feature表
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS feature (
                    id INTEGER NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT NOT NULL,
                    use_cases TEXT,
                    videos TEXT,
                    version_range VARCHAR(100) NOT NULL,
                    parent_id INTEGER,
                    node_type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    is_guide_supported BOOLEAN NOT NULL,
                    devices TEXT,
                    created_by VARCHAR(50),
                    updated_by VARCHAR(50),
                    created_at DATETIME NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at DATETIME,
                    PRIMARY KEY (id),
                    FOREIGN KEY(parent_id) REFERENCES feature (id)
                )
            ''')
            
            # 创建device表
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS device (
                    id INTEGER NOT NULL,
                    name VARCHAR(100),
                    device_model VARCHAR(100) NOT NULL,
                    description TEXT,
                    release_name VARCHAR(100),
                    release_year INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME,
                    PRIMARY KEY (id),
                    UNIQUE (device_model)
                )
            ''')
            
            # 创建user_app表
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_app (
                    id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    app_id INTEGER NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(user_id) REFERENCES user (id),
                    FOREIGN KEY(app_id) REFERENCES feature (id)
                )
            ''')
            
            # 创建audit_log表
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER NOT NULL,
                    feature_id INTEGER NOT NULL,
                    action VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    created_by VARCHAR(50) NOT NULL,
                    approved_by VARCHAR(50),
                    before_content TEXT,
                    after_content TEXT,
                    created_at DATETIME NOT NULL,
                    approved_at DATETIME,
                    PRIMARY KEY (id),
                    FOREIGN KEY(feature_id) REFERENCES feature (id)
                )
            ''')
            
            # 创建app_version表
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_version (
                    id INTEGER NOT NULL,
                    app_id INTEGER NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    changelog TEXT,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(app_id) REFERENCES feature (id)
                )
            ''')
            
            # 创建schema_version表
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INTEGER NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE (version)
                )
            ''')
            
            # 插入默认schema版本
            new_cursor.execute('INSERT INTO schema_version (id, version, created_at) VALUES (?, ?, ?)', (1, current_version, datetime.utcnow().isoformat()))
            
            new_conn.commit()
            new_conn.close()
            print("New database structure created")
            
            # 3. 数据迁移
            print("Migrating data...")
            # 连接临时数据库和新数据库
            temp_conn = sqlite3.connect(temp_db_path)
            new_conn = sqlite3.connect(new_db_path)
            temp_cursor = temp_conn.cursor()
            new_cursor = new_conn.cursor()
            
            # 获取当前版本的表结构
            current_tables = ['user', 'feature', 'device', 'audit_log', 'app_version', 'user_app']
            
            # 遍历每个表进行数据迁移
            for table in current_tables:
                print(f"Migrating table: {table}")
                
                # 获取新表的列信息
                new_cursor.execute(f"PRAGMA table_info({table});")
                new_columns = [column[1] for column in new_cursor.fetchall()]
                print(f"New table columns: {new_columns}")
                
                # 检查临时数据库中是否存在该表
                temp_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
                if temp_cursor.fetchone():
                    # 获取临时表的列信息
                    temp_cursor.execute(f"PRAGMA table_info({table});")
                    temp_columns = [column[1] for column in temp_cursor.fetchall()]
                    print(f"Temp table columns: {temp_columns}")
                    
                    # 找出共同的列
                    common_columns = [col for col in temp_columns if col in new_columns]
                    print(f"Common columns: {common_columns}")
                    
                    if common_columns:
                        # 构建插入语句
                        columns_str = ', '.join(common_columns)
                        placeholders = ', '.join(['?'] * len(common_columns))
                        insert_sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders});"
                        
                        # 读取临时表的数据
                        select_sql = f"SELECT {columns_str} FROM {table};"
                        temp_cursor.execute(select_sql)
                        rows = temp_cursor.fetchall()
                        
                        # 插入数据到新表
                        if rows:
                            new_cursor.executemany(insert_sql, rows)
                            new_conn.commit()
                            print(f"Migrated {len(rows)} rows to table {table}")
            
            # 关闭数据库连接
            temp_conn.close()
            new_conn.close()
            print("Data migration completed")
            
            # 4. 替换原始数据库
            print(f"Replacing original database: {db_path}")
            shutil.copy2(new_db_path, db_path)
            print("Database replaced")
            
            # 5. 重新初始化数据库连接
            print("Reinitializing database connection...")
            # 关闭当前数据库连接
            db.session.remove()
            # 刷新数据库引擎
            db.engine.dispose()
            print("Database connection reinitialized")
            
        except Exception as e:
            print(f"Error during data adaptation: {e}")
            import traceback
            traceback.print_exc()
            return jsonify(message=f'数据适配失败: {str(e)}'), 500
        finally:
            # 清理临时文件
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if os.path.exists(new_db_path):
                os.remove(new_db_path)
            print("Cleaned up temporary files")
        
        print("Import completed with data adaptation")
        
        # 设置正确的文件权限
        os.chmod(db_path, 0o644)
        print("Set correct permissions on database file")
        
        # 清理上传的临时文件
        os.remove(file_path)
        print(f"Cleaned up temporary file: {file_path}")
        
        return jsonify(message='数据库导入成功'), 200
    except Exception as e:
        print(f"Error importing database: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(message=f'导入数据库失败: {str(e)}'), 500
    finally:
        maintenance_mode = False


# ============================================
# 大模型相关API
# ============================================

# 导入服务（移到API函数内部，避免在初始化时导入失败）


@app.route('/api/llm/config', methods=['GET'])
@jwt_required()
def get_llm_config():
    """获取LLM配置"""
    try:
        # 检查权限
        identity = get_jwt_identity()
        print(f"DEBUG - Raw identity from JWT: {identity}, type: {type(identity)}")
        
        # 兼容两种格式：旧的字典格式和新的字符串格式
        if isinstance(identity, dict):
            # 旧格式：直接使用
            user_info = identity
        else:
            # 新格式：通过 get_current_user() 获取
            user_info = get_current_user()
        
        print(f"DEBUG - User info: {user_info}")
        
        if not user_info or user_info.get('role') != 'admin':
            return jsonify(message='只有管理员可以访问'), 403
        
        config = LLMConfig.query.first()
        if config:
            return jsonify(config.to_dict())
        else:
            return jsonify(message='未找到配置'), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify(message=f'获取配置失败: {str(e)}'), 500


@app.route('/api/llm/config', methods=['POST'])
@jwt_required()
def save_llm_config():
    """保存LLM配置"""
    try:
        # 检查权限
        identity = get_current_user()
        print(f"DEBUG - save config identity: {identity}")
        if not identity or identity.get('role') != 'admin':
            return jsonify(message='只有管理员可以访问'), 403
        
        data = request.get_json()
        
        # 检查是否已存在配置
        config = LLMConfig.query.first()
        if not config:
            config = LLMConfig()
        
        # 更新配置
        config.name = data.get('name', 'default')
        config.base_url = data.get('base_url', '')
        config.api_key = data.get('api_key', '')
        config.model_name = data.get('model_name', '')
        config.enable_search = data.get('enable_search', False)
        config.system_prompt = data.get('system_prompt', '')
        config.user_prompt = data.get('user_prompt', '')
        config.http_proxy = data.get('http_proxy', '')
        config.https_proxy = data.get('https_proxy', '')
        config.no_proxy = data.get('no_proxy', False)
        config.same_proxy = data.get('same_proxy', False)
        
        db.session.add(config)
        db.session.commit()
        
        return jsonify(message='配置保存成功', config=config.to_dict())
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify(message=f'保存配置失败: {str(e)}'), 500


@app.route('/api/llm/test', methods=['POST'])
@jwt_required()
def test_llm_connection():
    """测试LLM连接"""
    try:
        # 检查权限
        identity = get_current_user()
        print(f"DEBUG - test connection identity: {identity}")
        if not identity or identity.get('role') != 'admin':
            return jsonify(message='只有管理员可以访问'), 403
        
        # 导入服务
        from services.llm_service import LLMService
        
        # 获取配置
        config = LLMConfig.query.first()
        if not config:
            return jsonify(message='请先配置大模型'), 400
        
        if not config.api_key or not config.base_url:
            return jsonify(message='请先配置API Key和Base URL'), 400
        
        # 测试连接
        llm_service = LLMService(config)
        success, message = llm_service.test_connection()
        
        if success:
            return jsonify(message=message, success=True)
        else:
            return jsonify(message=message, success=False), 400
    except Exception as e:
        return jsonify(message=f'测试连接失败: {str(e)}'), 500


@app.route('/api/llm/optimize', methods=['POST'])
@jwt_required()
def optimize_description():
    """优化功能描述"""
    try:
        data = request.get_json()
        feature_id = data.get('feature_id')
        
        if not feature_id:
            return jsonify(message='功能ID不能为空'), 400
        
        # 获取功能
        feature = Feature.query.get(feature_id)
        if not feature:
            return jsonify(message='功能不存在'), 404
        
        # 获取LLM配置
        config = LLMConfig.query.first()
        if not config:
            return jsonify(message='请先配置大模型'), 400
        
        if not config.api_key or not config.base_url:
            return jsonify(message='请先配置API Key和Base URL'), 400
        
        # 导入服务
        from services.llm_service import LLMService
        from services.prompt_service import PromptService
        
        # 构建上下文
        context = PromptService.get_optimization_context(feature)
        
        # 渲染prompt
        system_prompt = PromptService.render_prompt(config.system_prompt, context)
        user_prompt = PromptService.render_prompt(config.user_prompt, context)
        
        # 调用大模型
        llm_service = LLMService(config)
        optimized_description = llm_service.optimize_description(system_prompt, user_prompt)
        
        return jsonify(
            message='优化成功',
            original_description=feature.description,
            optimized_description=optimized_description
        )
    except Exception as e:
        return jsonify(message=f'优化失败: {str(e)}'), 500


if __name__ == '__main__':
    app.run(debug=True, host=SERVER_HOST, port=SERVER_PORT)
