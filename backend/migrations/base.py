"""迁移脚本公共工具。"""
import json
import os
import shutil
from datetime import datetime


def get_db_path():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_dir, 'instance', 'app_knowledge.db')


def get_backup_dir():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_dir, 'backups')


def backup_database(prefix='pre_migrate_2_0_0'):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    backup_dir = get_backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'{prefix}_{ts}.db')
    shutil.copy2(db_path, backup_path)
    return backup_path


def rollback_database(backup_path):
    if not backup_path or not os.path.exists(backup_path):
        raise FileNotFoundError(f'备份不存在: {backup_path}')
    shutil.copy2(backup_path, get_db_path())


def ensure_reports_dir():
    reports_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'reports'
    )
    os.makedirs(reports_dir, exist_ok=True)
    return reports_dir


def write_report(report, filename_prefix='migrate_2_0_0'):
    reports_dir = ensure_reports_dir()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = os.path.join(reports_dir, f'{filename_prefix}_{ts}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path
