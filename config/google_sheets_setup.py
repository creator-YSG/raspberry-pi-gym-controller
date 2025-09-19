#!/usr/bin/env python3
"""
구글시트 설정 파일 생성 및 인증 파일 설정

기존 gym-entry-locker-system의 설정을 활용하여 
현재 프로젝트에 맞게 구글시트 연동을 설정
"""

import json
import os
import shutil
from pathlib import Path

# 프로젝트 경로
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_DIR.mkdir(exist_ok=True)

# 기존 프로젝트 경로
OLD_PROJECT_PATH = Path("/Users/yunseong-geun/Projects/gym-entry-locker-system")

def copy_google_credentials():
    """기존 프로젝트에서 구글 인증 파일 복사"""
    print("🔍 기존 구글 인증 파일 찾는 중...")
    
    # 가능한 인증 파일 위치들
    possible_paths = [
        OLD_PROJECT_PATH / "gym-entry-locker-system-b903a78609d9.json",
        OLD_PROJECT_PATH / "gym_agent" / "gym-entry-locker-system-b903a78609d9.json",
        OLD_PROJECT_PATH / "config" / "gym-entry-locker-system-b903a78609d9.json",
    ]
    
    for auth_file in possible_paths:
        if auth_file.exists():
            target_file = CONFIG_DIR / "google_credentials.json"
            shutil.copy(auth_file, target_file)
            print(f"✅ 인증 파일 복사 완료: {auth_file} -> {target_file}")
            return True
    
    print("❌ 기존 인증 파일을 찾을 수 없습니다")
    return False

def create_sheets_config():
    """구글시트 설정 파일 생성"""
    config = {
        "spreadsheet_id": "11oFMFby5stYSve8WGrdTL__jyp6mFuyZbo-Iv8mnHvc",
        "credentials_file": "google_credentials.json",
        "sheet_names": {
            "members": "회원명단",
            "lockers": "락카정보",
            "rentals": "대여기록",
            "keys": "락카키목록",
            "logs": "시스템로그"
        },
        "sync_settings": {
            "auto_sync": True,
            "sync_interval_sec": 300,
            "cache_timeout_sec": 300,
            "offline_mode": True
        }
    }
    
    config_file = CONFIG_DIR / "google_sheets_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 구글시트 설정 파일 생성: {config_file}")
    return config

def create_env_file():
    """실제 .env 파일 생성"""
    template_file = CONFIG_DIR / "config.env.template"
    env_file = PROJECT_ROOT / ".env"
    
    if template_file.exists():
        shutil.copy(template_file, env_file)
        print(f"✅ 환경 설정 파일 생성: {env_file}")
        print("📝 필요에 따라 .env 파일을 수정하세요")
        return True
    else:
        print("❌ 템플릿 파일이 없습니다")
        return False

def test_google_sheets_connection():
    """구글시트 연결 테스트"""
    print("\n🔍 구글시트 연결 테스트 중...")
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        credentials_file = CONFIG_DIR / "google_credentials.json"
        if not credentials_file.exists():
            print("❌ 인증 파일이 없습니다")
            return False
        
        # 인증
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_file(
            credentials_file, scopes=scope
        )
        
        client = gspread.authorize(credentials)
        
        # 시트 열기
        sheet_id = "11oFMFby5stYSve8WGrdTL__jyp6mFuyZbo-Iv8mnHvc"
        spreadsheet = client.open_by_key(sheet_id)
        
        print(f"✅ 구글시트 연결 성공!")
        print(f"📊 시트 이름: {spreadsheet.title}")
        print(f"📄 워크시트 수: {len(spreadsheet.worksheets())}")
        
        # 워크시트 목록
        print("📋 워크시트 목록:")
        for ws in spreadsheet.worksheets():
            print(f"  • {ws.title} ({ws.row_count}행 × {ws.col_count}열)")
        
        return True
        
    except ImportError:
        print("❌ 필요한 라이브러리가 설치되지 않았습니다")
        print("🔧 다음 명령어로 설치하세요:")
        print("   pip install gspread google-auth google-auth-oauthlib google-auth-httplib2")
        return False
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return False

def main():
    print("🔗 구글시트 연동 설정 시작")
    print("=" * 50)
    
    # 1. 인증 파일 복사
    auth_copied = copy_google_credentials()
    
    # 2. 설정 파일 생성
    config = create_sheets_config()
    
    # 3. 환경 파일 생성
    env_created = create_env_file()
    
    # 4. 연결 테스트
    if auth_copied:
        connection_ok = test_google_sheets_connection()
    else:
        connection_ok = False
    
    print("\n" + "=" * 50)
    print("📋 설정 완료 상태:")
    print(f"  • 인증 파일: {'✅' if auth_copied else '❌'}")
    print(f"  • 설정 파일: ✅")
    print(f"  • 환경 파일: {'✅' if env_created else '❌'}")
    print(f"  • 구글시트 연결: {'✅' if connection_ok else '❌'}")
    
    if auth_copied and connection_ok:
        print("\n🎉 구글시트 연동 설정 완료!")
        print("이제 메인 애플리케이션에서 구글시트를 사용할 수 있습니다.")
    else:
        print("\n⚠️ 일부 설정이 완료되지 않았습니다.")
        print("수동으로 인증 파일을 config/ 폴더에 복사해주세요.")

if __name__ == "__main__":
    main()
