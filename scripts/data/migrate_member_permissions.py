#!/usr/bin/env python3
"""
회원 테이블에 락커 권한 컬럼 추가 마이그레이션
"""

import sys
import os
import sqlite3
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database_manager import DatabaseManager


def migrate_member_permissions(db_path: str = 'instance/gym_system.db'):
    """회원 테이블에 락커 권한 관련 컬럼 추가"""
    
    print(f"🔄 회원 테이블 마이그레이션 시작: {db_path}")
    
    # 데이터베이스 연결
    db = DatabaseManager(db_path)
    db.connect()
    
    try:
        # 현재 테이블 구조 확인
        cursor = db.execute_query("PRAGMA table_info(members)")
        if cursor:
            columns = [row['name'] for row in cursor.fetchall()]
            print(f"📋 현재 컬럼: {columns}")
            
            # 새 컬럼들이 이미 있는지 확인
            new_columns = ['gender', 'member_category', 'customer_type']
            missing_columns = [col for col in new_columns if col not in columns]
            
            if not missing_columns:
                print("✅ 모든 컬럼이 이미 존재합니다. 마이그레이션이 필요하지 않습니다.")
                return
            
            print(f"➕ 추가할 컬럼: {missing_columns}")
            
            # 각 컬럼 추가
            for column in missing_columns:
                if column == 'gender':
                    db.execute_query("ALTER TABLE members ADD COLUMN gender TEXT DEFAULT 'male'")
                    print("   ✅ gender 컬럼 추가됨")
                elif column == 'member_category':
                    db.execute_query("ALTER TABLE members ADD COLUMN member_category TEXT DEFAULT 'general'")
                    print("   ✅ member_category 컬럼 추가됨")
                elif column == 'customer_type':
                    db.execute_query("ALTER TABLE members ADD COLUMN customer_type TEXT DEFAULT '학부'")
                    print("   ✅ customer_type 컬럼 추가됨")
            
            # 마이그레이션 완료 후 테이블 구조 재확인
            cursor = db.execute_query("PRAGMA table_info(members)")
            if cursor:
                updated_columns = [row['name'] for row in cursor.fetchall()]
                print(f"📋 업데이트된 컬럼: {updated_columns}")
            
            print("✅ 회원 테이블 마이그레이션 완료!")
            
        else:
            print("❌ 회원 테이블 정보를 가져올 수 없습니다.")
            
    except Exception as e:
        print(f"❌ 마이그레이션 오류: {e}")
    finally:
        db.close()


def main():
    """메인 함수"""
    db_path = 'instance/gym_system.db'
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        sys.exit(1)
    
    migrate_member_permissions(db_path)


if __name__ == "__main__":
    main()
