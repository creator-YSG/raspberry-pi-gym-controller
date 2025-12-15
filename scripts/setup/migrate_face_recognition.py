#!/usr/bin/env python3
"""
얼굴인식 관련 컬럼 추가 마이그레이션 스크립트

members 테이블:
  - face_embedding BLOB (pickle 직렬화된 임베딩 벡터)
  - face_photo_path TEXT (등록된 얼굴 사진 경로)
  - face_registered_at TIMESTAMP
  - face_enabled INTEGER DEFAULT 0

rentals 테이블:
  - auth_method TEXT DEFAULT 'barcode' (barcode, qr, nfc, face)
  - rental_photo_path TEXT (인증 시 촬영된 사진 경로)
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager


def get_column_names(cursor, table_name: str) -> list:
    """테이블의 컬럼 이름 목록 반환"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return [col[1] for col in columns]


def add_column_if_not_exists(cursor, table_name: str, column_name: str, 
                              column_def: str, column_names: list) -> bool:
    """컬럼이 없으면 추가"""
    if column_name in column_names:
        print(f"   ✓ {column_name} 컬럼이 이미 존재합니다.")
        return False
    
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        print(f"   ✓ {column_name} 컬럼 추가 완료")
        return True
    except Exception as e:
        print(f"   ✗ {column_name} 컬럼 추가 실패: {e}")
        return False


def migrate_face_recognition():
    """얼굴인식 관련 컬럼 추가"""
    
    db_manager = DatabaseManager()
    db_manager.connect()
    cursor = db_manager.conn.cursor()
    
    print("=" * 60)
    print("얼굴인식 기능 마이그레이션")
    print("=" * 60)
    
    changes_made = False
    
    # =====================================================
    # 1. members 테이블 마이그레이션
    # =====================================================
    print("\n[1/2] members 테이블 마이그레이션")
    print("-" * 40)
    
    member_columns = get_column_names(cursor, 'members')
    print(f"현재 컬럼: {len(member_columns)}개")
    
    # 얼굴인식 관련 컬럼 추가
    member_new_columns = [
        ('face_embedding', 'BLOB'),
        ('face_photo_path', 'TEXT'),
        ('face_photo_url', 'TEXT'),
        ('face_registered_at', 'TIMESTAMP'),
        ('face_enabled', 'INTEGER DEFAULT 0'),
    ]
    
    for col_name, col_def in member_new_columns:
        if add_column_if_not_exists(cursor, 'members', col_name, col_def, member_columns):
            changes_made = True
    
    # =====================================================
    # 2. rentals 테이블 마이그레이션
    # =====================================================
    print("\n[2/2] rentals 테이블 마이그레이션")
    print("-" * 40)
    
    rental_columns = get_column_names(cursor, 'rentals')
    print(f"현재 컬럼: {len(rental_columns)}개")
    
    # 인증 방법 및 사진 관련 컬럼 추가
    rental_new_columns = [
        ('auth_method', "TEXT DEFAULT 'barcode'"),
        ('rental_photo_path', 'TEXT'),
        ('rental_photo_url', 'TEXT'),
    ]
    
    for col_name, col_def in rental_new_columns:
        if add_column_if_not_exists(cursor, 'rentals', col_name, col_def, rental_columns):
            changes_made = True
    
    # =====================================================
    # 3. 변경사항 커밋
    # =====================================================
    if changes_made:
        db_manager.conn.commit()
        print("\n변경사항이 저장되었습니다.")
    else:
        print("\n변경할 사항이 없습니다. 이미 마이그레이션되었습니다.")
    
    # =====================================================
    # 4. 결과 확인
    # =====================================================
    print("\n" + "=" * 60)
    print("마이그레이션 결과")
    print("=" * 60)
    
    # members 테이블 최종 구조
    print("\n[members 테이블]")
    member_columns_final = get_column_names(cursor, 'members')
    face_columns = [c for c in member_columns_final if c.startswith('face_')]
    print(f"  얼굴인식 관련 컬럼: {', '.join(face_columns)}")
    
    # rentals 테이블 최종 구조
    print("\n[rentals 테이블]")
    rental_columns_final = get_column_names(cursor, 'rentals')
    new_columns = [c for c in rental_columns_final if c in ['auth_method', 'rental_photo_path']]
    print(f"  새로 추가된 컬럼: {', '.join(new_columns)}")
    
    # =====================================================
    # 5. 사진 저장 디렉토리 생성
    # =====================================================
    print("\n" + "=" * 60)
    print("사진 저장 디렉토리 생성")
    print("=" * 60)
    
    photo_dirs = [
        project_root / 'instance' / 'photos' / 'faces',
        project_root / 'instance' / 'photos' / 'rentals',
    ]
    
    for photo_dir in photo_dirs:
        photo_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {photo_dir.relative_to(project_root)}")
    
    # =====================================================
    # 6. 완료 메시지
    # =====================================================
    print("\n" + "=" * 60)
    print("✓ 마이그레이션 완료!")
    print("=" * 60)
    print("\n다음 단계:")
    print("  1. 의존성 설치: pip install mediapipe opencv-python")
    print("  2. 라즈베리파이: pip install picamera2")
    print("  3. 얼굴 등록 테스트: curl -X POST http://localhost:5001/api/face/register/<member_id>")


if __name__ == "__main__":
    try:
        migrate_face_recognition()
    except Exception as e:
        print(f"\n❌ 마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

