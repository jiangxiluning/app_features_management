#!/usr/bin/env python3
"""
方案 M+ 一致性改造集成测试：
- JWT 鉴权 / 管理员接口保护
- COW 写入（开发者不改已发布 Feature 正文）
- 读侧 pending 隔离
- revision 乐观锁 409
- 原子 approve
- move before_content 保留旧 parent_id
- 维护模式阻断写入
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime

BACKEND = os.path.dirname(os.path.abspath(__file__))

# 必须在 import app 之前设置，确保绝不触碰 instance/app_knowledge.db
_TEST_TMP = tempfile.mkdtemp(prefix='plan_test_')
_TEST_DB_PATH = os.path.join(_TEST_TMP, 'app_knowledge.db')
os.environ['PLAN_TEST_DATABASE_URI'] = f'sqlite:///{_TEST_DB_PATH}'
sys.path.insert(0, BACKEND)

import app as app_module  # noqa: E402

app_module.app.config['TESTING'] = True


def setup_test_app():
    """确认测试库路径隔离，并初始化 schema。"""
    uri = app_module.app.config['SQLALCHEMY_DATABASE_URI']
    prod_marker = os.path.join(BACKEND, 'instance', 'app_knowledge.db')
    if prod_marker in uri.replace('sqlite:///', ''):
        raise RuntimeError('拒绝运行：测试将操作生产数据库')

    with app_module.app.app_context():
        if not app_module.SchemaVersion.query.first():
            app_module.db.session.add(
                app_module.SchemaVersion(version='2.0.0')
            )
            app_module.db.session.commit()

    return app_module, _TEST_TMP


def seed_users(app_module):
    User = app_module.User
    pwd = app_module.hash_password('pass')
    specs = {
        'admin': 'admin',
        'dev1': 'developer',
        'dev2': 'developer',
    }
    with app_module.app.app_context():
        for username, role in specs.items():
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=pwd, role=role)
                app_module.db.session.add(user)
            else:
                user.password = pwd
                user.role = role
        app_module.db.session.commit()
        ids = {k: User.query.filter_by(username=k).first().id for k in specs}
    return ids


def seed_feature_tree(app_module, dev1_id):
    Feature = app_module.Feature
    UserApp = app_module.UserApp
    now = datetime.utcnow()
    with app_module.app.app_context():
        app = Feature(
            name='TestApp', description='app desc', version_range='All',
            parent_id=None, node_type='app', status='approved',
            is_guide_supported=False, created_by='admin', updated_by='admin',
            created_at=now, revision=1, updated_at=now,
        )
        app_module.db.session.add(app)
        app_module.db.session.flush()

        cat = Feature(
            name='Cat', description='cat desc', version_range='All',
            parent_id=app.id, node_type='category', status='approved',
            is_guide_supported=False, created_by='admin', updated_by='admin',
            created_at=now, revision=1, updated_at=now,
        )
        app_module.db.session.add(cat)
        app_module.db.session.flush()

        fn = Feature(
            name='Fn', description='published desc', version_range='1.0',
            parent_id=cat.id, node_type='function', status='approved',
            is_guide_supported=False, created_by='admin', updated_by='admin',
            created_at=now, revision=3, updated_at=now,
        )
        app_module.db.session.add(fn)
        app_module.db.session.flush()

        for uid in (dev1_id,):
            app_module.db.session.add(UserApp(user_id=uid, app_id=app.id))

        app_module.db.session.commit()
        return {'app': app.id, 'cat': cat.id, 'fn': fn.id}


def login(client, app_module, username):
    pwd = app_module.hash_password('pass')
    r = client.post('/api/auth/login', json={'username': username, 'password': pwd})
    assert r.status_code == 200, r.get_json()
    return r.get_json()['access_token']


def headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def flatten_tree(tree):
    nodes = []
    for n in tree:
        nodes.append(n)
        nodes.extend(flatten_tree(n.get('children', [])))
    return nodes


def find_node(tree, node_id):
    for n in flatten_tree(tree):
        if n['id'] == node_id:
            return n
    return None


class TestRunner:
    def __init__(self):
        self.app_module, self.tmp = setup_test_app()
        self.app = self.app_module.app
        self.client = self.app.test_client()
        self.user_ids = seed_users(self.app_module)
        self.ids = seed_feature_tree(self.app_module, self.user_ids['dev1'])
        self.admin_token = login(self.client, self.app_module, 'admin')
        self.dev1_token = login(self.client, self.app_module, 'dev1')
        self.dev2_token = login(self.client, self.app_module, 'dev2')
        self.passed = 0
        self.failed = 0

    def check(self, name, condition, detail=''):
        if condition:
            self.passed += 1
            print(f'  ✓ {name}')
        else:
            self.failed += 1
            print(f'  ✗ {name}: {detail}')

    def test_jwt_required(self):
        print('\n[JWT 鉴权]')
        r = self.client.get('/api/features')
        self.check('无 token 返回 401', r.status_code == 401)

        r = self.client.get('/api/features', headers=headers(self.dev1_token))
        self.check('有效 token 可访问', r.status_code == 200)

    def test_register_admin_only(self):
        print('\n[注册鉴权]')
        pwd = self.app_module.hash_password('newpass')
        r = self.client.post('/api/auth/register', json={
            'username': 'hacker', 'password': pwd, 'role': 'admin',
        })
        self.check('未授权注册返回 401/422', r.status_code in (401, 422))

        r = self.client.post('/api/auth/register', headers=headers(self.admin_token), json={
            'username': 'newdev', 'password': pwd, 'role': 'developer',
        })
        self.check('管理员可注册', r.status_code == 200)

    def test_backup_admin_only(self):
        print('\n[备份接口鉴权]')
        r = self.client.get('/api/backup/list')
        self.check('备份列表需鉴权', r.status_code in (401, 422))

        r = self.client.get('/api/backup/list', headers=headers(self.dev1_token))
        self.check('开发者不能列备份', r.status_code == 403)

        r = self.client.get('/api/backup/list', headers=headers(self.admin_token))
        self.check('管理员可列备份', r.status_code == 200)

    def test_cow_developer_update(self):
        print('\n[COW 开发者更新]')
        fn_id = self.ids['fn']
        r = self.client.put(
            f'/api/features/{fn_id}',
            headers=headers(self.dev1_token),
            json={
                'description': 'draft desc',
                'version_range': '1.0',
                'is_guide_supported': False,
            },
        )
        self.check('开发者更新提交成功', r.status_code == 200, r.get_json())

        Feature = self.app_module.Feature
        AuditLog = self.app_module.AuditLog
        with self.app.app_context():
            f = Feature.query.get(fn_id)
            self.check('Feature 正文未改（COW）', f.description == 'published desc')
            self.check('Feature status=pending', f.status == 'pending')
            log = AuditLog.query.filter_by(feature_id=fn_id, status='pending').first()
            self.check('存在 pending audit', log is not None and log.action == 'update')
            if log:
                after = self.app_module.parse_audit_content(log.after_content)
                self.check('audit after 含草稿', after.get('description') == 'draft desc')

    def test_read_isolation(self):
        print('\n[读侧 pending 隔离]')
        fn_id = self.ids['fn']

        r = self.client.get('/api/features', headers=headers(self.dev1_token))
        tree = r.get_json()['data']
        owner_view = find_node(tree, fn_id)
        self.check('提交人看到草稿', owner_view and owner_view['description'] == 'draft desc')

        r = self.client.get('/api/features', headers=headers(self.dev2_token))
        tree = r.get_json()['data']
        # dev2 无 UserApp 授权，树可能为空；给 dev2 授权后测试
        with self.app.app_context():
            self.app_module.db.session.add(
                self.app_module.UserApp(
                    user_id=self.user_ids['dev2'],
                    app_id=self.ids['app'],
                )
            )
            self.app_module.db.session.commit()

        r = self.client.get('/api/features', headers=headers(self.dev2_token))
        other_view = find_node(r.get_json()['data'], fn_id)
        self.check('他人只见已发布内容', other_view and other_view['description'] == 'published desc')
        self.check('他人见 status=approved', other_view and other_view['status'] == 'approved')

    def test_admin_revision_conflict(self):
        print('\n[revision 乐观锁]')
        fn_id = self.ids['fn']
        # 先批准 dev1 的 pending，恢复可编辑状态
        with self.app.app_context():
            log = self.app_module.AuditLog.query.filter_by(
                feature_id=fn_id, status='pending'
            ).first()
            if log:
                self.client.post(
                    f'/api/audit-logs/{log.id}/approve',
                    headers=headers(self.admin_token),
                    json={},
                )

        with self.app.app_context():
            f = self.app_module.Feature.query.get(fn_id)
            rev = f.revision

        r = self.client.put(
            f'/api/features/{fn_id}',
            headers=headers(self.admin_token),
            json={
                'description': 'admin v1',
                'version_range': '1.0',
                'is_guide_supported': False,
                'revision': rev,
            },
        )
        self.check('管理员带正确 revision 成功', r.status_code == 200)

        r = self.client.put(
            f'/api/features/{fn_id}',
            headers=headers(self.admin_token),
            json={
                'description': 'admin stale',
                'version_range': '1.0',
                'is_guide_supported': False,
                'revision': rev,
            },
        )
        self.check('过期 revision 返回 409', r.status_code == 409)

    def test_atomic_approve(self):
        print('\n[原子 approve]')
        fn_id = self.ids['fn']
        r = self.client.put(
            f'/api/features/{fn_id}',
            headers=headers(self.dev1_token),
            json={
                'description': 'another draft',
                'version_range': '1.0',
                'is_guide_supported': False,
            },
        )
        self.check('再次提交 pending', r.status_code == 200)

        with self.app.app_context():
            log_id = self.app_module.AuditLog.query.filter_by(
                feature_id=fn_id, status='pending'
            ).first().id

        r1 = self.client.post(
            f'/api/audit-logs/{log_id}/approve',
            headers=headers(self.admin_token),
            json={},
        )
        self.check('首次批准成功', r1.status_code == 200)

        r2 = self.client.post(
            f'/api/audit-logs/{log_id}/approve',
            headers=headers(self.admin_token),
            json={},
        )
        self.check('重复批准返回 409', r2.status_code == 409)

    def test_move_before_content(self):
        print('\n[move before_content]')
        fn_id = self.ids['fn']
        cat_id = self.ids['cat']
        app_id = self.ids['app']

        with self.app.app_context():
            # 新建可移动分类
            cat2 = self.app_module.Feature(
                name='Cat2', description='c2', version_range='All',
                parent_id=app_id, node_type='category', status='approved',
                is_guide_supported=False, created_by='admin', updated_by='admin',
                created_at=datetime.utcnow(), revision=1,
            )
            self.app_module.db.session.add(cat2)
            self.app_module.db.session.commit()
            cat2_id = cat2.id
            fn = self.app_module.Feature.query.get(fn_id)
            fn.parent_id = cat_id
            fn.revision = 5
            self.app_module.db.session.commit()

        r = self.client.post(
            f'/api/features/{fn_id}/move',
            headers=headers(self.dev1_token),
            json={'new_parent_id': cat2_id},
        )
        self.check('开发者 move 提交成功', r.status_code == 200)

        with self.app.app_context():
            f = self.app_module.Feature.query.get(fn_id)
            self.check('move 未改 DB parent_id（COW）', f.parent_id == cat_id)
            log = self.app_module.AuditLog.query.filter_by(
                feature_id=fn_id, status='pending', action='move'
            ).order_by(self.app_module.AuditLog.id.desc()).first()
            self.check('存在 move audit', log is not None)
            if log:
                before = self.app_module.parse_audit_content(log.before_content)
                after = self.app_module.parse_audit_content(log.after_content)
                self.check(
                    'before_content.parent_id 为旧值',
                    before.get('parent_id') == cat_id,
                    f'before={before}',
                )
                self.check(
                    'after_content.parent_id 为新值',
                    after.get('parent_id') == cat2_id,
                    f'after={after}',
                )

    def test_maintenance_mode(self):
        print('\n[维护模式]')
        self.app_module.maintenance_mode = True
        try:
            r = self.client.put(
                f'/api/features/{self.ids["fn"]}',
                headers=headers(self.admin_token),
                json={
                    'description': 'blocked',
                    'version_range': '1.0',
                    'is_guide_supported': False,
                    'revision': 99,
                },
            )
            self.check('维护模式阻断写入', r.status_code == 503)
        finally:
            self.app_module.maintenance_mode = False

    def test_consistency_helpers(self):
        print('\n[consistency 辅助函数]')
        from consistency import parse_audit_content, resolve_feature_view, check_revision_conflict

        raw = "{'name': 'x', 'description': 'y'}"
        parsed = parse_audit_content(raw)
        self.check('parse_audit_content literal_eval', parsed == {'name': 'x', 'description': 'y'})

        raw_json = json.dumps({'name': 'j'}, ensure_ascii=False)
        self.check('parse_audit_content JSON', parse_audit_content(raw_json) == {'name': 'j'})

        class RevFeature:
            revision = 2

        with self.app.app_context():
            resp = check_revision_conflict(RevFeature(), {'revision': 1})
            self.check('revision 冲突返回 409 元组', resp is not None and resp[1] == 409)

            fn = self.app_module.Feature.query.get(self.ids['fn'])
            view = resolve_feature_view(
                fn, self.app_module.AuditLog, 'developer', 'dev1', False
            )
            self.check('resolve_feature_view 返回 dict', isinstance(view, dict) and 'id' in view)

    def test_admin_delete_with_audit_log(self):
        print('\n[管理员删除含 audit 节点]')
        with self.app.app_context():
            Feature = self.app_module.Feature
            now = datetime.utcnow()
            node = Feature(
                name='ToDelete',
                description='d',
                version_range='1.0',
                parent_id=self.ids['cat'],
                node_type='function',
                status='approved',
                is_guide_supported=False,
                created_by='admin',
                updated_by='admin',
                created_at=now,
                revision=1,
                updated_at=now,
            )
            self.app_module.db.session.add(node)
            self.app_module.db.session.flush()
            node_id = node.id
            self.app_module.db.session.add(self.app_module.AuditLog(
                feature_id=node_id,
                action='update',
                status='approved',
                created_by='dev1',
                before_content='{}',
                after_content='{}',
            ))
            self.app_module.db.session.commit()

        r = self.client.delete(
            f'/api/features/{node_id}',
            headers=headers(self.admin_token),
            json={},
        )
        self.check('管理员删除含 audit 记录节点成功', r.status_code == 200, r.get_json())

        with self.app.app_context():
            gone = self.app_module.Feature.query.get(node_id) is None
            audits = self.app_module.AuditLog.query.filter_by(feature_id=node_id).count()
            self.check('节点已删除', gone)
            self.check('关联 audit 已清理', audits == 0)

    def run_all(self):
        print('=' * 60)
        print('方案 M+ 一致性集成测试')
        print('=' * 60)
        try:
            self.test_jwt_required()
            self.test_register_admin_only()
            self.test_backup_admin_only()
            self.test_cow_developer_update()
            self.test_read_isolation()
            self.test_admin_revision_conflict()
            self.test_atomic_approve()
            self.test_move_before_content()
            self.test_maintenance_mode()
            self.test_admin_delete_with_audit_log()
            self.test_consistency_helpers()
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)
            os.environ.pop('PLAN_TEST_DATABASE_URI', None)

        print('\n' + '=' * 60)
        print(f'结果: {self.passed} 通过, {self.failed} 失败')
        print('=' * 60)
        return self.failed == 0


def main():
    ok = TestRunner().run_all()
    if not ok:
        sys.exit(1)
    print('test_plan_consistency: OK')


if __name__ == '__main__':
    main()
