#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
현금흐름장부에서 이미지가 있는 행만 높이 조정
"""

import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
import os

def get_credentials():
    """OAuth 인증 정보 가져오기"""
    creds = None
    token_path = '/Users/yunseong-geun/Projects/raspberry-pi-gym-controller/instance/sheets_token.pickle'
    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
    
    return creds

def main():
    print("=" * 80)
    print("현금흐름장부 이미지 행 높이 조정")
    print("=" * 80)
    
    # 인증
    creds = get_credentials()
    gc = gspread.authorize(creds)
    
    # 스프레드시트 열기
    spreadsheet = gc.open('ZEROLANE [스타트업 실전형] 현금흐름 장부 - 2025년 12월')
    worksheet = spreadsheet.worksheet('현금흐름장부')
    print(f"✅ 시트 열림: 현금흐름장부")
    
    # E열(상품이미지 열) 데이터 가져오기
    # get_all_values()는 수식이 아닌 표시값을 가져오므로, 
    # 대신 col_values로 E열 전체를 가져옵니다
    e_column_values = worksheet.col_values(5)  # E열 (1-based index 5)
    
    # 이미지가 있는 행 찾기 (E열에 값이 있는 행)
    image_rows = []
    for i, value in enumerate(e_column_values[1:], start=2):  # 헤더(1행) 제외, 2행부터
        if value and value.strip():  # 빈 문자열이 아닌 경우
            image_rows.append(i)
    
    print(f"\n이미지가 있는 행: {len(image_rows)}개")
    print(f"행 번호: {image_rows}")
    
    if not image_rows:
        print("\n⚠️ 이미지가 있는 행이 없습니다.")
        return
    
    # 행 높이 조정 요청 생성
    requests = []
    
    for row_num in image_rows:
        # 각 행의 높이를 80px로 설정 (기본 21px의 약 3.8배)
        requests.append({
            'updateDimensionProperties': {
                'range': {
                    'sheetId': worksheet.id,
                    'dimension': 'ROWS',
                    'startIndex': row_num - 1,  # 0-based
                    'endIndex': row_num
                },
                'properties': {
                    'pixelSize': 80
                },
                'fields': 'pixelSize'
            }
        })
    
    # 한번에 업데이트
    if requests:
        spreadsheet.batch_update({'requests': requests})
        print(f"\n✅ {len(image_rows)}개 행의 높이를 80px로 조정 완료!")
    
    print("\n" + "=" * 80)
    print("✅ 작업 완료!")
    print("=" * 80)
    print(f"\n📎 시트에서 확인하세요:")
    print(f"   https://docs.google.com/spreadsheets/d/{spreadsheet.id}")

if __name__ == '__main__':
    main()

