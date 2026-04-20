#!/usr/bin/env python3
"""
测试数据库导入功能的测试脚本
"""
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

# 测试用例1: 创建一个旧版本的测试数据库
def create_old_version_db(db_path):
    """创建一个旧版本(1.0.0)的测试数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建user表
    cursor.execute('''
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feature (
            id INTEGER NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            use_cases TEXT,
            version_range VARCHAR(100) NOT NULL,
            parent_id INTEGER,
            node_type VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL,
            is_guide_supported BOOLEAN NOT NULL,
            created_by VARCHAR(50),
            updated_by VARCHAR(50),
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(parent_id) REFERENCES feature (id)
        )
    ''')
    
    # 创建schema_version表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER NOT NULL,
            version VARCHAR(50) NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (version)
        )
    ''')
    
    # 插入测试数据
    cursor.execute('INSERT INTO user (id, username, password, role) VALUES (?, ?, ?, ?)', (1, 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin'))
    cursor.execute('INSERT INTO user (id, username, password, role) VALUES (?, ?, ?, ?)', (2, 'testuser', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'developer'))
    
    cursor.execute('INSERT INTO feature (id, name, description, version_range, node_type, status, is_guide_supported, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                  (1, 'Test App', 'Test application', '1.0.0', 'app', 'approved', 0, datetime.utcnow().isoformat()))
    cursor.execute('INSERT INTO feature (id, name, description, version_range, parent_id, node_type, status, is_guide_supported, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                  (2, 'Test Feature', 'Test feature', '1.0.0', 1, 'function', 'approved', 0, datetime.utcnow().isoformat()))
    
    cursor.execute('INSERT INTO schema_version (id, version, created_at) VALUES (?, ?, ?)', (1, '1.0.0', datetime.utcnow().isoformat()))
    
    conn.commit()
    conn.close()
    print(f"Created old version test database: {db_path}")

# 测试用例2: 创建一个同版本的测试数据库
def create_same_version_db(db_path):
    """创建一个同版本(1.0.1)的测试数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建所有表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER NOT NULL,
            username VARCHAR(50) NOT NULL,
            password VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (username)
        )
    ''')
    
    cursor.execute('''
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
            PRIMARY KEY (id),
            FOREIGN KEY(parent_id) REFERENCES feature (id)
        )
    ''')
    
    cursor.execute('''
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER NOT NULL,
            version VARCHAR(50) NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (version)
        )
    ''')
    
    # 插入测试数据
    cursor.execute('INSERT INTO user (id, username, password, role) VALUES (?, ?, ?, ?)', (1, 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin'))
    cursor.execute('INSERT INTO feature (id, name, description, version_range, node_type, status, is_guide_supported, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                  (1, 'Same Version App', 'Same version application', '1.0.1', 'app', 'approved', 1, datetime.utcnow().isoformat()))
    cursor.execute('INSERT INTO device (id, name, device_model, release_year, created_at) VALUES (?, ?, ?, ?, ?)', 
                  (1, 'Test Device', 'test-model-1', 2024, datetime.utcnow().isoformat()))
    cursor.execute('INSERT INTO schema_version (id, version, created_at) VALUES (?, ?, ?)', (1, '1.0.1', datetime.utcnow().isoformat()))
    
    conn.commit()
    conn.close()
    print(f"Created same version test database: {db_path}")

# 测试用例3: 创建一个新版本的测试数据库
def create_new_version_db(db_path):
    """创建一个新版本(1.0.2)的测试数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER NOT NULL,
            username VARCHAR(50) NOT NULL,
            password VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (username)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER NOT NULL,
            version VARCHAR(50) NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (version)
        )
    ''')
    
    # 插入数据
    cursor.execute('INSERT INTO user (id, username, password, role) VALUES (?, ?, ?, ?)', (1, 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin'))
    cursor.execute('INSERT INTO schema_version (id, version, created_at) VALUES (?, ?, ?)', (1, '1.0.2', datetime.utcnow().isoformat()))
    
    conn.commit()
    conn.close()
    print(f"Created new version test database: {db_path}")

# 测试用例4: 创建一个无版本信息的测试数据库
def create_no_version_db(db_path):
    """创建一个无版本信息的测试数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表但不创建schema_version表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER NOT NULL,
            username VARCHAR(50) NOT NULL,
            password VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (username)
        )
    ''')
    
    # 插入数据
    cursor.execute('INSERT INTO user (id, username, password, role) VALUES (?, ?, ?, ?)', (1, 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin'))
    
    conn.commit()
    conn.close()
    print(f"Created no version test database: {db_path}")

if __name__ == '__main__':
    # 创建测试数据库目录
    test_dir = os.path.join(os.path.dirname(__file__), 'test_databases')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # 创建测试数据库
    create_old_version_db(os.path.join(test_dir, 'old_version.db'))
    create_same_version_db(os.path.join(test_dir, 'same_version.db'))
    create_new_version_db(os.path.join(test_dir, 'new_version.db'))
    create_no_version_db(os.path.join(test_dir, 'no_version.db'))
    
    print("\n测试数据库创建完成！")
    print("请使用这些数据库文件测试导入功能：")
    print(f"1. 旧版本数据库: {os.path.join(test_dir, 'old_version.db')}")
    print(f"2. 同版本数据库: {os.path.join(test_dir, 'same_version.db')}")
    print(f"3. 新版本数据库: {os.path.join(test_dir, 'new_version.db')}")
    print(f"4. 无版本数据库: {os.path.join(test_dir, 'no_version.db')}")
