#!/usr/bin/env python3
"""
NFC UID 컬럼 추가 마이그레이션 스크립트

locker_status 테이블에 nfc_uid TEXT UNIQUE 컬럼을 추가합니다.
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager


def migrate_add_nfc_uid():
    """locker_status 테이블에 nfc_uid 컬럼 추가"""
    
    db_manager = DatabaseManager()
    
    print("=" * 60)
    print("NFC UID 컬럼 추가 마이그레이션")
    print("=" * 60)
    
    # 1. 컬럼 존재 여부 확인
    print("\n1. 현재 locker_status 테이블 구조 확인 중...")
    
    cursor = db_manager.conn.cursor()
    cursor.execute("PRAGMA table_info(locker_status)")
    columns = cursor.fetchall()
    
    column_names = [col[1] for col in columns]
    print(f"   현재 컬럼: {', '.join(column_names)}")
    
    if 'nfc_uid' in column_names:
        print("   ✓ nfc_uid 컬럼이 이미 존재합니다.")
        print("\n마이그레이션이 이미 완료되었습니다.")
        return
    
    # 2. nfc_uid 컬럼 추가
    print("\n2. nfc_uid 컬럼 추가 중...")
    
    try:
        cursor.execute("""
            ALTER TABLE locker_status 
            ADD COLUMN nfc_uid TEXT UNIQUE
        """)
        db_manager.conn.commit()
        print("   ✓ nfc_uid 컬럼 추가 완료")
    except Exception as e:
        print(f"   ✗ 컬럼 추가 실패: {e}")
        db_manager.conn.rollback()
        return
    
    # 3. 결과 확인
    print("\n3. 마이그레이션 결과 확인 중...")
    
    cursor.execute("PRAGMA table_info(locker_status)")
    columns = cursor.fetchall()
    
    column_names = [col[1] for col in columns]
    print(f"   업데이트된 컬럼: {', '.join(column_names)}")
    
    if 'nfc_uid' in column_names:
        print("   ✓ nfc_uid 컬럼이 정상적으로 추가되었습니다.")
    else:
        print("   ✗ nfc_uid 컬럼 추가 실패")
        return
    
    # 4. 락커 개수 확인
    cursor.execute("SELECT COUNT(*) FROM locker_status")
    locker_count = cursor.fetchone()[0]
    print(f"\n4. 총 {locker_count}개 락커에 NFC UID 컬럼이 추가되었습니다.")
    
    # 5. 샘플 데이터 조회
    print("\n5. 샘플 데이터:")
    cursor.execute("""
        SELECT locker_number, zone, nfc_uid 
        FROM locker_status 
        LIMIT 5
    """)
    
    for row in cursor.fetchall():
        locker_number, zone, nfc_uid = row
        nfc_status = nfc_uid if nfc_uid else "(미등록)"
        print(f"   {locker_number} ({zone}): NFC={nfc_status}")
    
    print("\n" + "=" * 60)
    print("✓ 마이그레이션 완료!")
    print("=" * 60)
    print("\n다음 단계:")
    print("  - scripts/setup/register_nfc_tags.py를 실행하여 NFC UID를 등록하세요.")
    print("  - 각 락커키에 NFC 태그를 부착하고 스캔하여 등록합니다.")


if __name__ == "__main__":
    try:
        migrate_add_nfc_uid()
    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

