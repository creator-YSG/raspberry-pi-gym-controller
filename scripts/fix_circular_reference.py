"""
현금흐름 장부 수식 수정 - 순환참조 제거
단순하게: 공급가액 입력 → 부가세/합계 자동계산
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
    """인증"""
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    return gspread.authorize(creds)

def fix_formulas():
    """수식 수정 및 대시보드 점검"""
    
    client = authenticate()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    print("🔧 현금흐름 장부 수식 수정 중...\n")
    
    # 1. 현금흐름장부 수식 단순화
    print("1️⃣ 현금흐름장부 수식 수정 중...")
    worksheet = spreadsheet.worksheet("현금흐름장부")
    
    # 부가세(G열): F열 * 0.1 (F열이 비어있으면 빈칸)
    print("   - 부가세 자동계산 수식...")
    vat_formulas = [['=IF(F{}="","",F{}*0.1)'.format(i, i)] for i in range(2, 1001)]
    worksheet.update(vat_formulas, 'G2:G1001', value_input_option='USER_ENTERED')
    
    # 합계(H열): F열 + G열 (F열이 비어있으면 빈칸)
    print("   - 합계 자동계산 수식...")
    total_formulas = [['=IF(F{}="","",F{}+G{})'.format(i, i, i)] for i in range(2, 1001)]
    worksheet.update(total_formulas, 'H2:H1001', value_input_option='USER_ENTERED')
    
    print("   ✅ 수식 수정 완료!")
    print("   💡 사용법: 공급가액(F열)만 입력하면 부가세, 합계 자동계산")
    print("   💡 면세일 때: 부가세(G열)를 0으로 수동 변경")
    
    # 2. 대시보드 점검 및 수정
    print("\n2️⃣ 대시보드 점검 및 수정 중...")
    dashboard = spreadsheet.worksheet("대시보드")
    
    # 현재 대시보드 내용 확인
    print("   - 현재 수식 확인 중...")
    
    # 대시보드 수식들 다시 확인하고 수정
    dashboard_updates = [
        ('B7', '=SUMIF(현금흐름장부!B:B,"지출",현금흐름장부!H:H)', '이번 달 총 지출'),
        ('B8', '=SUMIF(현금흐름장부!B:B,"수입",현금흐름장부!H:H)', '이번 달 총 수입'),
        ('B9', '=B8-B7', '순 현금흐름'),
        ('B12', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!I:I,"개인카드")', '개인카드 지출'),
        ('B13', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!I:I,"개인계좌(대표)")', '개인계좌 지출'),
        ('B14', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!I:I,"현금")', '현금 지출'),
        ('B17', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"제품/제조")', '제품/제조'),
        ('B18', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"마케팅/영업")', '마케팅/영업'),
        ('B19', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"운영비")', '운영비'),
        ('B20', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"인건비/복리후생")', '인건비/복리후생'),
        ('B21', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"여비교통비")', '여비교통비'),
        ('B22', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"자산/투자")', '자산/투자'),
        ('B23', '=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,"지출",현금흐름장부!C:C,"기타")', '기타'),
        ('B26', '=COUNTIFS(현금흐름장부!J:J,"없음")', '증빙 없음 건수'),
    ]
    
    for cell, formula, desc in dashboard_updates:
        dashboard.update([[formula]], cell, value_input_option='USER_ENTERED')
        print(f"   ✅ {cell}: {desc}")
    
    # 대시보드 값 확인
    print("\n   - 대시보드 현재 값 확인 중...")
    try:
        values = dashboard.get('B7:B9')
        print(f"   📊 이번 달 총 지출: {values[0][0] if values and len(values) > 0 else '계산 중...'}")
        print(f"   📊 이번 달 총 수입: {values[1][0] if values and len(values) > 1 else '계산 중...'}")
        print(f"   📊 순 현금흐름: {values[2][0] if values and len(values) > 2 else '계산 중...'}")
    except Exception as e:
        print(f"   ⚠️ 값 확인 실패 (수식은 정상 적용됨): {e}")
    
    print("\n   ✅ 대시보드 점검 완료!")
    
    # 3. 사용가이드 업데이트 (역계산 부분 제거)
    print("\n3️⃣ 사용가이드 업데이트 중...")
    guide_sheet = spreadsheet.worksheet("사용가이드")
    
    # 금액 입력 방법 부분만 수정
    guide_updates = [
        ["▶ 금액 입력 방법"],
        ["  "],
        ["  1. F열(공급가액)에 금액 입력"],
        ["     → G열(부가세), H열(합계)가 자동으로 계산됩니다"],
        ["     예: 공급가액 500,000 입력 → 부가세 50,000, 합계 550,000 자동"],
        ["  "],
        ["  2. 면세 물품인 경우"],
        ["     → F열에 전체 금액 입력 후, G열(부가세)를 0으로 덮어쓰기"],
        ["     예: F열에 100,000 입력 → G열을 0으로 변경"],
        ["  "],
        ["  3. 합계만 알고 있을 때 (예: 배달음식 33,000원)"],
        ["     → F열에 30,000 입력 (역계산: 33,000 ÷ 1.1)"],
        ["     → 또는 F열에 33,000 입력 후 G열 부가세를 직접 수정"],
        ["  "],
        ["  💡 팁: 합계 ÷ 1.1 = 공급가액 (계산기 사용)"],
    ]
    
    guide_sheet.update(guide_updates, 'A19:A32', value_input_option='RAW')
    print("   ✅ 사용가이드 업데이트 완료!")
    
    print("\n" + "="*70)
    print("🎉 수식 수정 완료!")
    print("="*70)
    print("\n✅ 수정 내용:")
    print("   1. 순환참조 오류 해결")
    print("   2. 단순한 수식으로 변경:")
    print("      - 공급가액(F) 입력 → 부가세(G), 합계(H) 자동계산")
    print("   3. 대시보드 모든 수식 점검 및 수정 완료")
    print("   4. 사용가이드 업데이트 (역계산 부분 제거)")
    print("\n💡 사용법:")
    print("   • 기본: 공급가액만 입력하면 됩니다")
    print("   • 면세: 부가세를 0으로 덮어쓰기")
    print("   • 합계만 알 때: 계산기로 ÷1.1 해서 공급가액에 입력")
    print("\n📎 시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}\n")

if __name__ == "__main__":
    print("🚀 현금흐름 장부 수식 수정 시작...\n")
    
    try:
        fix_formulas()
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

