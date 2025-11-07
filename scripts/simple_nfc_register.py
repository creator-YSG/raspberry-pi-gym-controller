#!/usr/bin/env python3
"""
간단한 NFC 태그 순차 등록 스크립트
S02 → M02 → F01 순서로 자동 등록
"""

import sqlite3
import sys
import json
import serial
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.nfc_service import NFCService

def register_nfc_uid(nfc_service, locker_number, nfc_uid):
    """NFC UID 등록"""
    print(f"\n🔖 NFC 감지: {nfc_uid}")
    print(f"📍 등록 대상: {locker_number}")
    
    # 이미 등록된 UID인지 확인
    existing = nfc_service.get_locker_by_nfc_uid(nfc_uid)
    if existing:
        print(f"⚠️  이미 등록됨: {nfc_uid} → {existing}")
        return False
    
    # 등록 실행
    result = nfc_service.register_nfc_tag(locker_number, nfc_uid)
    if result.get('success'):
        print(f"✅ 등록 성공: {locker_number} → {nfc_uid}")
        return True
    else:
        print(f"❌ 등록 실패: {result.get('error')}")
        return False

def extract_nfc_uid(line):
    """라인에서 NFC UID 추출"""
    line = line.strip()
    
    # JSON 메시지 파싱
    if line.startswith('{') and '}' in line:
        try:
            data = json.loads(line)
            if (data.get('event_type') == 'nfc_scanned' and 
                data.get('message_type') == 'event'):
                nfc_uid = data.get('data', {}).get('nfc_uid')
                if nfc_uid:
                    return nfc_uid.strip().upper()
        except:
            pass
    
    # 디버그 메시지 파싱
    if '[NFC] UID:' in line:
        parts = line.split('[NFC] UID:')
        if len(parts) > 1:
            uid = parts[1].strip().replace(' ', '').upper()
            return uid if len(uid) >= 8 else None
    
    return None

def connect_esp32():
    """ESP32 시리얼 연결"""
    ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2']
    
    for port in ports:
        try:
            print(f"🔍 포트 시도: {port}")
            conn = serial.Serial(port, 115200, timeout=1)
            time.sleep(1)
            print(f"✅ ESP32 연결: {port}")
            return conn
        except Exception as e:
            continue
    
    print("❌ ESP32 연결 실패")
    return None

def main():
    print("🎯 NFC 태그 순차 등록 시스템")
    print("📋 등록 순서: S02 → M02 → F01")
    print("=" * 40)
    
    # NFC 서비스 초기화
    nfc_service = NFCService()
    target_lockers = ["S02", "M02", "F01"]
    current_step = 0
    
    # 이미 등록된 상태 확인
    try:
        conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
        cursor = conn.cursor()
        
        for i, locker in enumerate(target_lockers):
            cursor.execute('SELECT nfc_uid FROM locker_status WHERE locker_number = ?', (locker,))
            result = cursor.fetchone()
            if result and result[0]:
                print(f"✅ 이미 등록됨: {locker} → {result[0]}")
                current_step = i + 1
        
        conn.close()
    except Exception as e:
        print(f"⚠️ 상태 확인 오류: {e}")
    
    if current_step >= len(target_lockers):
        print("🎉 모든 락커가 이미 등록되어 있습니다!")
        return
    
    # ESP32 연결
    ser = connect_esp32()
    if not ser:
        return
    
    print(f"\n📍 현재 대기: {target_lockers[current_step]}")
    print("💡 NFC 태그를 ESP32에 가져다 대세요")
    print("🛑 Ctrl+C로 종료\n")
    
    last_uid = None
    last_time = 0
    
    try:
        while current_step < len(target_lockers):
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore')
                    if not line.strip():
                        continue
                    
                    # 모든 ESP32 메시지 출력 (디버깅용)
                    print(f"📡 {line.strip()}")
                    
                    # NFC UID 추출
                    nfc_uid = extract_nfc_uid(line)
                    if not nfc_uid:
                        continue
                    
                    # 중복 방지 (2초 이내 같은 UID 무시)
                    now = time.time()
                    if nfc_uid == last_uid and (now - last_time) < 2.0:
                        continue
                    
                    last_uid = nfc_uid
                    last_time = now
                    
                    # 등록 처리
                    current_locker = target_lockers[current_step]
                    if register_nfc_uid(nfc_service, current_locker, nfc_uid):
                        current_step += 1
                        if current_step < len(target_lockers):
                            next_locker = target_lockers[current_step]
                            print(f"👉 다음: {next_locker} 태그를 대세요")
                        else:
                            print("\n🎉 모든 등록 완료!")
                            break
                
                except Exception as e:
                    print(f"⚠️ 처리 오류: {e}")
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\n👋 중단됨")
    finally:
        ser.close()
        print("🔌 연결 해제")
    
    # 최종 결과 확인
    print("\n" + "=" * 40)
    print("📋 최종 결과")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
        cursor = conn.cursor()
        
        for locker in target_lockers:
            cursor.execute('SELECT nfc_uid FROM locker_status WHERE locker_number = ?', (locker,))
            result = cursor.fetchone()
            uid = result[0] if result and result[0] else "미등록"
            print(f"{locker}: {uid}")
        
        conn.close()
    except Exception as e:
        print(f"❌ 결과 확인 오류: {e}")

if __name__ == "__main__":
    main()