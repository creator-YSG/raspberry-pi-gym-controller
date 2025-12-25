"""
F, G, H 열 완전히 정리 - 간단하게!
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

def clean_fgh_columns():
    client = authenticate()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet("현금흐름장부")
    
    print("🧹 F, G, H 열 정리 중...\n")
    
    # 1. F열(공급가액) 5행부터 완전히 비우기 (수동 입력만)
    print("1. F열(공급가액) 5행 이하 비우는 중...")
    empty_f = [[""] for _ in range(996)]  # 5행부터 1000행까지
    worksheet.update(empty_f, 'F5:F1000', value_input_option='RAW')
    print("   ✅ F열 정리 완료 (수동 입력용)")
    
    # 2. G열(부가세) 5행부터 수식 입력
    print("2. G열(부가세) 수식 입력 중...")
    vat_formulas = [['=IF(F{}="","",F{}*0.1)'.format(i, i)] for i in range(5, 1001)]
    worksheet.update(vat_formulas, 'G5:G1000', value_input_option='USER_ENTERED')
    print("   ✅ G열 수식 완료 (=F×0.1)")
    
    # 3. H열(합계) 5행부터 수식 입력
    print("3. H열(합계) 수식 입력 중...")
    total_formulas = [['=IF(F{}="","",F{}+G{})'.format(i, i, i)] for i in range(5, 1001)]
    worksheet.update(total_formulas, 'H5:H1000', value_input_option='USER_ENTERED')
    print("   ✅ H열 수식 완료 (=F+G)")
    
    # 4. 예시 데이터(2-4행)도 확인
    print("\n4. 예시 데이터(2-4행) 확인 중...")
    
    # 2-4행 G, H 열도 수식으로 변경
    vat_example = [['=IF(F{}="","",F{}*0.1)'.format(i, i)] for i in range(2, 5)]
    worksheet.update(vat_example, 'G2:G4', value_input_option='USER_ENTERED')
    
    total_example = [['=IF(F{}="","",F{}+G{})'.format(i, i, i)] for i in range(2, 5)]
    worksheet.update(total_example, 'H2:H4', value_input_option='USER_ENTERED')
    print("   ✅ 예시 데이터도 수식으로 변경")
    
    print("\n" + "="*70)
    print("🎉 F, G, H 열 정리 완료!")
    print("="*70)
    print("\n✅ 최종 구조:")
    print("   • F열(공급가액): 빈칸 → 직접 입력하세요")
    print("   • G열(부가세): =F×0.1 (자동계산)")
    print("   • H열(합계): =F+G (자동계산)")
    print("\n💡 사용법:")
    print("   1. F열에 공급가액만 입력")
    print("   2. G, H는 자동으로 채워집니다")
    print("   3. 면세 시: G열을 0으로 덮어쓰기")
    print("\n📎 시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}\n")

if __name__ == "__main__":
    print("🚀 F, G, H 열 정리 시작...\n")
    
    try:
        clean_fgh_columns()
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

