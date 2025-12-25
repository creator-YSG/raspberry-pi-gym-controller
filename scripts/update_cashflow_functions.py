"""
기존 현금흐름 장부 시트에 함수 추가 스크립트
"""

import gspread
from google.oauth2.credentials import Credentials
import pickle
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
TOKEN_FILE = INSTANCE_DIR / "sheets_token.pickle"

# 생성된 스프레드시트 ID
SPREADSHEET_ID = "1v9lkVVs8CGFUEJltFX2WGiFfjd253R_yginO24Ssf3U"

def authenticate():
    """인증"""
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    return gspread.authorize(creds)

def update_cashflow_sheet():
    """현금흐름 장부에 함수 추가"""
    
    client = authenticate()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    print("📝 현금흐름장부 업데이트 중...\n")
    
    # 현금흐름장부 시트
    worksheet = spreadsheet.worksheet("현금흐름장부")
    
    # 부가세 수식 추가 (G열 = F열 * 0.1)
    print("1. 부가세 자동계산 수식 추가 중...")
    # 수식들을 리스트로 만들어서 한번에 업데이트
    vat_formulas = [['=IF(F{}="","",F{}*0.1)'.format(i, i)] for i in range(2, 1001)]
    worksheet.update('G2:G1001', vat_formulas, value_input_option='USER_ENTERED')
    print("   ✅ 부가세 자동계산 완료")
    
    # 합계 수식 추가 (H열 = F열 + G열)
    print("2. 합계 자동계산 수식 추가 중...")
    total_formulas = [['=IF(F{}="","",F{}+G{})'.format(i, i, i)] for i in range(2, 1001)]
    worksheet.update('H2:H1001', total_formulas, value_input_option='USER_ENTERED')
    print("   ✅ 합계 자동계산 완료")
    
    # 기존 예시 데이터의 부가세/합계를 수식으로 변경
    print("3. 예시 데이터를 수식으로 변경 중...")
    # 2-4행의 부가세/합계를 수식이 자동으로 계산하도록 이미 처리됨
    print("   ✅ 예시 데이터 업데이트 완료")
    
    print("\n📊 대시보드 수식 수정 중...\n")
    
    # 대시보드 시트
    dashboard = spreadsheet.worksheet("대시보드")
    
    # 수식들을 배열로 업데이트 (텍스트가 아닌 실제 수식으로)
    print("1. 월별 요약 수식 수정 중...")
    
    # B7: 이번 달 총 지출
    dashboard.update('B7', [['=SUMIF(현금흐름장부!B:B,"지출",현금흐름장부!H:H)']], value_input_option='USER_ENTERED')
    
    # B8: 이번 달 총 수입
    dashboard.update('B8', [['=SUMIF(현금흐름장부!B:B,"수입",현금흐름장부!H:H)']], value_input_option='USER_ENTERED')
    
    # B9: 순 현금흐름
    dashboard.update('B9', [['=B8-B7']], value_input_option='USER_ENTERED')
    
    print("   ✅ 월별 요약 완료")
    
    print("2. 결제수단별 지출 수식 수정 중...")
    
    # B12: 개인카드(대표)
    dashboard.update('B12', [['=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!I:I,"개인카드")']], value_input_option='USER_ENTERED')
    
    # B13: 개인계좌(대표)
    dashboard.update('B13', [['=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!I:I,"개인계좌(대표)")']], value_input_option='USER_ENTERED')
    
    # B14: 현금
    dashboard.update('B14', [['=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!I:I,"현금")']], value_input_option='USER_ENTERED')
    
    print("   ✅ 결제수단별 지출 완료")
    
    print("3. 대분류별 지출 수식 수정 중...")
    
    # B17-B23: 대분류별 지출
    categories = [
        ('B17', '제품/제조'),
        ('B18', '마케팅/영업'),
        ('B19', '운영비'),
        ('B20', '인건비/복리후생'),
        ('B21', '여비교통비'),
        ('B22', '자산/투자'),
        ('B23', '기타')
    ]
    
    for cell, category in categories:
        formula = f'=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"{category}")'
        dashboard.update(cell, [[formula]], value_input_option='USER_ENTERED')
    
    print("   ✅ 분류별 지출 완료")
    
    print("4. 증빙 체크리스트 수식 수정 중...")
    
    # B26: 증빙 없음 건수
    dashboard.update('B26', [['=COUNTIFS(현금흐름장부!J:J,"없음")']], value_input_option='USER_ENTERED')
    
    print("   ✅ 증빙 체크리스트 완료")
    
    print("\n" + "="*70)
    print("🎉 함수 추가 완료!")
    print("="*70)
    print("\n✅ 추가된 기능:")
    print("   1. 현금흐름장부:")
    print("      - 부가세 자동계산 (공급가액 × 10%)")
    print("      - 합계 자동계산 (공급가액 + 부가세)")
    print("\n   2. 대시보드:")
    print("      - 이번 달 총 지출/수입 자동 집계")
    print("      - 순 현금흐름 자동 계산")
    print("      - 결제수단별 지출 자동 집계")
    print("      - 대분류별 지출 자동 집계")
    print("      - 증빙 없음 건수 자동 카운트")
    print("\n💡 이제 현금흐름장부에 공급가액만 입력하면")
    print("   부가세와 합계가 자동으로 계산됩니다!")
    print("\n📎 시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}\n")

if __name__ == "__main__":
    print("🔧 현금흐름 장부 함수 추가 작업을 시작합니다...\n")
    
    try:
        update_cashflow_sheet()
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

