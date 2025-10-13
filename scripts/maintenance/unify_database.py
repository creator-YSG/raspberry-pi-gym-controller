#!/usr/bin/env python3
"""
데이터베이스 파일 통일 스크립트
모든 데이터베이스 파일을 instance/gym_system.db로 통일합니다.
"""

import sys
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def backup_old_files():
    """기존 파일들을 백업"""
    backup_dir = Path('backups')
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 기존 locker.db 백업
    if Path('locker.db').exists():
        backup_path = backup_dir / f'locker_old_{timestamp}.db'
        shutil.copy('locker.db', backup_path)
        print(f"📦 기존 locker.db 백업: {backup_path}")
    
    # 기존 백업 파일들 정리
    backup_files = list(Path('.').glob('locker_backup_*.db'))
    if backup_files:
        for backup_file in backup_files:
            new_path = backup_dir / backup_file.name
            shutil.move(backup_file, new_path)
            print(f"📦 백업 파일 이동: {new_path}")


def update_all_python_files():
    """모든 Python 파일에서 데이터베이스 경로를 통일"""
    
    # 변경할 파일들과 패턴
    files_to_update = [
        'app/services/locker_service.py',
        'app/services/member_service.py', 
        'app/services/sensor_event_handler.py',
        'app/api/routes.py',
        'scripts/test_locker_permissions.py',
        'scripts/update_member_permissions.py',
        'scripts/migrate_member_permissions.py',
        'scripts/setup_lockers.py',
        'scripts/fix_data_inconsistency.py',
        'scripts/import_members_csv.py',
        'scripts/test_api_direct.py',
        'scripts/test_server.py',
        'scripts/test_sensor_event_direct.py',
        'scripts/test_complete_flow.py',
        'scripts/test_locker_service.py',
        'scripts/add_test_members.py',
        'scripts/init_database.py',
        'database/database_manager.py'
    ]
    
    # 교체할 패턴들
    replacements = [
        ("'locker.db'", "'instance/gym_system.db'"),
        ('"locker.db"', '"instance/gym_system.db"'),
        ("db_path: str = 'locker.db'", "db_path: str = 'instance/gym_system.db'"),
        ("db_path='locker.db'", "db_path='instance/gym_system.db'"),
        ('db_path="locker.db"', 'db_path="instance/gym_system.db"'),
        ("DatabaseManager('locker.db')", "DatabaseManager('instance/gym_system.db')"),
        ('DatabaseManager("locker.db")', 'DatabaseManager("instance/gym_system.db")'),
        ("LockerService('locker.db')", "LockerService('instance/gym_system.db')"),
        ('LockerService("locker.db")', 'LockerService("instance/gym_system.db")'),
        ("MemberService('locker.db')", "MemberService('instance/gym_system.db')"),
        ('MemberService("locker.db")', 'MemberService("instance/gym_system.db")'),
    ]
    
    updated_files = []
    
    for file_path in files_to_update:
        if not Path(file_path).exists():
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # 모든 교체 패턴 적용
            for old_pattern, new_pattern in replacements:
                content = content.replace(old_pattern, new_pattern)
            
            # 변경사항이 있으면 파일 업데이트
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                updated_files.append(file_path)
                print(f"✅ 업데이트: {file_path}")
        
        except Exception as e:
            print(f"❌ 오류 ({file_path}): {e}")
    
    return updated_files


def clean_old_database_files():
    """오래된 데이터베이스 파일들 정리"""
    
    # 삭제할 파일들
    files_to_remove = [
        'locker.db',
        'locker.db-shm', 
        'locker.db-wal'
    ]
    
    removed_files = []
    
    for file_path in files_to_remove:
        if Path(file_path).exists():
            os.remove(file_path)
            removed_files.append(file_path)
            print(f"🗑️  삭제: {file_path}")
    
    return removed_files


def verify_database():
    """통일된 데이터베이스 검증"""
    db_path = 'instance/gym_system.db'
    
    if not Path(db_path).exists():
        print(f"❌ 데이터베이스 파일이 없습니다: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['members', 'locker_status', 'rentals', 'active_transactions', 'system_settings']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ 누락된 테이블: {missing_tables}")
            return False
        
        # 회원 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM members")
        member_count = cursor.fetchone()[0]
        
        # 락커 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM locker_status")
        locker_count = cursor.fetchone()[0]
        
        print(f"✅ 데이터베이스 검증 완료:")
        print(f"   📊 회원 수: {member_count}명")
        print(f"   🔐 락커 수: {locker_count}개")
        print(f"   📋 테이블: {len(tables)}개")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 데이터베이스 검증 오류: {e}")
        return False


def main():
    """메인 함수"""
    print("🔄 데이터베이스 파일 통일 작업 시작")
    print("=" * 50)
    
    # 1. 기존 파일들 백업
    print("\n1️⃣ 기존 파일 백업...")
    backup_old_files()
    
    # 2. Python 파일들 업데이트
    print("\n2️⃣ Python 파일 경로 업데이트...")
    updated_files = update_all_python_files()
    print(f"   📝 업데이트된 파일: {len(updated_files)}개")
    
    # 3. 오래된 데이터베이스 파일 정리
    print("\n3️⃣ 오래된 파일 정리...")
    removed_files = clean_old_database_files()
    print(f"   🗑️  삭제된 파일: {len(removed_files)}개")
    
    # 4. 데이터베이스 검증
    print("\n4️⃣ 데이터베이스 검증...")
    if verify_database():
        print("\n✅ 데이터베이스 통일 작업 완료!")
        print(f"📍 통일된 데이터베이스: instance/gym_system.db")
        print("\n🎯 이제 모든 시스템이 하나의 데이터베이스를 사용합니다.")
    else:
        print("\n❌ 데이터베이스 검증 실패!")
        return 1
    
    print("\n" + "=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
