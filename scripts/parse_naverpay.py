"""
네이버페이 HTML 파싱 및 현금흐름장부 자동 입력
"""

import json
import re
from datetime import datetime
import gspread
from google.oauth2.credentials import Credentials
import pickle
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
TOKEN_FILE = INSTANCE_DIR / "sheets_token.pickle"
SPREADSHEET_ID = "1v9lkVVs8CGFUEJltFX2WGiFfjd253R_yginO24Ssf3U"

# 이미지 URL 매핑 로드
IMAGE_MAPPING_FILE = BASE_DIR / "scripts" / "image_url_mapping.json"

def load_image_mapping():
    """이미지 URL 매핑 로드"""
    if IMAGE_MAPPING_FILE.exists():
        with open(IMAGE_MAPPING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def authenticate():
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    return gspread.authorize(creds)

def classify_category(product_name, merchant_name):
    """상품명과 거래처명으로 대분류 자동 분류"""
    
    # 소문자로 변환
    product = product_name.lower()
    merchant = merchant_name.lower()
    
    # 제품/제조
    if any(keyword in product for keyword in ['필라멘트', '라즈베리', 'raspberry', 'pi', '모터', 'nema', 'esp32', 'nfc', '센서', '아두이노', 'pcb', '포맥스', '아크릴']):
        return "제품/제조", product_name[:30]
    
    # 자산/투자 (30만원 이상 고가품)
    if any(keyword in product for keyword in ['퀘스트', 'quest', '노트북', '모니터', '피아노', '가구', '의자']):
        return "자산/투자", product_name[:30]
    
    # 인건비/복리후생
    if any(keyword in product + merchant for keyword in ['실장', '미용', '헤어', '식대', '간식', '커피']):
        return "인건비/복리후생", merchant_name if '실장' in product else product_name[:30]
    
    # 운영비
    if any(keyword in product for keyword in ['밥', '라면', '쉐이빙', '폼', '생활용품', '화장지', '휴지']):
        return "운영비", product_name[:30]
    
    # 마케팅/영업
    if any(keyword in product + merchant for keyword in ['광고', '명함', '리플렛', '포스터']):
        return "마케팅/영업", product_name[:30]
    
    # 기타 (기본값)
    return "기타", product_name[:30]

def parse_naverpay_html(html_file):
    """네이버페이 HTML에서 거래 내역 추출"""
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # JSON 데이터 추출
    json_pattern = r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>'
    match = re.search(json_pattern, html_content, re.DOTALL)
    
    if not match:
        print("❌ JSON 데이터를 찾을 수 없습니다")
        return []
    
    json_str = match.group(1)
    data = json.loads(json_str)
    
    # 거래 내역 추출
    transactions = []
    
    try:
        items = data['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']['pages'][0]['items']
        
        for item in items:
            # 날짜 변환
            timestamp = item.get('date', 0)
            date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
            
            # 상품 정보
            product = item.get('product', {})
            merchant_name = item.get('merchantName', '')
            product_name = product.get('name', '')
            price = product.get('price', 0)
            img_url = product.get('imgUrl', '')
            
            # 묶음 주문인 경우 orderAmount에서 가격 가져오기
            if price == 0:
                additional_data = item.get('additionalData', {})
                price = additional_data.get('orderAmount', 0)
            
            if price > 0 and product_name:
                # 대분류 자동 분류
                category, detail = classify_category(product_name, merchant_name)
                
                # 공급가액 계산 (부가세 포함가 ÷ 1.1)
                supply_price = round(price / 1.1)
                
                transactions.append({
                    'date': date,
                    'category': category,
                    'detail': detail,
                    'merchant': merchant_name,
                    'supply_price': supply_price,
                    'price': price,
                    'product_name': product_name,
                    'img_url': img_url
                })
        
        # 날짜순 정렬 (최신순)
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
    except Exception as e:
        print(f"❌ 데이터 파싱 오류: {e}")
        import traceback
        traceback.print_exc()
    
    return transactions

def add_to_cashflow(transactions):
    """현금흐름장부에 추가"""
    
    client = authenticate()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet("현금흐름장부")
    
    # 이미지 URL 매핑 로드
    image_mapping = load_image_mapping()
    
    # 기존 마지막 행 찾기
    all_values = worksheet.get_all_values()
    last_row = len(all_values)
    
    # 비어있지 않은 마지막 행 찾기
    for i in range(len(all_values) - 1, -1, -1):
        if any(all_values[i]):
            last_row = i + 1
            break
    
    next_row = last_row + 1
    
    print(f"\n📝 {next_row}행부터 입력 시작...\n")
    
    # 각 거래 내역을 행으로 추가
    rows_to_add = []
    
    for i, tx in enumerate(transactions):
        row_num = next_row + i
        
        # 이미지 URL 가져오기
        img_filename = tx['img_url'].split('/')[-1] if tx['img_url'] else ''
        thumbnail_url = image_mapping.get(img_filename, '')
        
        # 이미지 수식 (있으면 IMAGE 함수, 없으면 빈칸)
        image_formula = f'=IMAGE("{thumbnail_url}", 1)' if thumbnail_url else ''
        
        # A~L열: 날짜, 구분, 대분류, 상세항목, 상품이미지, 거래처, 공급가액, 부가세(수식), 합계(수식), 결제수단, 증빙, 비고
        row = [
            tx['date'],                    # A: 날짜
            '지출',                        # B: 구분
            tx['category'],                # C: 대분류
            tx['detail'],                  # D: 상세항목
            image_formula,                 # E: 상품이미지 (IMAGE 수식)
            tx['merchant'],                # F: 거래처
            tx['supply_price'],           # G: 공급가액
            f'=IF(G{row_num}="","",G{row_num}*0.1)',  # H: 부가세 (수식)
            f'=IF(G{row_num}="","",G{row_num}+H{row_num})',  # I: 합계 (수식)
            '네이버페이',                  # J: 결제수단
            '전자영수증',                  # K: 증빙
            tx['product_name'][:100]       # L: 비고 (상품명 전체)
        ]
        
        rows_to_add.append(row)
        
        img_status = "🖼️" if thumbnail_url else "  "
        print(f"{i+1}. {img_status} {tx['date']} | {tx['merchant']} | {tx['detail']}")
        print(f"   → {tx['price']:,}원 ({tx['category']})")
    
    # 한번에 추가
    range_notation = f'A{next_row}:L{next_row + len(rows_to_add) - 1}'
    worksheet.update(rows_to_add, range_notation, value_input_option='USER_ENTERED')
    
    return len(rows_to_add)

def main():
    html_file = "/Users/yunseong-geun/Downloads/네이버페이.html"
    
    print("🔍 네이버페이 HTML 파싱 중...\n")
    
    # HTML 파싱
    transactions = parse_naverpay_html(html_file)
    
    if not transactions:
        print("❌ 거래 내역을 찾을 수 없습니다")
        return
    
    print(f"✅ {len(transactions)}건의 거래 내역 발견\n")
    
    # 미리보기
    print("=" * 70)
    print("📋 파싱된 거래 내역:")
    print("=" * 70)
    for i, tx in enumerate(transactions, 1):
        print(f"\n{i}. {tx['date']} | {tx['merchant']}")
        print(f"   상품: {tx['product_name']}")
        print(f"   금액: {tx['price']:,}원")
        print(f"   분류: {tx['category']} > {tx['detail']}")
    
    print("\n" + "=" * 70)
    
    # 현금흐름장부에 추가
    print("\n📊 현금흐름장부에 입력 중...")
    
    count = add_to_cashflow(transactions)
    
    print("\n" + "=" * 70)
    print("🎉 현금흐름장부 입력 완료!")
    print("=" * 70)
    print(f"\n✅ 총 {count}건의 거래 내역이 입력되었습니다")
    print(f"\n📎 시트 URL:")
    print(f"   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}\n")
    print("💡 현금흐름장부 시트에서 확인하세요!")
    print("   대분류가 잘못된 경우 드롭다운에서 수정 가능합니다.\n")

if __name__ == "__main__":
    main()

