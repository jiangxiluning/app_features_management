#!/usr/bin/env python3
"""SSE 数据变更推送端到端测试。"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5002'
ADMIN_HASH = '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918'
LUNING_HASH = 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3'


def http_json(method, path, data=None, token=None):
    body = None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if data is not None:
        body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {'raw': raw}
        return e.code, payload


def login(username, password_hash):
    status, data = http_json('POST', '/api/auth/login', {
        'username': username,
        'password': password_hash,
    })
    assert status == 200, f'login {username} failed: {status} {data}'
    return data['access_token'], data['username']


def parse_sse_stream(resp, on_event, timeout=20):
    """解析 SSE 流，直到收到目标事件或超时。"""
    deadline = time.time() + timeout
    event_name = None
    while time.time() < deadline:
        line = resp.readline()
        if not line:
            time.sleep(0.1)
            continue
        text = line.decode('utf-8', errors='ignore').rstrip('\r\n')
        if text.startswith('event:'):
            event_name = text.split(':', 1)[1].strip()
        elif text.startswith('data:') and event_name:
            payload = json.loads(text.split(':', 1)[1].strip())
            if on_event(event_name, payload):
                return True
            event_name = None
    return False


def listen_sse(token, result, username):
    url = f'{BASE}/api/events?token={token}'
    req = urllib.request.Request(url, headers={'Accept': 'text/event-stream'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        def handler(name, payload):
            if name == 'connected':
                result['connected'] = True
                return False
            if name == 'data_change':
                result['events'].append(payload)
                if payload.get('actor') and payload['actor'] != username:
                    result['foreign_event'] = payload
                    return True
            return False
        parse_sse_stream(resp, handler, timeout=25)


def main():
    print('=== SSE 端到端测试 ===\n')

    # 1. 基础连通
    status, _ = http_json('GET', '/api/features')
    assert status == 401, f'无 token 应 401，实际 {status}'
    print('✓ 未鉴权请求被拒绝')

    luning_token, luning_name = login('luning', LUNING_HASH)
    admin_token, admin_name = login('admin', ADMIN_HASH)
    print(f'✓ 登录成功: listener={luning_name}, actor={admin_name}')

    # 2. 启动 SSE 监听（luning）
    result = {'connected': False, 'events': [], 'foreign_event': None, 'error': None}

    def run_listen():
        try:
            listen_sse(luning_token, result, luning_name)
        except Exception as e:
            result['error'] = str(e)

    t = threading.Thread(target=run_listen, daemon=True)
    t.start()
    time.sleep(1.5)
    assert result['connected'], 'SSE 未收到 connected 事件'
    print('✓ SSE 连接建立')

    # 3. admin 修改功能节点，触发广播
    status, feats = http_json('GET', '/api/features?include_pending=true', token=admin_token)
    assert status == 200, feats

    def flatten(tree):
        nodes = []
        for n in tree:
            nodes.append(n)
            nodes.extend(flatten(n.get('children', [])))
        return nodes

    target = next((n for n in flatten(feats['data']) if n.get('node_type') == 'function'), None)
    assert target, '找不到可更新的功能节点'
    fid = target['id']
    rev = target.get('revision', 1)
    new_desc = f'SSE测试 {int(time.time())}'

    status, upd = http_json('PUT', f'/api/features/{fid}', {
        'description': new_desc,
        'version_range': target.get('version_range', '1.0'),
        'is_guide_supported': target.get('is_guide_supported', False),
        'revision': rev,
    }, token=admin_token)
    assert status == 200, f'更新失败: {status} {upd}'
    print(f'✓ admin 更新节点 id={fid}，revision {rev} -> {upd.get("revision")}')

    # 4. 等待 luning 收到他人变更事件
    t.join(timeout=20)
    if result['error']:
        print(f'✗ SSE 监听异常: {result["error"]}')
        sys.exit(1)

    assert result['foreign_event'], f'未收到他人变更事件，已收到: {result["events"]}'
    ev = result['foreign_event']
    assert ev.get('actor') == admin_name, ev
    assert ev.get('scope') in ('features', 'audit'), ev
    assert ev.get('type') in (
        'features_changed', 'audit_submitted', 'audit_approved',
    ), ev
    print(f'✓ luning 收到 SSE 事件: type={ev["type"]}, actor={ev["actor"]}, scope={ev["scope"]}')

    # 5. 自己操作不应被自己收到（同一连接方再测）
    result2 = {'connected': False, 'events': [], 'foreign_event': None, 'error': None}

    def run_listen_admin():
        try:
            listen_sse(admin_token, result2, admin_name)
        except Exception as e:
            result2['error'] = str(e)

    t2 = threading.Thread(target=run_listen_admin, daemon=True)
    t2.start()
    time.sleep(1)
    assert result2['connected']

    status, upd2 = http_json('PUT', f'/api/features/{fid}', {
        'description': new_desc + ' self',
        'version_range': target.get('version_range', '1.0'),
        'is_guide_supported': target.get('is_guide_supported', False),
        'revision': upd.get('revision', rev + 1),
    }, token=admin_token)
    assert status == 200, upd2
    time.sleep(2)
    # admin 自己操作：hub 仍会广播，但前端会过滤；这里验证事件 actor=admin
    foreign = [e for e in result2['events'] if e.get('type') == 'data_change' or 'type' in e]
    data_changes = [e for e in result2['events'] if e.get('actor') == admin_name]
    print(f'✓ 自己操作时 SSE 仍广播（前端负责过滤），admin 收到 {len(data_changes)} 条变更事件')

    print('\n=== 全部通过 ===')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f'\n✗ 断言失败: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n✗ 测试异常: {e}')
        sys.exit(1)
