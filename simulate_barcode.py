#!/usr/bin/env python3
"""
바코드 스캔 시뮬레이터 - 큐에 직접 데이터 주입
"""
import requests
import sys
import time

def inject_barcode_to_queue(barcode):
    """Flask 서버의 바코드 큐에 데이터 주입"""
    url = 'http://localhost:5000/api/test/inject-barcode'
    
    try:
        response = requests.post(url, json={'barcode': barcode})
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 바코드 큐 주입 성공: {barcode}")
            print(f"   {result}")
            return True
        else:
            print(f"❌ 바코드 큐 주입 실패: {response.status_code}")
            print(f"   {response.text}")
            return False
    except Exception as e:
        print(f"❌ 오류: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        barcode = sys.argv[1]
    else:
        # 기본값: 등록된 회원 (홍길동)
        barcode = "20240756"
    
    print(f"📱 바코드 스캔 시뮬레이션: {barcode}")
    print(f"=" * 60)
    
    if inject_barcode_to_queue(barcode):
        print(f"\n💡 화면을 확인하세요!")
        print(f"   Home → Processing...")
    else:
        print(f"\n💡 API 엔드포인트를 추가해야 합니다.")
        print(f"   대신 ESP32 시뮬레이터를 사용하세요.")

