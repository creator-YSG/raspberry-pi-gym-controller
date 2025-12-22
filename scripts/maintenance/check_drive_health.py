#!/usr/bin/env python3
"""
Google Drive 연결 상태 확인 스크립트

- OAuth 토큰 유효성 검사
- Drive API 연결 테스트
- 토큰 만료 시 자동 알림

사용법:
    python3 scripts/maintenance/check_drive_health.py

크론탭 등록 (매일 오전 9시):
    0 9 * * * cd /home/pi/raspberry-pi-gym-controller && python3 scripts/maintenance/check_drive_health.py >> logs/drive_health.log 2>&1
"""

import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.drive_service import DriveService


def check_drive_health():
    """Google Drive 연결 상태 확인"""
    print("=" * 70)
    print(f"Google Drive 헬스체크 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    drive = DriveService()
    
    # 1. 토큰 파일 존재 확인
    if not drive.token_path.exists():
        print("❌ OAuth 토큰 파일이 없습니다.")
        print(f"   경로: {drive.token_path}")
        print(f"   조치: python3 scripts/setup/oauth_setup.py 실행")
        return False
    
    print(f"✅ 토큰 파일 존재: {drive.token_path}")
    
    # 2. 연결 테스트
    print("\n🔌 Google Drive 연결 시도...")
    success = drive.connect()
    
    if not success:
        print("❌ Google Drive 연결 실패")
        print("   조치 1: 토큰 갱신 시도 (자동)")
        print("   조치 2: 실패 시 수동 재인증 필요")
        print(f"   명령어: python3 scripts/setup/oauth_setup.py")
        return False
    
    print("✅ Google Drive 연결 성공")
    
    # 3. 루트 폴더 접근 테스트
    print("\n📁 루트 폴더 접근 테스트...")
    try:
        folder = drive.service.files().get(
            fileId=drive.ROOT_FOLDER_ID, 
            fields='name,id'
        ).execute()
        print(f"✅ 루트 폴더 접근 성공: {folder['name']}")
    except Exception as e:
        print(f"❌ 루트 폴더 접근 실패: {e}")
        return False
    
    # 4. 업로드 테스트 (선택적)
    print("\n📤 업로드 테스트 (스킵)")
    # 실제 파일 업로드는 하지 않음 (불필요한 트래픽 방지)
    
    print("\n" + "=" * 70)
    print("🎉 모든 테스트 통과!")
    print("=" * 70)
    
    return True


def main():
    try:
        result = check_drive_health()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

