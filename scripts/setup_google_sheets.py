#!/usr/bin/env python3
"""
구글시트 연동 설정 도우미

구글 서비스 계정 인증 파일 설정 및 시트 ID 구성을 도와주는 대화형 스크립트
"""

import os
import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
config_dir = project_root / "config"
config_dir.mkdir(exist_ok=True)

def main():
    print("🔗 구글시트 연동 설정")
    print("=" * 40)
    
    # 1. 구글 서비스 계정 JSON 파일 확인
    credentials_file = config_dir / "google_credentials.json"
    
    if credentials_file.exists():
        print(f"✅ 인증 파일 발견: {credentials_file}")
        
        # JSON 파일 유효성 검사
        try:
            with open(credentials_file, 'r') as f:
                creds = json.load(f)
            
            if 'client_email' in creds and 'private_key' in creds:
                print(f"📧 서비스 계정: {creds['client_email']}")
            else:
                print("❌ 인증 파일 형식이 올바르지 않습니다")
                return False
                
        except Exception as e:
            print(f"❌ 인증 파일 읽기 실패: {e}")
            return False
    else:
        print("❌ 구글 서비스 계정 인증 파일이 없습니다")
        print()
        print("📋 설정 방법:")
        print("1. https://console.cloud.google.com/ 접속")
        print("2. 새 프로젝트 생성 또는 기존 프로젝트 선택")
        print("3. 'Google Sheets API' 활성화")
        print("4. '서비스 계정' 생성")
        print("5. JSON 키 파일 다운로드")
        print(f"6. 파일을 다음 경로에 저장: {credentials_file}")
        print()
        
        # 수동 입력 옵션
        manual_path = input("📁 인증 파일 경로를 직접 입력하시겠습니까? (y/N): ").strip().lower()
        if manual_path == 'y':
            file_path = input("파일 경로 입력: ").strip()
            if os.path.exists(file_path):
                import shutil
                shutil.copy(file_path, credentials_file)
                print(f"✅ 인증 파일 복사 완료: {credentials_file}")
            else:
                print("❌ 파일을 찾을 수 없습니다")
                return False
        else:
            return False
    
    # 2. 구글시트 ID 설정
    config_file = config_dir / "google_sheets_config.json"
    
    print()
    print("📊 구글시트 설정")
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
        print(f"✅ 기존 설정 발견: {config.get('spreadsheet_id', 'Unknown')}")
        
        update = input("🔄 설정을 업데이트하시겠습니까? (y/N): ").strip().lower()
        if update != 'y':
            return test_connection(credentials_file, config.get('spreadsheet_id'))
    
    # 새 설정 입력
    print()
    print("📋 구글시트 설정 방법:")
    print("1. 구글시트에서 새 스프레드시트 생성")
    print("2. 서비스 계정 이메일을 시트 편집자로 초대")
    print("3. 시트 URL에서 ID 부분 복사")
    print("   예: https://docs.google.com/spreadsheets/d/[여기가ID]/edit")
    print()
    
    sheet_id = input("📊 구글시트 ID 입력: ").strip()
    if not sheet_id:
        print("❌ 시트 ID가 입력되지 않았습니다")
        return False
    
    # 설정 저장
    config = {
        "spreadsheet_id": sheet_id,
        "sheet_names": {
            "members": "회원명단",
            "lockers": "락카정보", 
            "rentals": "대여기록",
            "keys": "락카키목록"
        }
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 설정 저장 완료: {config_file}")
    
    # 3. 연결 테스트
    return test_connection(credentials_file, sheet_id)

def test_connection(credentials_file, sheet_id):
    """구글시트 연결 테스트"""
    print()
    print("🔍 연결 테스트 중...")
    
    try:
        # 라이브러리 확인
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            print("❌ 필요한 라이브러리가 설치되지 않았습니다")
            print("🔧 다음 명령어로 설치하세요:")
            print("   pip install gspread google-auth google-auth-oauthlib google-auth-httplib2")
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
        spreadsheet = client.open_by_key(sheet_id)
        
        print(f"✅ 연결 성공!")
        print(f"📊 시트 이름: {spreadsheet.title}")
        print(f"📄 워크시트 수: {len(spreadsheet.worksheets())}")
        
        # 워크시트 목록
        print("📋 워크시트 목록:")
        for ws in spreadsheet.worksheets():
            print(f"  • {ws.title}")
        
        print()
        print("🎉 구글시트 연동 설정 완료!")
        print("이제 메인 앱에서 구글시트를 사용할 수 있습니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        print()
        print("🔧 확인사항:")
        print("1. 서비스 계정이 시트에 편집자로 초대되었는지 확인")
        print("2. Google Sheets API가 활성화되었는지 확인")
        print("3. 시트 ID가 올바른지 확인")
        return False

if __name__ == "__main__":
    try:
        success = main()
        input("\n👆 Enter 키를 눌러 종료하세요...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 설정 취소됨")
        sys.exit(1)
