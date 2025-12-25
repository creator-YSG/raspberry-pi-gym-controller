"""
제품마스터 수식 수정 및 원가대시보드 개선
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

def check_and_fix():
    client = authenticate()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    print("🔍 시트 상태 확인 중...\n")
    
    # 1. 하드웨어BOM 확인
    print("1️⃣ 하드웨어BOM 확인...")
    hw_bom = spreadsheet.worksheet("하드웨어BOM")
    hw_data = hw_bom.get('A4:I12')
    print(f"   데이터 행 수: {len(hw_data)}")
    for row in hw_data[:5]:
        if row and len(row) > 0 and row[0]:
            print(f"   - {row[0]}: {row}")
    
    # 2. 소프트웨어BOM 확인
    print("\n2️⃣ 소프트웨어BOM 확인...")
    sw_bom = spreadsheet.worksheet("소프트웨어BOM")
    sw_data = sw_bom.get('A4:F8')
    print(f"   데이터 행 수: {len(sw_data)}")
    for row in sw_data[:5]:
        if row and len(row) > 0 and row[0]:
            print(f"   - {row[0]}: {row}")
    
    # 3. 제품마스터 수식 수정
    print("\n3️⃣ 제품마스터 수식 수정 중...")
    product_master = spreadsheet.worksheet("제품마스터")
    
    # 현재 값 확인
    current_values = product_master.get('A4:G6')
    print(f"   현재 데이터:")
    for row in current_values:
        print(f"   - {row}")
    
    # 수식 수정 - 더 간단하게
    # F열 (하드웨어원가) - 하드웨어BOM의 I열(부품총액) 합계
    # G열 (소프트웨어월비용) - 소프트웨어BOM의 F열(월비용) 합계
    
    # 하드웨어 제품 (HW-001, HW-002)
    product_master.update([['=SUMIF(하드웨어BOM!$A:$A,A4,하드웨어BOM!$I:$I)']], 'F4', value_input_option='USER_ENTERED')
    product_master.update([['=SUMIF(하드웨어BOM!$A:$A,A5,하드웨어BOM!$I:$I)']], 'F5', value_input_option='USER_ENTERED')
    
    # 소프트웨어 제품 (SW-001)
    product_master.update([['=SUMIF(소프트웨어BOM!$A:$A,A6,소프트웨어BOM!$F:$F)']], 'G6', value_input_option='USER_ENTERED')
    
    # 하드웨어는 소프트웨어 비용 없음, 소프트웨어는 하드웨어 원가 없음
    product_master.update([['-']], 'G4', value_input_option='RAW')
    product_master.update([['-']], 'G5', value_input_option='RAW')
    product_master.update([['-']], 'F6', value_input_option='RAW')
    
    print("   ✅ 제품마스터 수식 수정 완료")
    
    # 수정 후 값 확인
    import time
    time.sleep(2)
    updated_values = product_master.get('A4:G6')
    print(f"\n   수정 후 데이터:")
    for row in updated_values:
        print(f"   - {row}")
    
    # 4. 원가대시보드 개선
    print("\n4️⃣ 원가대시보드 개선 중...")
    cost_dashboard = spreadsheet.worksheet("원가대시보드")
    cost_dashboard.clear()
    
    dashboard_content = [
        ["📈 제품 원가 대시보드"],
        [""],
        ["이 대시보드는 모든 시트의 데이터를 자동으로 집계합니다."],
        [""],
        ["═══════════════════════════════════════════════════════════"],
        ["📦 하드웨어 제품 현황"],
        ["═══════════════════════════════════════════════════════════"],
        [""],
        ["제품ID", "제품명", "부품원가", "부품종류수", "상태"],
        ["HW-001", "=VLOOKUP(A10,제품마스터!A:B,2,FALSE)", "=SUMIF(하드웨어BOM!A:A,A10,하드웨어BOM!I:I)", "=COUNTIF(하드웨어BOM!A:A,A10)", "=VLOOKUP(A10,제품마스터!A:E,5,FALSE)"],
        ["HW-002", "=VLOOKUP(A11,제품마스터!A:B,2,FALSE)", "=SUMIF(하드웨어BOM!A:A,A11,하드웨어BOM!I:I)", "=COUNTIF(하드웨어BOM!A:A,A11)", "=VLOOKUP(A11,제품마스터!A:E,5,FALSE)"],
        ["", "", "", "", ""],
        ["하드웨어 총 원가", "", "=SUM(C10:C11)", "", ""],
        [""],
        ["═══════════════════════════════════════════════════════════"],
        ["💻 소프트웨어 제품 현황"],
        ["═══════════════════════════════════════════════════════════"],
        [""],
        ["제품ID", "제품명", "월운영비", "서비스수", "상태"],
        ["SW-001", "=VLOOKUP(A20,제품마스터!A:B,2,FALSE)", "=SUMIF(소프트웨어BOM!A:A,A20,소프트웨어BOM!F:F)", "=COUNTIF(소프트웨어BOM!A:A,A20)", "=VLOOKUP(A20,제품마스터!A:E,5,FALSE)"],
        ["", "", "", "", ""],
        ["소프트웨어 총 월비용", "", "=SUM(C20:C21)", "", ""],
        [""],
        ["═══════════════════════════════════════════════════════════"],
        ["📊 재고 요약"],
        ["═══════════════════════════════════════════════════════════"],
        [""],
        ["항목", "값", "", ""],
        ["총 부품 종류", "=COUNTA(재고현황!A4:A100)-COUNTBLANK(재고현황!A4:A100)", "", ""],
        ["총 재고 금액", "=SUM(재고현황!I4:I100)", "", ""],
        ["부족 부품 수", '=COUNTIF(재고현황!G4:G100,"*부족*")', "", "⚠️ 발주 필요!"],
        ["발주중 부품 수", '=COUNTIF(재고현황!G4:G100,"*발주중*")', "", ""],
        [""],
        ["═══════════════════════════════════════════════════════════"],
        ["💡 대시보드 사용법"],
        ["═══════════════════════════════════════════════════════════"],
        [""],
        ["▶ 이 대시보드의 역할:"],
        ["  • 모든 제품의 원가를 한눈에 파악"],
        ["  • 재고 상태를 빠르게 체크"],
        ["  • 부족한 부품이 있는지 확인"],
        [""],
        ["▶ 새 제품 추가 시:"],
        ["  1. 제품마스터에 새 제품 등록"],
        ["  2. 하드웨어BOM 또는 소프트웨어BOM에 상세 입력"],
        ["  3. 이 대시보드에도 행 추가 (위 수식 복사)"],
        [""],
        ["▶ 숫자가 0으로 나오면?"],
        ["  • BOM 시트의 제품ID가 정확한지 확인"],
        ["  • 예: 'HW-001'과 'HW-001 '(뒤에 공백)은 다름"],
        [""],
        ["▶ #N/A 오류가 나오면?"],
        ["  • 제품마스터에 해당 제품ID가 있는지 확인"],
    ]
    
    cost_dashboard.update(dashboard_content, 'A1', value_input_option='USER_ENTERED')
    
    # 서식 적용
    cost_dashboard.format('A1', {
        'backgroundColor': {'red': 0.1, 'green': 0.1, 'blue': 0.1},
        'textFormat': {'bold': True, 'fontSize': 16, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
    })
    cost_dashboard.format('A9:E9', {'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 0.8}, 'textFormat': {'bold': True}})
    cost_dashboard.format('A19:E19', {'backgroundColor': {'red': 0.9, 'green': 0.85, 'blue': 0.95}, 'textFormat': {'bold': True}})
    cost_dashboard.format('A27:D27', {'backgroundColor': {'red': 0.95, 'green': 0.9, 'blue': 0.8}, 'textFormat': {'bold': True}})
    cost_dashboard.format('C10:C13', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}})
    cost_dashboard.format('C20:C22', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}})
    cost_dashboard.format('B29', {'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}})
    
    print("   ✅ 원가대시보드 개선 완료")
    
    # 결과 확인
    print("\n" + "="*70)
    print("🎉 수정 완료!")
    print("="*70)
    print("\n📎 시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}\n")
    
    print("📊 원가대시보드 사용법:")
    print("   • 이 대시보드는 자동으로 다른 시트의 데이터를 집계합니다")
    print("   • 하드웨어 제품: 부품원가 합계 + 부품 종류 수 표시")
    print("   • 소프트웨어 제품: 월 운영비 합계 + 서비스 수 표시")
    print("   • 재고 요약: 총 재고금액, 부족 부품 수 표시")
    print("   • 새 제품 추가 시 해당 섹션에 행 추가하고 수식 복사")

if __name__ == "__main__":
    try:
        check_and_fix()
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

