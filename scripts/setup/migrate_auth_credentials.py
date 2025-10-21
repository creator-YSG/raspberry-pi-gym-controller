#!/usr/bin/env python3
"""
회원 인증 정보 분리 마이그레이션 스크립트
- member_id와 barcode/qr_code를 분리
- 기존 member_id를 barcode로 복사
"""

import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def backup_database(db_path):
    """데이터베이스 백업"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = PROJECT_ROOT / "data" / "backups" / "database"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_path = backup_dir / f"pre_auth_migration_{timestamp}.db"
    
    # 백업 수행
    import shutil
    shutil.copy2(db_path, backup_path)
    
    print(f"✅ 데이터베이스 백업 완료: {backup_path}")
    return backup_path


def migrate_members_table(conn, cursor):
    """members 테이블 마이그레이션"""
    
    print("\n" + "="*60)
    print("📊 members 테이블 마이그레이션 시작")
    print("="*60)
    
    # 1. 기존 데이터 확인
    cursor.execute("SELECT COUNT(*) FROM members")
    total_members = cursor.fetchone()[0]
    print(f"📌 기존 회원 수: {total_members}명")
    
    # 2. 임시 테이블 생성 (새 스키마)
    print("\n🔧 임시 테이블 생성 중...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS members_new (
            member_id TEXT PRIMARY KEY,
            barcode TEXT UNIQUE,
            qr_code TEXT UNIQUE,
            member_name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            membership_type TEXT DEFAULT 'basic',
            program_name TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            expiry_date DATE,
            currently_renting TEXT,
            daily_rental_count INTEGER DEFAULT 0,
            last_rental_time TIMESTAMP,
            sync_date TIMESTAMP,
            gender TEXT DEFAULT 'male',
            member_category TEXT DEFAULT 'general',
            customer_type TEXT DEFAULT '학부',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. 데이터 복사 (member_id를 barcode에도 복사)
    print("📦 데이터 복사 중 (member_id → barcode)...")
    cursor.execute("""
        INSERT INTO members_new (
            member_id, barcode, qr_code,
            member_name, phone, membership_type, program_name,
            status, expiry_date, currently_renting,
            daily_rental_count, last_rental_time, sync_date,
            gender, member_category, customer_type,
            created_at, updated_at
        )
        SELECT 
            member_id, member_id AS barcode, NULL AS qr_code,
            member_name, phone, membership_type, program_name,
            status, expiry_date, currently_renting,
            daily_rental_count, last_rental_time, sync_date,
            gender, member_category, customer_type,
            created_at, updated_at
        FROM members
    """)
    
    copied_count = cursor.rowcount
    print(f"✅ {copied_count}명 데이터 복사 완료")
    
    # 4. 기존 테이블 삭제
    print("\n🗑️  기존 테이블 삭제 중...")
    cursor.execute("DROP TABLE members")
    
    # 5. 임시 테이블 이름 변경
    print("🔄 임시 테이블 → members 로 변경 중...")
    cursor.execute("ALTER TABLE members_new RENAME TO members")
    
    # 6. 인덱스 재생성
    print("\n🔍 인덱스 재생성 중...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_barcode ON members(barcode)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_qr_code ON members(qr_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_status ON members(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_currently_renting ON members(currently_renting)")
    print("✅ 인덱스 생성 완료")
    
    # 7. 트리거 재생성
    print("\n⚡ 트리거 재생성 중...")
    cursor.execute("DROP TRIGGER IF EXISTS update_members_timestamp")
    cursor.execute("""
        CREATE TRIGGER update_members_timestamp 
            AFTER UPDATE ON members
            FOR EACH ROW
        BEGIN
            UPDATE members SET updated_at = CURRENT_TIMESTAMP WHERE member_id = NEW.member_id;
        END
    """)
    print("✅ 트리거 생성 완료")
    
    # 8. 검증
    print("\n🔍 마이그레이션 검증 중...")
    cursor.execute("SELECT COUNT(*) FROM members")
    new_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM members WHERE barcode IS NOT NULL")
    barcode_count = cursor.fetchone()[0]
    
    print(f"  - 전체 회원 수: {new_count}명")
    print(f"  - barcode 설정된 회원: {barcode_count}명")
    
    if new_count == total_members and barcode_count == total_members:
        print("✅ 마이그레이션 검증 성공!")
        return True
    else:
        print("❌ 마이그레이션 검증 실패!")
        return False


def show_sample_data(cursor):
    """샘플 데이터 확인"""
    print("\n" + "="*60)
    print("📋 샘플 데이터 확인 (상위 5명)")
    print("="*60)
    
    cursor.execute("""
        SELECT member_id, barcode, qr_code, member_name, status
        FROM members
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    for row in rows:
        member_id, barcode, qr_code, name, status = row
        qr_display = qr_code if qr_code else "(없음)"
        print(f"  회원ID: {member_id} | 바코드: {barcode} | QR: {qr_display} | 이름: {name} | 상태: {status}")


def main():
    """메인 실행 함수"""
    print("\n" + "="*80)
    print("🔄 회원 인증 정보 분리 마이그레이션")
    print("="*80)
    
    # 데이터베이스 경로 확인
    db_path = PROJECT_ROOT / "instance" / "gym_system.db"
    
    if not db_path.exists():
        print(f"❌ 데이터베이스를 찾을 수 없습니다: {db_path}")
        sys.exit(1)
    
    print(f"📂 데이터베이스: {db_path}")
    
    # 백업 생성
    backup_path = backup_database(db_path)
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # WAL 모드 체크포인트
        print("\n📝 WAL 모드 체크포인트...")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        # 마이그레이션 실행
        success = migrate_members_table(conn, cursor)
        
        if success:
            # 커밋
            conn.commit()
            print("\n✅ 트랜잭션 커밋 완료")
            
            # 샘플 데이터 확인
            show_sample_data(cursor)
            
            print("\n" + "="*80)
            print("✅ 마이그레이션 완료!")
            print("="*80)
            print(f"\n💾 백업 파일: {backup_path}")
            print("\n⚠️  다음 단계:")
            print("  1. 애플리케이션 코드 수정 (barcode로 회원 조회)")
            print("  2. 라즈베리파이에도 동일한 마이그레이션 실행")
            print("  3. 전체 시스템 테스트")
            
        else:
            conn.rollback()
            print("\n❌ 마이그레이션 실패! 롤백되었습니다.")
            print(f"💾 백업에서 복구 가능: {backup_path}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        conn.rollback()
        print(f"💾 백업에서 복구 가능: {backup_path}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    # 확인 메시지
    print("\n⚠️  경고: 이 스크립트는 데이터베이스 구조를 변경합니다.")
    print("자동으로 백업이 생성되지만, 중요한 데이터는 별도로 백업하세요.")
    
    response = input("\n계속하시겠습니까? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        main()
    else:
        print("❌ 마이그레이션 취소됨")
        sys.exit(0)

