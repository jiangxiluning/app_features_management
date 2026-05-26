#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本
用于安全地升级数据库结构
"""

import os
import sys
import shutil
from datetime import datetime

# 添加当前目录到路径，以便导入app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db, SchemaVersion
except ImportError as e:
    print(f"导入app失败: {e}")
    print("请确保在backend目录下运行此脚本")
    sys.exit(1)


def backup_database():
    """备份现有数据库"""
    print("\n=== 开始备份数据库 ===")
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'app_knowledge.db')
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过备份")
        return None
    
    # 创建备份目录
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # 生成备份文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'app_knowledge_{timestamp}.db')
    
    # 复制数据库文件
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ 数据库已备份到: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ 数据库备份失败: {e}")
        return None


def check_current_version():
    """检查当前数据库版本"""
    print("\n=== 检查数据库版本 ===")
    try:
        current_version = SchemaVersion.query.order_by(SchemaVersion.id.desc()).first()
        if current_version:
            print(f"当前数据库版本: {current_version.version}")
            return current_version.version
        else:
            print("数据库版本未记录")
            return None
    except Exception as e:
        print(f"检查版本失败: {e}")
        return None


def migrate_to_1_1_0():
    """迁移到版本1.1.0 - 添加大模型配置表"""
    print("\n=== 开始迁移到版本1.1.0 ===")
    
    try:
        # 首先创建所有新表（包括llm_config）
        # 注意：db.create_all()只会创建不存在的表，不会修改现有表
        print("创建新表结构...")
        db.create_all()
        
        # 检查llm_config表是否创建成功
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'llm_config' not in tables:
            raise Exception("llm_config表创建失败")
        
        print("✅ llm_config表创建成功")
        
        # 更新schema版本
        print("更新数据库版本记录...")
        new_version = SchemaVersion(version='1.1.0')
        db.session.add(new_version)
        db.session.commit()
        
        print("✅ 数据库版本已更新为 1.1.0")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_migration():
    """验证迁移结果"""
    print("\n=== 验证迁移结果 ===")
    
    try:
        # 1. 检查llm_config表是否存在
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'llm_config' not in tables:
            print("❌ llm_config表不存在")
            return False
        
        print("✅ llm_config表存在")
        
        # 2. 检查现有表是否完整
        existing_tables = ['user', 'feature', 'device', 'audit_log', 'app_version', 'schema_version']
        for table in existing_tables:
            if table not in tables:
                print(f"❌ 现有表 {table} 丢失")
                return False
        
        print("✅ 所有现有表完整")
        
        # 3. 检查版本记录
        current_version = SchemaVersion.query.order_by(SchemaVersion.id.desc()).first()
        if not current_version or current_version.version != '1.1.0':
            print(f"❌ 版本记录不正确: {current_version.version if current_version else 'None'}")
            return False
        
        print("✅ 版本记录正确")
        
        print("\n✅ 迁移验证通过！")
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def rollback(backup_path):
    """回滚到备份"""
    print("\n=== 开始回滚 ===")
    
    if not backup_path:
        print("❌ 没有可用的备份文件")
        return False
    
    if not os.path.exists(backup_path):
        print(f"❌ 备份文件不存在: {backup_path}")
        return False
    
    try:
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'app_knowledge.db')
        shutil.copy2(backup_path, db_path)
        print(f"✅ 已从备份恢复: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ 回滚失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("   数据库迁移工具")
    print("=" * 50)
    
    backup_path = None
    success = False
    
    try:
        with app.app_context():
            # 检查当前版本
            current_version = check_current_version()
            
            # 检查是否需要迁移
            if current_version and current_version >= '1.1.0':
                print("\n✅ 数据库已是最新版本，无需迁移")
                return
            
            # 询问用户是否继续
            print("\n准备将数据库迁移到版本 1.1.0")
            print("此操作将：")
            print("  1. 自动备份当前数据库")
            print("  2. 创建新的llm_config表")
            print("  3. 更新数据库版本记录")
            print("  4. 验证迁移结果")
            print("\n⚠️  注意：不会修改任何现有表结构和数据")
            
            response = input("\n是否继续？(y/n): ").strip().lower()
            if response != 'y':
                print("用户取消迁移")
                return
            
            # 备份数据库
            backup_path = backup_database()
            
            # 执行迁移
            if migrate_to_1_1_0():
                # 验证迁移
                if verify_migration():
                    success = True
                    print("\n" + "=" * 50)
                    print("✅ 数据库迁移成功完成！")
                    print("=" * 50)
                else:
                    print("\n❌ 迁移验证失败")
                    if backup_path:
                        print("正在尝试回滚...")
                        rollback(backup_path)
            else:
                print("\n❌ 迁移执行失败")
                if backup_path:
                    print("正在尝试回滚...")
                    rollback(backup_path)
    
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        if backup_path:
            print(f"备份文件已保留: {backup_path}")
    except Exception as e:
        print(f"\n❌ 迁移过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        if backup_path:
            print(f"\n备份文件已保留: {backup_path}")
            response = input("是否尝试回滚？(y/n): ").strip().lower()
            if response == 'y':
                rollback(backup_path)
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
