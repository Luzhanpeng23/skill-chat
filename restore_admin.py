#!/usr/bin/env python3
"""
恢复管理员权限的脚本
用法：python restore_admin.py <邮箱地址>
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "app.db"

def restore_admin(email: str) -> bool:
    """恢复指定用户的管理员权限"""
    if not DB_PATH.exists():
        print(f"错误：数据库文件不存在: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # 查找用户
        user = conn.execute(
            "SELECT id, email, is_admin, status FROM users WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()
        
        if not user:
            print(f"错误：未找到邮箱为 {email} 的用户")
            return False
        
        print(f"找到用户: {user['email']}")
        print(f"用户ID: {user['id']}")
        print(f"当前管理员状态: {'是' if user['is_admin'] else '否'}")
        print(f"账户状态: {user['status']}")
        
        if user['is_admin']:
            print("该用户已经是管理员，无需恢复")
            return True
        
        # 恢复管理员权限
        conn.execute(
            "UPDATE users SET is_admin = 1, updated_at = datetime('now') WHERE id = ?",
            (user['id'],)
        )
        conn.commit()
        
        # 验证更新
        updated_user = conn.execute(
            "SELECT is_admin FROM users WHERE id = ?",
            (user['id'],)
        ).fetchone()
        
        if updated_user and updated_user['is_admin']:
            print("✓ 管理员权限已成功恢复！")
            return True
        else:
            print("✗ 恢复管理员权限失败")
            return False
            
    except Exception as e:
        print(f"错误: {e}")
        return False
    finally:
        conn.close()

def list_users():
    """列出所有用户"""
    if not DB_PATH.exists():
        print(f"错误：数据库文件不存在: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        users = conn.execute(
            "SELECT id, email, is_admin, status, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        
        if not users:
            print("数据库中没有用户")
            return
        
        print("\n当前用户列表:")
        print("-" * 80)
        print(f"{'邮箱':<30} {'管理员':<8} {'状态':<10} {'注册时间':<20}")
        print("-" * 80)
        
        for user in users:
            admin_status = "是" if user['is_admin'] else "否"
            print(f"{user['email']:<30} {admin_status:<8} {user['status']:<10} {user['created_at']:<20}")
        
        print("-" * 80)
        print(f"共 {len(users)} 个用户")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        conn.close()

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python restore_admin.py <邮箱地址>    # 恢复指定用户的管理员权限")
        print("  python restore_admin.py --list        # 列出所有用户")
        print("\n示例:")
        print("  python restore_admin.py admin@example.com")
        return
    
    if sys.argv[1] == "--list":
        list_users()
        return
    
    email = sys.argv[1]
    restore_admin(email)

if __name__ == "__main__":
    main()