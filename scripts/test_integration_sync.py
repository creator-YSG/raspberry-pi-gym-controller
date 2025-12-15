#!/usr/bin/env python3
"""
System_Integration 시트 동기화 테스트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.integration_sync import IntegrationSync

def main():
    """테스트 실행"""
    print("=" * 60)
    print("System_Integration 시트 동기화 테스트")
    print("=" * 60)
    
    # IntegrationSync 인스턴스 생성
    sync = IntegrationSync()
    
    # 1. 연결 테스트
    print("\n[1단계] 구글 시트 연결...")
    if not sync.connect():
        print("❌ 연결 실패")
        return
    
    print(f"✅ 연결 성공: {sync.spreadsheet.title}")
    
    # 2. 헤더 초기화
    print("\n[2단계] 헤더 초기화...")
    if sync.initialize_sheet_headers():
        print("✅ 헤더 작성 완료")
    else:
        print("❌ 헤더 작성 실패")
        return
    
    # 3. IP 업로드
    print("\n[3단계] 락카키 대여기 IP 업로드...")
    ip = sync.get_local_ip()
    print(f"   감지된 IP: {ip}")
    
    if sync.upload_locker_api_info():
        print("✅ IP 업로드 완료")
    else:
        print("❌ IP 업로드 실패")
        return
    
    # 4. 다운로드 테스트
    print("\n[4단계] IP 다운로드 테스트...")
    info = sync.download_locker_api_info()
    print(f"   다운로드된 URL: {info['url']}")
    print(f"   상태: {info['status']}")
    print(f"   마지막 업데이트: {info.get('last_updated', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("✅ 모든 테스트 완료!")
    print("=" * 60)
    print(f"\n시트 URL: https://docs.google.com/spreadsheets/d/{sync.INTEGRATION_SHEET_ID}/edit")


if __name__ == '__main__':
    main()

