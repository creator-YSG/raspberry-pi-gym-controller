"""
현금흐름 장부에 드롭다운(데이터 확인 규칙) 추가 스크립트
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

def add_dropdown_validation():
    """드롭다운 규칙 추가"""
    
    client = authenticate()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet("현금흐름장부")
    
    print("📋 드롭다운 규칙 추가 중...\n")
    
    # 데이터 검증 규칙을 batch로 추가
    requests = []
    
    # B열(구분) - 지출, 수입, 자금투입
    print("1. B열(구분) 드롭다운 설정 중...")
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": worksheet.id,
                "startRowIndex": 1,  # 2행부터 (0-based)
                "endRowIndex": 1000,
                "startColumnIndex": 1,  # B열 (0-based)
                "endColumnIndex": 2
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "지출"},
                        {"userEnteredValue": "수입"},
                        {"userEnteredValue": "자금투입"}
                    ]
                },
                "showCustomUi": True,
                "strict": True
            }
        }
    })
    print("   ✅ B열(구분) 설정 완료")
    
    # C열(대분류) - 제품/제조, 마케팅/영업 등
    print("2. C열(대분류) 드롭다운 설정 중...")
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": worksheet.id,
                "startRowIndex": 1,
                "endRowIndex": 1000,
                "startColumnIndex": 2,  # C열
                "endColumnIndex": 3
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "제품/제조"},
                        {"userEnteredValue": "마케팅/영업"},
                        {"userEnteredValue": "운영비"},
                        {"userEnteredValue": "인건비/복리후생"},
                        {"userEnteredValue": "여비교통비"},
                        {"userEnteredValue": "자산/투자"},
                        {"userEnteredValue": "기타"}
                    ]
                },
                "showCustomUi": True,
                "strict": True
            }
        }
    })
    print("   ✅ C열(대분류) 설정 완료")
    
    # I열(결제수단) - 개인카드, 개인계좌, 현금, 법인카드, 법인계좌
    print("3. I열(결제수단) 드롭다운 설정 중...")
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": worksheet.id,
                "startRowIndex": 1,
                "endRowIndex": 1000,
                "startColumnIndex": 8,  # I열
                "endColumnIndex": 9
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "개인카드"},
                        {"userEnteredValue": "개인계좌(대표)"},
                        {"userEnteredValue": "현금"},
                        {"userEnteredValue": "법인카드"},
                        {"userEnteredValue": "법인계좌"}
                    ]
                },
                "showCustomUi": True,
                "strict": True
            }
        }
    })
    print("   ✅ I열(결제수단) 설정 완료")
    
    # J열(증빙) - 세금계산서, 카드영수증, 현금영수증, 간이영수증, 없음
    print("4. J열(증빙) 드롭다운 설정 중...")
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": worksheet.id,
                "startRowIndex": 1,
                "endRowIndex": 1000,
                "startColumnIndex": 9,  # J열
                "endColumnIndex": 10
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "세금계산서"},
                        {"userEnteredValue": "카드영수증"},
                        {"userEnteredValue": "현금영수증"},
                        {"userEnteredValue": "간이영수증"},
                        {"userEnteredValue": "없음"}
                    ]
                },
                "showCustomUi": True,
                "strict": True
            }
        }
    })
    print("   ✅ J열(증빙) 설정 완료")
    
    # Batch 요청 실행
    print("\n📤 드롭다운 규칙을 시트에 적용 중...")
    spreadsheet.batch_update({"requests": requests})
    
    print("\n" + "="*70)
    print("🎉 드롭다운 규칙 추가 완료!")
    print("="*70)
    print("\n✅ 추가된 드롭다운:")
    print("   • B열(구분): 지출, 수입, 자금투입")
    print("   • C열(대분류): 제품/제조, 마케팅/영업, 운영비, 인건비/복리후생, 여비교통비, 자산/투자, 기타")
    print("   • I열(결제수단): 개인카드, 개인계좌(대표), 현금, 법인카드, 법인계좌")
    print("   • J열(증빙): 세금계산서, 카드영수증, 현금영수증, 간이영수증, 없음")
    print("\n💡 이제 해당 셀을 클릭하면 드롭다운 화살표가 나타납니다!")
    print("   오타 걱정 없이 선택만 하시면 됩니다! ✨")
    print("\n📎 시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}\n")

if __name__ == "__main__":
    print("🔽 드롭다운 규칙 추가 작업을 시작합니다...\n")
    
    try:
        add_dropdown_validation()
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

