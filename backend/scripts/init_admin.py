#!/usr/bin/env python3
"""一次性初始化管理员账户。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, User, hash_password


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else 'admin'
    password = sys.argv[2] if len(sys.argv) > 2 else 'admin'

    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f'用户已存在: {username}')
            return
        user = User(
            username=username,
            password=hash_password(password),
            role='admin',
        )
        db.session.add(user)
        db.session.commit()
        print(f'管理员已创建: {username}')


if __name__ == '__main__':
    main()
