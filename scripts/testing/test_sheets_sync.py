#!/usr/bin/env python3
"""
Google Sheets 동기화 테스트

DB 데이터를 구글 시트에 업로드하고 확인합니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import DatabaseManager
from app.services.sheets_sync import SheetsSync


def test_connection():
    """연결 테스트"""
    print("=" * 50)
    print("🔗 Google Sheets 연결 테스트")
    print("=" * 50)
    
    sync = SheetsSync()
    
    if sync.connect():
        print("✅ 연결 성공!")
        print(f"   스프레드시트: {sync.spreadsheet.title}")
        print(f"   시트 목록: {[ws.title for ws in sync.spreadsheet.worksheets()]}")
        return sync
    else:
        print("❌ 연결 실패")
        return None


def test_upload_lockers(sync: SheetsSync, db: DatabaseManager):
    """락카 현황 업로드 테스트"""
    print("\n" + "=" * 50)
    print("📤 락카 현황 업로드 테스트")
    print("=" * 50)
    
    # DB에서 락카 수 확인
    cursor = db.execute_query("SELECT COUNT(*) as cnt FROM locker_status")
    if cursor:
        count = cursor.fetchone()['cnt']
        print(f"📊 DB 락카 수: {count}개")
    
    # 업로드
    uploaded = sync.upload_locker_status(db)
    print(f"✅ 업로드 완료: {uploaded}개")


def test_upload_rentals(sync: SheetsSync, db: DatabaseManager):
    """대여 기록 업로드 테스트"""
    print("\n" + "=" * 50)
    print("📤 대여 기록 업로드 테스트")
    print("=" * 50)
    
    # DB에서 대여 기록 수 확인
    cursor = db.execute_query("SELECT COUNT(*) as cnt FROM rentals WHERE sync_status = 0")
    if cursor:
        count = cursor.fetchone()['cnt']
        print(f"📊 미동기화 대여 기록: {count}건")
    
    # 업로드
    uploaded = sync.upload_rentals(db)
    print(f"✅ 업로드 완료: {uploaded}건")


def test_upload_sensor_events(sync: SheetsSync, db: DatabaseManager):
    """센서 이벤트 업로드 테스트"""
    print("\n" + "=" * 50)
    print("📤 센서 이벤트 업로드 테스트")
    print("=" * 50)
    
    # DB에서 센서 이벤트 수 확인
    cursor = db.execute_query("SELECT COUNT(*) as cnt FROM sensor_events")
    if cursor:
        count = cursor.fetchone()['cnt']
        print(f"📊 DB 센서 이벤트: {count}건")
    
    # 업로드
    uploaded = sync.upload_sensor_events(db)
    print(f"✅ 업로드 완료: {uploaded}건")


def test_download_members(sync: SheetsSync, db: DatabaseManager):
    """회원 정보 다운로드 테스트"""
    print("\n" + "=" * 50)
    print("📥 회원 정보 다운로드 테스트")
    print("=" * 50)
    
    # 현재 DB 회원 수
    cursor = db.execute_query("SELECT COUNT(*) as cnt FROM members")
    if cursor:
        count = cursor.fetchone()['cnt']
        print(f"📊 현재 DB 회원 수: {count}명")
    
    # 다운로드
    downloaded = sync.download_members(db)
    print(f"✅ 다운로드 완료: {downloaded}명")


def test_full_sync(sync: SheetsSync, db: DatabaseManager):
    """전체 동기화 테스트"""
    print("\n" + "=" * 50)
    print("🔄 전체 동기화 테스트")
    print("=" * 50)
    
    # 다운로드
    print("\n📥 다운로드...")
    download_result = sync.sync_all_downloads(db)
    print(f"   결과: {download_result}")
    
    # 업로드
    print("\n📤 업로드...")
    upload_result = sync.sync_all_uploads(db)
    print(f"   결과: {upload_result}")
    
    print("\n✅ 전체 동기화 완료!")


def main():
    print("🔧 Google Sheets 동기화 테스트")
    print("=" * 50)
    
    # DB 연결
    db_path = PROJECT_ROOT / "instance" / "gym_system.db"
    print(f"📁 DB 경로: {db_path}")
    
    db = DatabaseManager(str(db_path))
    db.connect()
    
    # Sheets 연결 테스트
    sync = test_connection()
    if not sync:
        return
    
    # 메뉴
    print("\n" + "=" * 50)
    print("테스트 옵션:")
    print("  1. 락카 현황 업로드")
    print("  2. 대여 기록 업로드")
    print("  3. 센서 이벤트 업로드")
    print("  4. 회원 정보 다운로드")
    print("  5. 전체 동기화")
    print("  q. 종료")
    print("=" * 50)
    
    while True:
        choice = input("\n선택 (1-5, q): ").strip()
        
        if choice == '1':
            test_upload_lockers(sync, db)
        elif choice == '2':
            test_upload_rentals(sync, db)
        elif choice == '3':
            test_upload_sensor_events(sync, db)
        elif choice == '4':
            test_download_members(sync, db)
        elif choice == '5':
            test_full_sync(sync, db)
        elif choice == 'q':
            print("\n👋 종료")
            break
        else:
            print("❓ 잘못된 선택")
    
    db.close()


if __name__ == "__main__":
    main()

