#!/usr/bin/env python3
"""迁移脚本测试：在临时库上验证 migrate_to_2_0_0。"""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime

BACKEND = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND)

import migrations.migrate_to_2_0_0 as mig


def create_fixture_db(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute('CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)')
    c.execute('''CREATE TABLE feature (
        id INTEGER PRIMARY KEY, name TEXT, description TEXT, use_cases TEXT, videos TEXT,
        version_range TEXT, parent_id INTEGER, node_type TEXT, status TEXT,
        is_guide_supported INTEGER, devices TEXT, created_by TEXT, updated_by TEXT,
        created_at TEXT)''')
    c.execute('''CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY, feature_id INTEGER, action TEXT, status TEXT,
        created_by TEXT, approved_by TEXT, before_content TEXT, after_content TEXT,
        created_at TEXT, approved_at TEXT)''')
    c.execute('CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version TEXT UNIQUE, created_at TEXT)')
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO schema_version VALUES (1, '1.0.1', ?)", (now,))
    c.execute("INSERT INTO feature VALUES (1,'App','desc',NULL,NULL,'All',NULL,'app','approved',0,NULL,'a','a',?)", (now,))
    c.execute("INSERT INTO feature VALUES (2,'Fn','new',NULL,NULL,'1.0',1,'function','pending',0,NULL,'d','d',?)", (now,))
    before = "{'name': 'Fn', 'description': 'old', 'parent_id': 1, 'node_type': 'function', 'version_range': '1.0', 'is_guide_supported': False, 'devices': None, 'use_cases': None, 'videos': None}"
    after = "{'name': 'Fn', 'description': 'new', 'parent_id': 1, 'node_type': 'function', 'version_range': '1.0', 'is_guide_supported': False, 'devices': None, 'use_cases': None, 'videos': None}"
    c.execute("INSERT INTO audit_log VALUES (1,2,'update','pending','d',NULL,?, ?, ?,NULL)", (before, after, now))
    conn.commit()
    conn.close()


def main():
    tmp = tempfile.mkdtemp()
    inst = os.path.join(tmp, 'instance')
    os.makedirs(inst)
    db_path = os.path.join(inst, 'app_knowledge.db')
    create_fixture_db(db_path)

    orig_get = mig.get_db_path
    orig_backup = mig.backup_database
    mig.get_db_path = lambda: db_path
    mig.backup_database = lambda prefix='test': None
    try:
        assert mig.run_migration(dry_run=True)
        assert mig.run_migration(dry_run=False)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('PRAGMA table_info(feature)')
        cols = [r[1] for r in c.fetchall()]
        assert 'revision' in cols, cols
        c.execute('SELECT description FROM feature WHERE id=2')
        assert c.fetchone()[0] == 'old'
        c.execute('SELECT version FROM schema_version ORDER BY id DESC LIMIT 1')
        assert c.fetchone()[0] == '2.0.0'
        conn.close()
        print('test_migration_2_0_0: OK')
    finally:
        mig.get_db_path = orig_get
        mig.backup_database = orig_backup
        shutil.rmtree(tmp)


if __name__ == '__main__':
    main()
