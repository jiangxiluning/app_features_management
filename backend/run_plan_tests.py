#!/usr/bin/env python3
"""运行方案 M+ 相关全部测试。"""
import subprocess
import sys
import os

BACKEND = os.path.dirname(os.path.abspath(__file__))
TESTS = [
    'test_migration_2_0_0.py',
    'test_plan_consistency.py',
]


def main():
    failed = []
    print('运行方案 M+ 测试套件\n')
    for name in TESTS:
        path = os.path.join(BACKEND, name)
        print(f'>>> {name}')
        r = subprocess.run([sys.executable, path], cwd=BACKEND)
        if r.returncode != 0:
            failed.append(name)
        print()
    if failed:
        print(f'失败: {", ".join(failed)}')
        sys.exit(1)
    print('全部测试通过')


if __name__ == '__main__':
    main()
