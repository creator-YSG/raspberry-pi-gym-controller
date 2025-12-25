#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
현금흐름장부에 상품 이미지 열 추가 및 이미지 업로드
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
import os
import json
from pathlib import Path

# OAuth 인증 (사용자 계정)
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

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
        else:
            raise Exception("인증 토큰이 없습니다!")
    
    return creds

def create_drive_folder(drive_service, folder_name, parent_id=None):
    """구글 드라이브에 폴더 생성"""
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    if parent_id:
        file_metadata['parents'] = [parent_id]
    
    folder = drive_service.files().create(body=file_metadata, fields='id').execute()
    print(f"✅ 폴더 생성: {folder_name} (ID: {folder.get('id')})")
    return folder.get('id')

def find_or_create_folder(drive_service, folder_name, parent_id=None):
    """폴더 찾기 또는 생성"""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    
    if items:
        print(f"✅ 기존 폴더 발견: {folder_name} (ID: {items[0]['id']})")
        return items[0]['id']
    else:
        return create_drive_folder(drive_service, folder_name, parent_id)

def upload_image_to_drive(drive_service, file_path, folder_id):
    """이미지 파일을 구글 드라이브에 업로드"""
    file_name = os.path.basename(file_path)
    
    # 이미 업로드된 파일이 있는지 확인
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name, webViewLink)").execute()
    items = results.get('files', [])
    
    if items:
        file_id = items[0]['id']
        print(f"   이미 존재: {file_name}")
    else:
        # 업로드
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        file_id = file.get('id')
        print(f"   업로드 완료: {file_name}")
    
    # 공개 권한 설정 (누구나 볼 수 있음)
    permission = {
        'type': 'anyone',
        'role': 'reader'
    }
    drive_service.permissions().create(
        fileId=file_id,
        body=permission
    ).execute()
    
    # 썸네일 URL 생성 (구글 드라이브 이미지 직접 링크)
    thumbnail_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w200"
    
    return file_id, thumbnail_url

def insert_column_after(worksheet, column_letter):
    """특정 열 뒤에 새 열 삽입"""
    # 열 문자를 숫자로 변환 (A=1, B=2, ...)
    col_num = ord(column_letter.upper()) - ord('A') + 1
    
    # 다음 열에 빈 열 삽입
    worksheet.insert_cols([['']] * worksheet.row_count, col=col_num + 1)
    print(f"✅ {column_letter}열 뒤에 새 열 삽입 완료")

def main():
    print("=" * 80)
    print("현금흐름장부 이미지 열 추가 작업 시작")
    print("=" * 80)
    
    # 1. 인증
    creds = get_credentials()
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    
    # 2. 스프레드시트 열기
    spreadsheet = gc.open('ZEROLANE [스타트업 실전형] 현금흐름 장부 - 2025년 12월')
    worksheet = spreadsheet.worksheet('현금흐름장부')
    print(f"✅ 시트 열림: 현금흐름장부")
    
    # 3. 구글 드라이브에 폴더 구조 생성
    print("\n[구글 드라이브 폴더 생성]")
    evidence_folder_id = find_or_create_folder(drive_service, "증빙자료")
    image_folder_id = find_or_create_folder(drive_service, "상품이미지", evidence_folder_id)
    
    # 4. 로컬 이미지 파일들 업로드
    print("\n[이미지 업로드 중...]")
    images_dir = Path("/Users/yunseong-geun/Projects/raspberry-pi-gym-controller/네이버페이_files")
    image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
    
    # 실제로 HTML에서 참조된 이미지만 업로드 (네이버페이 HTML에서 추출)
    html_file = "/Users/yunseong-geun/Downloads/네이버페이.html"
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    import re
    json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', html_content, re.DOTALL)
    
    image_url_map = {}  # filename -> thumbnail_url 매핑
    
    if json_match:
        data = json.loads(json_match.group(1))
        items = data['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']['pages'][0]['items']
        
        referenced_images = set()
        for item in items:
            product = item.get('product', {})
            img_url = product.get('imgUrl', '')
            if img_url:
                filename = img_url.split('/')[-1]
                referenced_images.add(filename)
        
        print(f"   참조된 이미지 파일: {len(referenced_images)}개")
        
        # 참조된 이미지만 업로드
        uploaded_count = 0
        for filename in referenced_images:
            local_file = images_dir / filename
            if local_file.exists():
                try:
                    file_id, thumbnail_url = upload_image_to_drive(drive_service, str(local_file), image_folder_id)
                    image_url_map[filename] = thumbnail_url
                    uploaded_count += 1
                except Exception as e:
                    print(f"   ❌ 업로드 실패: {filename} - {e}")
        
        print(f"\n✅ 총 {uploaded_count}개 이미지 업로드 완료")
    
    # 5. 이미지 URL 매핑 저장
    mapping_file = "/Users/yunseong-geun/Projects/raspberry-pi-gym-controller/scripts/image_url_mapping.json"
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(image_url_map, f, ensure_ascii=False, indent=2)
    print(f"✅ 이미지 URL 매핑 저장: {mapping_file}")
    
    # 6. 현금흐름장부에 새 열 삽입 (D열 다음, 즉 새로운 E열)
    print("\n[시트에 이미지 열 추가]")
    insert_column_after(worksheet, 'D')
    
    # 7. 헤더 업데이트
    worksheet.update('E1', [['상품이미지']], value_input_option='RAW')
    print("✅ E열 헤더 설정: '상품이미지'")
    
    # 8. 열 너비 조정 (E열을 넓게)
    requests = [{
        'updateDimensionProperties': {
            'range': {
                'sheetId': worksheet.id,
                'dimension': 'COLUMNS',
                'startIndex': 4,  # E열 (0-based)
                'endIndex': 5
            },
            'properties': {
                'pixelSize': 120
            },
            'fields': 'pixelSize'
        }
    }]
    
    spreadsheet.batch_update({'requests': requests})
    print("✅ E열 너비 조정 완료 (120px)")
    
    print("\n" + "=" * 80)
    print("✅ 이미지 열 추가 완료!")
    print("=" * 80)
    print(f"\n구글 드라이브 폴더:")
    print(f"  - 증빙자료/상품이미지 (ID: {image_folder_id})")
    print(f"\n업로드된 이미지: {len(image_url_map)}개")
    print(f"\n이제 거래 입력 시 자동으로 상품 이미지가 표시됩니다!")

if __name__ == '__main__':
    main()

