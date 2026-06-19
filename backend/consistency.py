"""数据一致性辅助：鉴权上下文、审核内容解析、Feature 快照与读侧隔离。"""
import ast
import json
from datetime import datetime
from functools import wraps

from flask import jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

FEATURE_CONTENT_FIELDS = (
    'name', 'description', 'use_cases', 'videos', 'version_range',
    'parent_id', 'node_type', 'is_guide_supported', 'devices',
)


def parse_audit_content(raw):
    """解析 audit before/after 内容，兼容 JSON 与历史 str(dict)。"""
    if raw is None or raw == '':
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None


def dump_audit_content(data):
    return json.dumps(data, ensure_ascii=False)


def feature_snapshot(feature):
    return {
        'name': feature.name,
        'description': feature.description,
        'use_cases': feature.use_cases,
        'videos': feature.videos,
        'version_range': feature.version_range,
        'parent_id': feature.parent_id,
        'node_type': feature.node_type,
        'is_guide_supported': feature.is_guide_supported,
        'devices': feature.devices,
    }


def apply_content_to_feature(feature, content):
    if not content:
        return
    for field in FEATURE_CONTENT_FIELDS:
        if field in content and content[field] is not None:
            setattr(feature, field, content[field])


def get_pending_audit(AuditLog, feature_id):
    return AuditLog.query.filter_by(
        feature_id=feature_id, status='pending'
    ).order_by(AuditLog.id.desc()).first()


def merge_draft_into_dict(base_dict, draft_content):
    if not draft_content:
        return base_dict
    merged = dict(base_dict)
    for field in FEATURE_CONTENT_FIELDS:
        if field in draft_content:
            merged[field] = draft_content[field]
    merged['has_pending_draft'] = True
    return merged


def feature_to_dict(feature, revision_default=1):
    updated_at = getattr(feature, 'updated_at', None)
    revision = getattr(feature, 'revision', None)
    return {
        'id': feature.id,
        'name': feature.name,
        'description': feature.description,
        'use_cases': feature.use_cases,
        'videos': feature.videos,
        'version_range': feature.version_range,
        'parent_id': feature.parent_id,
        'node_type': feature.node_type,
        'status': feature.status,
        'is_guide_supported': feature.is_guide_supported,
        'devices': feature.devices,
        'created_by': feature.created_by,
        'updated_by': feature.updated_by,
        'created_at': feature.created_at.isoformat() if feature.created_at else None,
        'updated_at': updated_at.isoformat() if updated_at else None,
        'revision': revision if revision is not None else revision_default,
        'children': [],
    }


def resolve_feature_view(feature, AuditLog, viewer_role, viewer_username, include_pending=False):
    """按查看者角色解析 Feature 展示数据（COW 读模型 + pending 隔离）。"""
    data = feature_to_dict(feature)
    pending_log = get_pending_audit(AuditLog, feature.id)

    if feature.status != 'pending' and not pending_log:
        return data

    if pending_log:
        draft = parse_audit_content(pending_log.after_content)
        is_owner = pending_log.created_by == viewer_username
        is_admin = viewer_role == 'admin'

        if pending_log.action == 'delete':
            if is_admin and include_pending:
                data['pending_action'] = 'delete'
                data['status'] = 'pending'
            elif is_owner:
                data['pending_action'] = 'delete'
                data['status'] = 'pending'
            # 他人看到 approved 快照（feature 行未删）
            return data

        if pending_log.action == 'create':
            if is_admin or is_owner or include_pending:
                if draft:
                    data = merge_draft_into_dict(data, draft)
                data['status'] = 'pending'
                data['pending_action'] = 'create'
            else:
                return None  # 他人不见未审新建（整节点隐藏）
            return data

        # update / move
        if is_admin and include_pending:
            if draft:
                data = merge_draft_into_dict(data, draft)
            data['status'] = 'pending'
            data['pending_action'] = pending_log.action
        elif is_owner:
            if draft:
                data = merge_draft_into_dict(data, draft)
            data['status'] = 'pending'
            data['pending_action'] = pending_log.action
        else:
            # 他人只见已发布快照（feature 行，COW 下即 approved 内容）
            if feature.status == 'pending' and pending_log.before_content:
                published = parse_audit_content(pending_log.before_content)
                if published:
                    for field in FEATURE_CONTENT_FIELDS:
                        if field in published:
                            data[field] = published[field]
            data['status'] = 'approved'
        return data

    # status=pending 但无 audit（孤立）
    if viewer_role == 'admin' and include_pending:
        return data
    if feature.created_by == viewer_username:
        return data
    return data if feature.status == 'approved' else feature_to_dict(feature)


def get_auth_context():
    """从 JWT 获取当前用户上下文。"""
    try:
        claims = get_jwt()
        identity = get_jwt_identity()
        if identity and claims:
            return {
                'username': identity,
                'role': claims.get('role', 'developer'),
                'user_id': claims.get('user_id'),
            }
    except Exception:
        pass
    return None


def auth_required(fn):
    """要求有效 JWT。"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        ctx = get_auth_context()
        if not ctx or not ctx.get('user_id'):
            return jsonify(message='未授权访问'), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        ctx = get_auth_context()
        if not ctx or ctx.get('role') != 'admin':
            return jsonify(message='只有管理员可以执行此操作'), 403
        return fn(*args, **kwargs)
    return wrapper


def check_maintenance(maintenance_flag):
    """写操作前检查维护模式。"""
    if maintenance_flag and request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        path = request.path or ''
        if not path.endswith('/auth/login') and not path.endswith('/auth/register'):
            return jsonify(message='系统维护中，请稍后再试'), 503
    return None


def bump_revision(feature):
    rev = getattr(feature, 'revision', None) or 1
    feature.revision = rev + 1
    if hasattr(feature, 'updated_at'):
        feature.updated_at = datetime.utcnow()


def check_revision_conflict(feature, data):
    if 'revision' not in data:
        return None
    current = getattr(feature, 'revision', 1) or 1
    if data['revision'] != current:
        return jsonify(message='数据已被他人修改，请刷新后重试', revision=current), 409
    return None


def emit_data_change(event_type, actor=None, scope='features', resource_id=None):
    """广播数据变更，供 SSE 客户端提示刷新。"""
    try:
        from sse_hub import broadcast_data_change
        broadcast_data_change({
            'type': event_type,
            'scope': scope,
            'actor': actor,
            'resource_id': resource_id,
        })
    except Exception:
        pass
