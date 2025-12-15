#!/usr/bin/env python3
"""
Google Drive OAuth 2.0 최초 인증 스크립트

사용법:
    python scripts/setup/oauth_setup.py
    
실행 후:
    - 브라우저가 자동으로 열림
    - Google 계정으로 로그인
    - 권한 승인
    - instance/drive_token.pickle 파일 자동 생성
    
센터별 계정 설정 시:
    1. 센터별 Gmail 계정 생성 (예: gym-center-a@gmail.com)
    2. 이 스크립트 실행
    3. 해당 계정으로 로그인
    4. 생성된 token 파일을 라즈베리파이에 복사
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.drive_service import DriveService


def main():
    print("=" * 70)
    print("Google Drive OAuth 2.0 최초 인증")
    print("=" * 70)
    print()
    print("📌 준비사항:")
    print("   1. OAuth 클라이언트 ID 파일이 프로젝트 루트에 있어야 함")
    print("   2. Google Drive API가 활성화되어 있어야 함")
    print("   3. OAuth 동의 화면에 테스트 사용자가 추가되어 있어야 함")
    print()
    print("🔐 인증 시작...")
    print("-" * 70)
    
    # DriveService 인스턴스 생성
    drive_service = DriveService()
    
    # 연결 시도 (최초 인증 포함)
    if drive_service.connect():
        print()
        print("=" * 70)
        print("✅ OAuth 인증 성공!")
        print("=" * 70)
        print()
        print(f"📁 토큰 저장 위치: {drive_service.token_path}")
        print(f"📂 루트 폴더 ID: {drive_service._root_folder_id}")
        print()
        print("🎉 이제 DriveService를 사용할 수 있습니다!")
        print()
        print("📌 센터별 계정 설정 시:")
        print("   - 이 토큰 파일을 라즈베리파이에 복사")
        print("   - instance/drive_token.pickle")
        print()
        
        # 테스트 업로드
        print("-" * 70)
        print("🧪 테스트 업로드를 진행하시겠습니까? (y/n): ", end="")
        choice = input().strip().lower()
        
        if choice == 'y':
            print()
            print("테스트 이미지 생성 중...")
            
            from PIL import Image
            import numpy as np
            
            # 테스트 이미지 생성
            test_image = np.zeros((480, 640, 3), dtype='uint8')
            test_image[:, :] = [0, 255, 0]  # 초록색
            
            test_dir = project_root / 'instance' / 'photos' / 'test'
            test_dir.mkdir(parents=True, exist_ok=True)
            test_path = test_dir / 'oauth_test.jpg'
            
            img = Image.fromarray(test_image)
            img.save(test_path)
            
            print(f"   저장: {test_path}")
            print()
            print("업로드 중...")
            
            url = drive_service.upload_file(str(test_path), 'test', 'oauth_test.jpg')
            
            if url:
                print()
                print("✅ 업로드 성공!")
                print(f"   URL: {url}")
                print()
                print("🌐 Google Drive에서 확인하세요:")
                print("   https://drive.google.com/drive/my-drive")
            else:
                print()
                print("❌ 업로드 실패")
            
            # 정리
            import os
            os.remove(test_path)
            print()
            print("테스트 파일 삭제 완료")
        
    else:
        print()
        print("=" * 70)
        print("❌ OAuth 인증 실패")
        print("=" * 70)
        print()
        print("문제 해결:")
        print("   1. OAuth 클라이언트 ID 파일 경로 확인")
        print("   2. Google Cloud Console에서 Drive API 활성화 확인")
        print("   3. OAuth 동의 화면 설정 확인")
        print()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

