#!/usr/bin/env python3
"""
Google Sheets 초기화 스크립트

스프레드시트에 필요한 시트(탭)들을 생성하고 헤더를 설정합니다.
"""

import json
import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("❌ 필요한 라이브러리가 없습니다.")
    print("   pip install gspread google-auth")
    sys.exit(1)


# 시트별 헤더 정의
SHEET_HEADERS = {
    "회원명단": [
        "member_id", "barcode", "qr_code", "member_name", "phone", "email",
        "membership_type", "program_name", "status", "expiry_date",
        "gender", "member_category", "customer_type", "created_at", "updated_at"
    ],
    "대여기록": [
        "rental_id", "transaction_id", "member_id", "member_name", "locker_number", "zone",
        "rental_barcode_time", "rental_sensor_time", "return_sensor_time",
        "status", "device_id", "created_at"
    ],
    "락카현황": [
        "locker_number", "zone", "sensor_status", "door_status",
        "current_member", "current_member_name", "nfc_uid",
        "maintenance_status", "last_change_time", "updated_at"
    ],
    "센서이벤트": [
        "event_id", "locker_number", "sensor_state", "member_id",
        "rental_id", "session_context", "description", "event_timestamp"
    ],
    "시스템설정": [
        "setting_key", "setting_value", "setting_type", "description", "updated_at"
    ]
}

# 시스템 설정 기본값
DEFAULT_SETTINGS = [
    ["transaction_timeout_seconds", "30", "integer", "트랜잭션 타임아웃 (초)"],
    ["max_daily_rentals", "3", "integer", "일일 최대 대여 횟수"],
    ["sensor_verification_timeout", "30", "integer", "센서 검증 타임아웃 (초)"],
    ["sync_interval_minutes", "5", "integer", "구글시트 동기화 간격 (분)"],
    ["system_version", "1.0.0", "string", "시스템 버전"],
]


def load_config():
    """설정 파일 로드"""
    config_path = PROJECT_ROOT / "config" / "google_sheets_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def connect_sheets(config):
    """Google Sheets API 연결"""
    credentials_path = PROJECT_ROOT / "config" / config["credentials_file"]
    
    if not credentials_path.exists():
        print(f"❌ 인증 파일이 없습니다: {credentials_path}")
        sys.exit(1)
    
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    credentials = Credentials.from_service_account_file(
        str(credentials_path), scopes=scope
    )
    
    client = gspread.authorize(credentials)
    return client


def init_sheets(client, config):
    """시트 초기화"""
    spreadsheet_id = config["spreadsheet_id"]
    sheet_names = config["sheet_names"]
    
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        print(f"✅ 스프레드시트 연결: {spreadsheet.title}")
    except Exception as e:
        print(f"❌ 스프레드시트 연결 실패: {e}")
        print("   서비스 계정에 편집 권한이 있는지 확인하세요.")
        sys.exit(1)
    
    # 기존 시트 목록
    existing_sheets = [ws.title for ws in spreadsheet.worksheets()]
    print(f"📋 기존 시트: {existing_sheets}")
    
    # 각 시트 생성/업데이트
    for key, sheet_name in sheet_names.items():
        print(f"\n🔧 시트 처리: {sheet_name}")
        
        headers = SHEET_HEADERS.get(sheet_name, [])
        if not headers:
            print(f"   ⚠️ 헤더 정의 없음, 건너뜀")
            continue
        
        try:
            if sheet_name in existing_sheets:
                # 기존 시트 사용
                worksheet = spreadsheet.worksheet(sheet_name)
                print(f"   ✅ 기존 시트 사용")
            else:
                # 새 시트 생성
                worksheet = spreadsheet.add_worksheet(
                    title=sheet_name, 
                    rows=1000, 
                    cols=len(headers)
                )
                print(f"   ✅ 새 시트 생성")
            
            # 헤더 확인/설정
            first_row = worksheet.row_values(1)
            if first_row != headers:
                worksheet.update('A1', [headers])
                print(f"   ✅ 헤더 설정: {len(headers)}개 컬럼")
                
                # 헤더 스타일링
                worksheet.format('A1:' + chr(64 + len(headers)) + '1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })
                print(f"   ✅ 헤더 스타일 적용")
            else:
                print(f"   ✅ 헤더 이미 설정됨")
            
            # 시스템설정 시트에 기본값 추가
            if sheet_name == "시스템설정":
                existing_data = worksheet.get_all_values()
                if len(existing_data) <= 1:  # 헤더만 있음
                    for setting in DEFAULT_SETTINGS:
                        worksheet.append_row(setting + [""])
                    print(f"   ✅ 기본 설정값 추가: {len(DEFAULT_SETTINGS)}개")
                else:
                    print(f"   ✅ 설정값 이미 존재")
                    
        except Exception as e:
            print(f"   ❌ 오류: {e}")
    
    # 기본 시트(Sheet1) 삭제 시도
    try:
        default_sheet = spreadsheet.worksheet("Sheet1")
        spreadsheet.del_worksheet(default_sheet)
        print(f"\n🗑️ 기본 시트 'Sheet1' 삭제")
    except:
        pass  # 없으면 무시
    
    print(f"\n✅ 초기화 완료!")
    print(f"📊 스프레드시트 URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")


def main():
    print("=" * 50)
    print("🔧 Google Sheets 초기화")
    print("=" * 50)
    
    # 설정 로드
    config = load_config()
    print(f"📁 스프레드시트 ID: {config['spreadsheet_id']}")
    
    # 연결
    print("\n📡 Google Sheets API 연결 중...")
    client = connect_sheets(config)
    print("✅ 연결 성공")
    
    # 초기화
    print("\n🚀 시트 초기화 시작...")
    init_sheets(client, config)


if __name__ == "__main__":
    main()

