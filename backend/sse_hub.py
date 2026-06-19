"""内存 SSE 广播中心（单 worker 场景）。"""
import json
import queue
import threading
from datetime import datetime

_lock = threading.Lock()
_subscribers = []
_seq = 0


def subscribe():
    q = queue.Queue(maxsize=100)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def broadcast_data_change(payload):
    """向所有 SSE 客户端广播数据变更事件。"""
    global _seq
    with _lock:
        _seq += 1
        event = {
            'seq': _seq,
            'at': datetime.utcnow().isoformat() + 'Z',
            **payload,
        }
        for q in list(_subscribers):
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
    return event


def format_sse(event_name, data):
    return f'event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
