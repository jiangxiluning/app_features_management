#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量迁移至 schema 2.0.0：revision、pending 回迁、audit JSON、唯一索引。"""
import argparse
import ast
import json
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.base import backup_database, get_db_path, rollback_database, write_report

TARGET_VERSION = '2.0.0'
FEATURE_FIELDS = (
    'name', 'description', 'use_cases', 'videos', 'version_range',
    'parent_id', 'node_type', 'is_guide_supported', 'devices',
)


def parse_content(raw):
    if raw is None or raw == '':
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None


def column_exists(cursor, table, column):
    cursor.execute(f'PRAGMA table_info({table})')
    return column in [row[1] for row in cursor.fetchall()]


def index_exists(cursor, name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (name,),
    )
    return cursor.fetchone() is not None


def get_current_version(cursor):
    try:
        cursor.execute(
            'SELECT version FROM schema_version ORDER BY id DESC LIMIT 1'
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None


def compare_versions(v1, v2):
    p1 = list(map(int, v1.split('.')))
    p2 = list(map(int, v2.split('.')))
    n = max(len(p1), len(p2))
    p1.extend([0] * (n - len(p1)))
    p2.extend([0] * (n - len(p2)))
    for a, b in zip(p1, p2):
        if a < b:
            return -1
        if a > b:
            return 1
    return 0


def step_ddl(cursor, dry_run, report):
    if not column_exists(cursor, 'feature', 'revision'):
        if not dry_run:
            cursor.execute(
                'ALTER TABLE feature ADD COLUMN revision INTEGER NOT NULL DEFAULT 1'
            )
        report['stats']['ddl_revision'] = True
    if not column_exists(cursor, 'feature', 'updated_at'):
        if not dry_run:
            cursor.execute('ALTER TABLE feature ADD COLUMN updated_at DATETIME')
            cursor.execute(
                'UPDATE feature SET updated_at = created_at WHERE updated_at IS NULL'
            )
        report['stats']['ddl_updated_at'] = True


def step_duplicate_names(cursor, dry_run, report):
    cursor.execute('''
        SELECT parent_id, name, GROUP_CONCAT(id) AS ids, COUNT(*) AS cnt
        FROM feature
        WHERE parent_id IS NOT NULL
        GROUP BY parent_id, name
        HAVING cnt > 1
    ''')
    for parent_id, name, ids_str, cnt in cursor.fetchall():
        ids = [int(x) for x in ids_str.split(',')]
        ids.sort()
        for fid in ids[1:]:
            new_name = f'{name} (迁移重命名-{fid})'
            if not dry_run:
                cursor.execute(
                    'UPDATE feature SET name = ? WHERE id = ?',
                    (new_name, fid),
                )
            report['renamed_features'].append({
                'id': fid,
                'parent_id': parent_id,
                'old_name': name,
                'new_name': new_name,
            })
            report['stats']['duplicate_names_renamed'] += 1


def step_audit_json(cursor, dry_run, report):
    cursor.execute(
        'SELECT id, before_content, after_content FROM audit_log'
    )
    for log_id, before, after in cursor.fetchall():
        for field_name, raw in (('before_content', before), ('after_content', after)):
            if raw is None:
                continue
            parsed = parse_content(raw)
            if parsed is None:
                report['unparseable_audit_logs'].append({
                    'audit_log_id': log_id,
                    'field': field_name,
                })
                report['stats']['unparseable_audit_logs'] += 1
                continue
            new_val = json.dumps(parsed, ensure_ascii=False)
            if new_val != raw and not dry_run:
                cursor.execute(
                    f'UPDATE audit_log SET {field_name} = ? WHERE id = ?',
                    (new_val, log_id),
                )
                report['stats']['audit_json_converted'] += 1


def apply_content_to_row(cursor, feature_id, content):
    if not content:
        return
    sets = []
    vals = []
    for field in FEATURE_FIELDS:
        if field in content:
            sets.append(f'{field} = ?')
            vals.append(content[field])
    if sets:
        vals.append(feature_id)
        cursor.execute(
            f"UPDATE feature SET {', '.join(sets)} WHERE id = ?",
            vals,
        )


def step_pending_rollback(cursor, dry_run, report):
    cursor.execute("SELECT id, status, created_by FROM feature WHERE status = 'pending'")
    for feature_id, status, created_by in cursor.fetchall():
        cursor.execute('''
            SELECT id, action, before_content, after_content, created_by
            FROM audit_log
            WHERE feature_id = ? AND status = 'pending'
            ORDER BY id DESC LIMIT 1
        ''', (feature_id,))
        row = cursor.fetchone()
        if not row:
            if not dry_run:
                cursor.execute(
                    "UPDATE feature SET status = 'approved' WHERE id = ?",
                    (feature_id,),
                )
            report['orphan_pending_features'].append({'feature_id': feature_id})
            report['stats']['orphan_pending_fixed'] += 1
            continue

        log_id, action, before_raw, after_raw, _ = row
        before = parse_content(before_raw)
        after = parse_content(after_raw)

        if action == 'create':
            report['stats']['pending_create_kept'] += 1
            continue

        if action == 'delete':
            if not dry_run:
                cursor.execute(
                    "UPDATE feature SET status = 'approved' WHERE id = ?",
                    (feature_id,),
                )
            report['stats']['pending_rollback_delete'] += 1
            continue

        if action in ('update', 'move') and before:
            ap = after.get('parent_id') if after else None
            bp = before.get('parent_id')
            # 仅当 move 类变更且 before/after 的 parent_id 相同（历史 bug 快照）时跳过
            if action == 'move' or (after and bp != ap):
                if after and bp == ap:
                    report['corrupted_move_audits'].append({
                        'feature_id': feature_id,
                        'audit_log_id': log_id,
                        'reason': 'before.parent_id == after.parent_id',
                    })
                    report['stats']['corrupted_move_audits'] += 1
                    continue

            if not dry_run:
                apply_content_to_row(cursor, feature_id, before)
                cursor.execute(
                    "UPDATE feature SET status = 'pending' WHERE id = ?",
                    (feature_id,),
                )
            report['stats']['pending_rollback_update'] += 1


def step_unique_index(cursor, dry_run, report):
    if not index_exists(cursor, 'idx_feature_parent_name'):
        if not dry_run:
            cursor.execute('''
                CREATE UNIQUE INDEX idx_feature_parent_name
                ON feature(parent_id, name)
                WHERE parent_id IS NOT NULL
            ''')
        report['stats']['unique_index_created'] = True


def step_orphan_audits(cursor, dry_run, report):
    cursor.execute('''
        SELECT COUNT(*) FROM audit_log
        WHERE feature_id NOT IN (SELECT id FROM feature)
    ''')
    count = cursor.fetchone()[0]
    if count and not dry_run:
        cursor.execute('''
            DELETE FROM audit_log
            WHERE feature_id NOT IN (SELECT id FROM feature)
        ''')
    report['stats']['orphan_audits_deleted'] = count


def step_schema_version(cursor, dry_run, report):
    if not dry_run:
        cursor.execute(
            'INSERT INTO schema_version (version, created_at) VALUES (?, ?)',
            (TARGET_VERSION, datetime.utcnow().isoformat()),
        )
    report['stats']['schema_version'] = TARGET_VERSION


def verify(cursor, report):
    errors = []
    ver = get_current_version(cursor)
    if ver and compare_versions(ver, TARGET_VERSION) < 0 and report.get('executed'):
        errors.append(f'schema_version 未更新: {ver}')

    if not column_exists(cursor, 'feature', 'revision'):
        errors.append('feature.revision 列不存在')

    cursor.execute('''
        SELECT parent_id, name, COUNT(*) FROM feature
        WHERE parent_id IS NOT NULL
        GROUP BY parent_id, name HAVING COUNT(*) > 1
    ''')
    if cursor.fetchall():
        errors.append('仍存在重复 (parent_id, name)')

    return errors


def run_migration(dry_run=False):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f'数据库不存在: {db_path}')
        return False

    report = {
        'version': TARGET_VERSION,
        'dry_run': dry_run,
        'started_at': datetime.utcnow().isoformat(),
        'stats': {
            'duplicate_names_renamed': 0,
            'audit_json_converted': 0,
            'pending_rollback_update': 0,
            'pending_rollback_delete': 0,
            'pending_create_kept': 0,
            'orphan_pending_fixed': 0,
            'orphan_audits_deleted': 0,
            'corrupted_move_audits': 0,
            'unparseable_audit_logs': 0,
        },
        'renamed_features': [],
        'corrupted_move_audits': [],
        'orphan_pending_features': [],
        'unparseable_audit_logs': [],
        'backup_path': None,
    }

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    current = get_current_version(cursor)
    if current and compare_versions(current, TARGET_VERSION) >= 0:
        print(f'已迁移至 {current}，跳过')
        conn.close()
        return True

    backup_path = None
    if not dry_run:
        backup_path = backup_database()
        report['backup_path'] = backup_path
        print(f'已备份: {backup_path}')

    try:
        if not dry_run:
            conn.execute('BEGIN')
        step_ddl(cursor, dry_run, report)
        step_duplicate_names(cursor, dry_run, report)
        step_audit_json(cursor, dry_run, report)
        step_pending_rollback(cursor, dry_run, report)
        step_unique_index(cursor, dry_run, report)
        step_orphan_audits(cursor, dry_run, report)
        if not dry_run:
            step_schema_version(cursor, dry_run, report)
            conn.commit()
            report['executed'] = True
        else:
            conn.rollback()

        errors = verify(cursor, report)
        report['finished_at'] = datetime.utcnow().isoformat()
        report['verify_errors'] = errors
        report_path = write_report(report)
        print(f'报告: {report_path}')
        print(json.dumps(report['stats'], ensure_ascii=False, indent=2))

        if errors and not dry_run:
            print('验证失败:', errors)
            if backup_path:
                rollback_database(backup_path)
            return False

        print('迁移完成' if not dry_run else 'dry-run 完成')
        return True
    except Exception as e:
        if not dry_run:
            conn.rollback()
            if backup_path:
                rollback_database(backup_path)
        print(f'迁移失败: {e}')
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='迁移数据库至 2.0.0')
    parser.add_argument('--dry-run', action='store_true', help='预览不写库')
    parser.add_argument('--rollback', type=str, help='从备份恢复')
    args = parser.parse_args()

    if args.rollback:
        rollback_database(args.rollback)
        print(f'已从备份恢复: {args.rollback}')
        return

    ok = run_migration(dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
