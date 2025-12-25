"""
BOM 시트에서 제품명을 제품마스터에서 자동으로 불러오기
VLOOKUP으로 제품ID → 제품명 자동 연결
"""

import gspread
from google.oauth2.credentials import Credentials
import pickle
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
TOKEN_FILE = INSTANCE_DIR / "sheets_token.pickle"
SPREADSHEET_ID = "1v9lkVVs8CGFUEJltFX2WGiFfjd253R_yginO24Ssf3U"

def authenticate():
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    return gspread.authorize(creds)

def link_bom_sheets():
    client = authenticate()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    print("🔗 BOM 시트를 제품마스터와 연결 중...\n")
    
    # 1. 하드웨어BOM 수정
    print("1️⃣ 하드웨어BOM 수정 중...")
    hw_bom = spreadsheet.worksheet("하드웨어BOM")
    hw_bom.clear()
    
    hw_bom_content = [
        ["📦 하드웨어 BOM (Bill of Materials)"],
        [""],
        ["💡 제품ID만 입력하면 제품명이 자동으로 불러와집니다!"],
        [""],
        ["제품ID", "제품명 (자동)", "버전", "부품코드", "부품명", "소요량", "단위", "단가", "부품총액", "공급업체", "리드타임", "비고"],
        ["HW-001", '=IFERROR(VLOOKUP(A6,제품마스터!$A:$B,2,FALSE),"")', "v1.0", "RPI-4B-4GB", "Raspberry Pi 4B 4GB", 1, "EA", 65000, "=F6*H6", "RS코리아", "3일", ""],
        ["HW-001", '=IFERROR(VLOOKUP(A7,제품마스터!$A:$B,2,FALSE),"")', "v1.0", "TS-7INCH", "터치스크린 7인치", 1, "EA", 85000, "=F7*H7", "엘레파츠", "5일", ""],
        ["HW-001", '=IFERROR(VLOOKUP(A8,제품마스터!$A:$B,2,FALSE),"")', "v1.0", "ESP32-WROOM", "ESP32 모듈", 1, "EA", 8000, "=F8*H8", "디바이스마트", "2일", ""],
        ["HW-001", '=IFERROR(VLOOKUP(A9,제품마스터!$A:$B,2,FALSE),"")', "v1.0", "PN532", "NFC 모듈", 1, "EA", 12000, "=F9*H9", "알리익스프레스", "14일", ""],
        ["HW-001", '=IFERROR(VLOOKUP(A10,제품마스터!$A:$B,2,FALSE),"")', "v1.0", "PSU-5V3A", "전원어댑터 5V/3A", 1, "EA", 15000, "=F10*H10", "위드로봇", "2일", ""],
        ["HW-002", '=IFERROR(VLOOKUP(A11,제품마스터!$A:$B,2,FALSE),"")', "v1.0", "ESP32-WROOM", "ESP32 모듈", 1, "EA", 8000, "=F11*H11", "디바이스마트", "2일", ""],
        ["HW-002", '=IFERROR(VLOOKUP(A12,제품마스터!$A:$B,2,FALSE),"")', "v1.0", "PN532", "NFC 모듈", 1, "EA", 12000, "=F12*H12", "알리익스프레스", "14일", ""],
        ["", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", "", "", ""],
    ]
    
    # 빈 행에도 수식 추가 (16~100행)
    for i in range(16, 101):
        hw_bom_content.append([
            "", 
            f'=IFERROR(VLOOKUP(A{i},제품마스터!$A:$B,2,FALSE),"")', 
            "", "", "", "", "", "", 
            f'=IF(F{i}="","",F{i}*H{i})', 
            "", "", ""
        ])
    
    hw_bom.update(hw_bom_content, 'A1', value_input_option='USER_ENTERED')
    
    # 서식
    hw_bom.format('A1', {
        'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8},
        'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
    })
    hw_bom.format('A5:L5', {
        'backgroundColor': {'red': 0.8, 'green': 0.85, 'blue': 0.95},
        'textFormat': {'bold': True}
    })
    hw_bom.format('H6:I200', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}})
    
    print("   ✅ 하드웨어BOM 완료")
    print("   💡 B열(제품명)이 A열(제품ID)을 기준으로 자동 불러오기")
    
    # 2. 소프트웨어BOM 수정
    print("\n2️⃣ 소프트웨어BOM 수정 중...")
    sw_bom = spreadsheet.worksheet("소프트웨어BOM")
    sw_bom.clear()
    
    sw_bom_content = [
        ["💻 소프트웨어 BOM (월간 운영비용)"],
        [""],
        ["💡 제품ID만 입력하면 제품명이 자동으로 불러와집니다!"],
        [""],
        ["제품ID", "제품명 (자동)", "항목코드", "항목명", "카테고리", "월비용", "단위", "공급업체", "라이선스", "갱신일", "비고"],
        ["SW-001", '=IFERROR(VLOOKUP(A6,제품마스터!$A:$B,2,FALSE),"")', "AWS-EC2", "AWS EC2", "인프라", 50000, "월", "AWS", "종량제", "", "t3.micro"],
        ["SW-001", '=IFERROR(VLOOKUP(A7,제품마스터!$A:$B,2,FALSE),"")', "AWS-S3", "AWS S3", "인프라", 10000, "월", "AWS", "종량제", "", "사진 저장"],
        ["SW-001", '=IFERROR(VLOOKUP(A8,제품마스터!$A:$B,2,FALSE),"")', "GSHEET", "Google Workspace", "협업", 12000, "월", "Google", "연간", "2026-01-15", ""],
        ["", "", "", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", "", "", ""],
    ]
    
    # 빈 행에도 수식 추가 (11~50행)
    for i in range(11, 51):
        sw_bom_content.append([
            "", 
            f'=IFERROR(VLOOKUP(A{i},제품마스터!$A:$B,2,FALSE),"")', 
            "", "", "", "", "", "", "", "", ""
        ])
    
    sw_bom.update(sw_bom_content, 'A1', value_input_option='USER_ENTERED')
    
    # 서식
    sw_bom.format('A1', {
        'backgroundColor': {'red': 0.6, 'green': 0.2, 'blue': 0.6},
        'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
    })
    sw_bom.format('A5:K5', {
        'backgroundColor': {'red': 0.9, 'green': 0.85, 'blue': 0.95},
        'textFormat': {'bold': True}
    })
    sw_bom.format('F6:F100', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}})
    
    # 카테고리 드롭다운
    requests = [{
        "setDataValidation": {
            "range": {"sheetId": sw_bom.id, "startRowIndex": 5, "endRowIndex": 100, "startColumnIndex": 4, "endColumnIndex": 5},
            "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [
                    {"userEnteredValue": "인프라"}, {"userEnteredValue": "모니터링"},
                    {"userEnteredValue": "협업"}, {"userEnteredValue": "AI"}, {"userEnteredValue": "기타"}
                ]},
                "showCustomUi": True
            }
        }
    }]
    spreadsheet.batch_update({"requests": requests})
    
    print("   ✅ 소프트웨어BOM 완료")
    print("   💡 B열(제품명)이 A열(제품ID)을 기준으로 자동 불러오기")
    
    # 3. 재고현황도 제품마스터 연동은 필요없음 (부품 기준이라)
    print("\n3️⃣ 재고현황은 부품 기준이라 그대로 유지")
    
    print("\n" + "="*70)
    print("🎉 BOM 시트 연결 완료!")
    print("="*70)
    print("\n✅ 이제 이렇게 작동합니다:")
    print("")
    print("   제품마스터에서 제품명 변경")
    print("        ↓")
    print("   하드웨어BOM의 제품명 자동 변경 (VLOOKUP)")
    print("        ↓")
    print("   소프트웨어BOM의 제품명 자동 변경 (VLOOKUP)")
    print("        ↓")
    print("   원가대시보드에도 자동 반영 (QUERY)")
    print("")
    print("💡 BOM 시트에서 새 부품 추가할 때:")
    print("   1. A열에 제품ID만 입력 (예: HW-001)")
    print("   2. B열(제품명)은 자동으로 채워짐!")
    print("   3. 나머지 부품 정보 입력")
    print("")
    print("📎 시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}\n")

if __name__ == "__main__":
    try:
        link_bom_sheets()
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

