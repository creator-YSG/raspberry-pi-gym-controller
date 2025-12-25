#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
현금흐름장부 데이터 행 높이 3배로 조정
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
    print("현금흐름장부 데이터 행 높이 조정 (3배)")
    print("=" * 80)
    
    # 인증
    creds = get_credentials()
    gc = gspread.authorize(creds)
    
    # 스프레드시트 열기
    spreadsheet = gc.open('ZEROLANE [스타트업 실전형] 현금흐름 장부 - 2025년 12월')
    worksheet = spreadsheet.worksheet('현금흐름장부')
    print(f"✅ 시트 열림: 현금흐름장부")
    
    # 전체 행 수 확인
    all_values = worksheet.get_all_values()
    total_rows = len(all_values)
    
    print(f"\n전체 {total_rows}행")
    print(f"데이터 행: 2~{total_rows}행 ({total_rows - 1}개)")
    
    if total_rows <= 1:
        print("\n⚠️ 데이터가 없습니다 (헤더만 있음)")
        return
    
    # 2행부터 마지막까지 모든 행의 높이를 80px로 설정 (기본 21px의 약 3.8배)
    request = {
        'updateDimensionProperties': {
            'range': {
                'sheetId': worksheet.id,
                'dimension': 'ROWS',
                'startIndex': 1,  # 2행 (0-based)
                'endIndex': total_rows  # 마지막 행까지
            },
            'properties': {
                'pixelSize': 80
            },
            'fields': 'pixelSize'
        }
    }
    
    # 업데이트
    spreadsheet.batch_update({'requests': [request]})
    print(f"\n✅ 2~{total_rows}행의 높이를 80px로 조정 완료! (약 3배)")
    
    print("\n" + "=" * 80)
    print("✅ 작업 완료!")
    print("=" * 80)
    print(f"\n📎 시트에서 확인하세요:")
    print(f"   https://docs.google.com/spreadsheets/d/{spreadsheet.id}")

if __name__ == '__main__':
    main()

