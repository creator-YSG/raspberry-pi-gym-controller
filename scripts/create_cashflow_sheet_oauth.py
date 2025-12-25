"""
스타트업 실전형 현금흐름 장부 생성 스크립트 (OAuth 인증)

OAuth 인증을 사용하여 사용자의 드라이브에 직접 현금흐름 관리용 시트를 생성합니다.
"""

import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
from pathlib import Path
from datetime import datetime

# 설정 파일 경로
BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
CLIENT_SECRET_FILE = BASE_DIR / "client_secret_59516272673-h30ecghk38d912tkcal5k3mkgpqm11ad.apps.googleusercontent.com.json"
TOKEN_FILE = INSTANCE_DIR / "sheets_token.pickle"

# OAuth 스코프
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

def authenticate_google_sheets_oauth():
    """OAuth를 사용한 구글 시트 API 인증"""
    creds = None
    
    # 저장된 토큰이 있으면 로드
    if TOKEN_FILE.exists():
        print("📂 저장된 인증 토큰을 찾았습니다...")
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # 토큰이 없거나 유효하지 않으면 새로 인증
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 토큰을 갱신합니다...")
            creds.refresh(Request())
        else:
            print("🔐 새로운 인증이 필요합니다. 브라우저가 열립니다...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 토큰 저장
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        print("✅ 인증 토큰이 저장되었습니다.")
    
    return gspread.authorize(creds)

def create_cashflow_spreadsheet():
    """현금흐름 장부 스프레드시트 생성"""
    
    # OAuth 인증
    client = authenticate_google_sheets_oauth()
    
    # 새 스프레드시트 생성
    spreadsheet_title = f"[스타트업 실전형] 현금흐름 장부 - {datetime.now().strftime('%Y년 %m월')}"
    
    print(f"\n📝 새 스프레드시트 생성 중: {spreadsheet_title}")
    spreadsheet = client.create(spreadsheet_title)
    
    print(f"✅ 스프레드시트 생성 완료")
    print(f"📎 URL: https://docs.google.com/spreadsheets/d/{spreadsheet.id}")
    
    # 첫 번째 시트 설정
    worksheet = spreadsheet.sheet1
    worksheet.update_title("현금흐름장부")
    
    print("\n📋 시트 구조 생성 중...")
    
    # 헤더 설정
    headers = [
        "날짜", "구분", "대분류", "상세항목", "거래처", 
        "공급가액", "부가세", "합계(지출액)", "결제수단", "증빙", "비고"
    ]
    
    worksheet.update([headers], 'A1:K1')
    
    # 헤더 서식 설정
    worksheet.format('A1:K1', {
        'backgroundColor': {'red': 0.2, 'green': 0.5, 'blue': 0.8},
        'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
        'horizontalAlignment': 'CENTER'
    })
    
    # 예시 데이터 추가
    example_data = [
        [
            "2025-12-21", "지출", "제품/제조", "박스 인쇄비", "(주)스톰팩",
            500000, 50000, 550000, "개인카드", "카드영수증", "샘플 500개"
        ],
        [
            "2025-12-20", "지출", "마케팅/영업", "인스타그램 광고", "Meta",
            100000, "", 100000, "개인카드", "카드영수증", "12/15-12/20 캠페인"
        ],
        [
            "2025-12-19", "지출", "운영비", "노션 구독료", "Notion Labs",
            8000, "", 8000, "개인카드", "카드영수증", "팀 플랜 월결제"
        ]
    ]
    
    worksheet.update(example_data, 'A2:K4')
    
    # 금액 셀 서식 (통화)
    worksheet.format('F2:H1000', {
        'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}
    })
    
    print("✅ 현금흐름장부 시트 생성 완료")
    
    # 대시보드 시트 생성
    print("\n📊 대시보드 시트 생성 중...")
    dashboard_sheet = spreadsheet.add_worksheet(title="대시보드", rows="50", cols="10")
    
    # 대시보드 내용
    dashboard_content = [
        ["💰 스타트업 현금흐름 대시보드"],
        [""],
        ["📅 기준 월:", datetime.now().strftime("%Y년 %m월")],
        [""],
        ["📊 월별 요약"],
        ["구분", "금액 (원)"],
        ["이번 달 총 지출", "=SUMIF(현금흐름장부!B:B,\"지출\",현금흐름장부!H:H)"],
        ["이번 달 총 수입", "=SUMIF(현금흐름장부!B:B,\"수입\",현금흐름장부!H:H)"],
        ["순 현금흐름", "=B8-B7"],
        [""],
        ["💳 결제수단별 지출"],
        ["개인카드(대표)", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!I:I,\"개인카드(대표)\")", "→ 법인 전환 시 정산 필요"],
        ["개인계좌(대표)", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!I:I,\"개인계좌(대표)\")", "→ 법인 전환 시 정산 필요"],
        ["현금", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!I:I,\"현금\")"],
        [""],
        ["📂 대분류별 지출"],
        ["제품/제조", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!C:C,\"제품/제조\")"],
        ["마케팅/영업", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!C:C,\"마케팅/영업\")"],
        ["운영비", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!C:C,\"운영비\")"],
        ["인건비/복리후생", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!C:C,\"인건비/복리후생\")"],
        ["여비교통비", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!C:C,\"여비교통비\")"],
        ["자산/투자", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!C:C,\"자산/투자\")"],
        ["기타", "=SUMIFS(현금흐름장부!H:H,현금흐름장부!B:B,\"지출\",현금흐름장부!C:C,\"기타\")"],
        [""],
        ["📌 증빙 체크리스트"],
        ["증빙 없음 건수", "=COUNTIFS(현금흐름장부!J:J,\"없음\")", "⚠️ 세무 처리 주의"],
        [""],
        ["💡 세무 팁:"],
        ["• 개인카드/계좌 사용 금액은 법인 전환 시 정산 가능합니다"],
        ["• 증빙 없는 지출은 3만 원 이하만 안전합니다"],
        ["• 영수증은 구글 드라이브에 백업하세요"],
    ]
    
    dashboard_sheet.update(dashboard_content, 'A1')
    
    # 대시보드 서식 설정
    dashboard_sheet.format('A1', {
        'backgroundColor': {'red': 1, 'green': 0.7, 'blue': 0},
        'textFormat': {'bold': True, 'fontSize': 16}
    })
    
    dashboard_sheet.format('A5', {
        'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
        'textFormat': {'bold': True}
    })
    
    dashboard_sheet.format('A11', {
        'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
        'textFormat': {'bold': True}
    })
    
    dashboard_sheet.format('A16', {
        'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
        'textFormat': {'bold': True}
    })
    
    dashboard_sheet.format('A25', {
        'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
        'textFormat': {'bold': True}
    })
    
    # 금액 셀 서식
    dashboard_sheet.format('B7:B14', {
        'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}
    })
    
    dashboard_sheet.format('B17:B23', {
        'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}
    })
    
    # 순 현금흐름 강조
    dashboard_sheet.format('B9', {
        'backgroundColor': {'red': 1, 'green': 1, 'blue': 0.8},
        'textFormat': {'bold': True},
        'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0'}
    })
    
    print("✅ 대시보드 시트 생성 완료")
    
    # 가이드 시트 생성
    print("\n📖 사용 가이드 시트 생성 중...")
    guide_sheet = spreadsheet.add_worksheet(title="사용가이드", rows="40", cols="5")
    
    guide_content = [
        ["📘 스타트업 실전형 현금흐름 장부 사용 가이드"],
        [""],
        ["1️⃣ 기본 사용법"],
        [""],
        ["• 매일 지출/수입이 발생할 때마다 '현금흐름장부' 시트에 기록하세요"],
        ["• 드롭다운 설정은 아래 2단계 참고"],
        ["• 부가세는 공급가액의 10%입니다 (직접 계산하여 입력)"],
        ["• 증빙 사진은 구글 드라이브에 별도 저장하고 '비고'에 링크를 걸어두세요"],
        [""],
        ["2️⃣ 드롭다운 설정 방법 (한 번만 하면 됨)"],
        [""],
        ["▶ B열(구분) 드롭다운 설정:"],
        ["  1. B열 헤더를 클릭하여 전체 열 선택"],
        ["  2. 메뉴: 데이터 > 데이터 확인"],
        ["  3. 기준: 목록(항목 1개 범위에서)"],
        ["  4. 값 입력: 지출,수입,자금투입"],
        ["  5. 저장"],
        [""],
        ["▶ C열(대분류) 드롭다운 설정:"],
        ["  값: 제품/제조,마케팅/영업,운영비,인건비/복리후생,여비교통비,자산/투자,기타"],
        [""],
        ["▶ I열(결제수단) 드롭다운 설정:"],
        ["  값: 개인카드(대표),개인계좌(대표),현금,법인카드,법인계좌"],
        [""],
        ["▶ J열(증빙) 드롭다운 설정:"],
        ["  값: 세금계산서,카드영수증,현금영수증,간이영수증,없음"],
        [""],
        ["3️⃣ 각 항목 설명"],
        [""],
        ["항목", "설명", "예시"],
        ["날짜", "거래 발생 날짜", "2025-12-21"],
        ["구분", "지출/수입/자금투입", "지출"],
        ["대분류", "지출의 용도 카테고리", "제품/제조"],
        ["상세항목", "구체적인 지출 내역", "박스 인쇄비"],
        ["거래처", "거래한 업체명", "(주)스톰팩"],
        ["공급가액", "부가세 제외 금액", "500,000"],
        ["부가세", "부가세 (공급가액의 10%)", "50,000"],
        ["합계(지출액)", "실제 지불한 총 금액", "550,000"],
        ["결제수단", "어떤 방법으로 결제했는지", "개인카드(대표)"],
        ["증빙", "증빙 종류", "카드영수증"],
        ["비고", "추가 메모", "샘플 500개"],
        [""],
        ["4️⃣ 대시보드 활용"],
        [""],
        ["• '대시보드' 시트에서 이번 달 현금흐름을 한눈에 확인하세요"],
        ["• 개인카드/계좌 사용 금액은 나중에 법인 전환 시 정산 가능합니다"],
        ["• 대분류별 지출을 보고 어디에 돈이 많이 나가는지 파악하세요"],
        [""],
        ["5️⃣ 세무 처리 팁"],
        [""],
        ["• 증빙이 없는 지출은 3만 원 이하만 안전합니다"],
        ["• 카드영수증이 가장 확실한 증빙입니다"],
        ["• 현금 지출은 반드시 현금영수증을 받으세요 (사업자번호 제시)"],
        ["• 이 장부를 그대로 세무사에게 전달하면 됩니다"],
        [""],
        ["💡 문의사항이 있으면 언제든 물어보세요!"],
    ]
    
    guide_sheet.update(guide_content, 'A1')
    
    # 가이드 서식
    guide_sheet.format('A1', {
        'backgroundColor': {'red': 0.3, 'green': 0.7, 'blue': 0.3},
        'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
    })
    
    guide_sheet.format('A3', {'textFormat': {'bold': True, 'fontSize': 12}})
    guide_sheet.format('A10', {'textFormat': {'bold': True, 'fontSize': 12}})
    guide_sheet.format('A27', {'textFormat': {'bold': True, 'fontSize': 12}})
    guide_sheet.format('A42', {'textFormat': {'bold': True, 'fontSize': 12}})
    guide_sheet.format('A48', {'textFormat': {'bold': True, 'fontSize': 12}})
    
    guide_sheet.format('A29:C29', {
        'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
        'textFormat': {'bold': True}
    })
    
    print("✅ 사용 가이드 시트 생성 완료")
    
    print("\n" + "="*70)
    print("🎉 스타트업 현금흐름 장부 생성 완료!")
    print("="*70)
    print(f"\n📎 스프레드시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{spreadsheet.id}\n")
    print("📋 생성된 시트:")
    print("   1. 현금흐름장부 - 일일 거래 기록용")
    print("   2. 대시보드 - 월별 요약 및 통계")
    print("   3. 사용가이드 - 상세한 사용 방법 및 드롭다운 설정법\n")
    print("💡 다음 단계:")
    print("   1. 위 URL을 북마크에 저장하세요")
    print("   2. 사용가이드의 2단계를 보고 드롭다운을 설정하세요 (5분 소요)")
    print("   3. 매일 지출/수입 발생 시 바로 기록하세요")
    print("   4. 데이터가 10줄 정도 쌓이면 대시보드를 확인하세요")
    print("   5. 증빙 사진은 구글 드라이브에 별도 폴더로 관리하세요\n")
    
    return spreadsheet

if __name__ == "__main__":
    print("🚀 스타트업 실전형 현금흐름 장부 생성을 시작합니다...\n")
    
    try:
        spreadsheet = create_cashflow_spreadsheet()
    except FileNotFoundError as e:
        print(f"❌ 오류: 필요한 파일을 찾을 수 없습니다.")
        print(f"   {e}")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

