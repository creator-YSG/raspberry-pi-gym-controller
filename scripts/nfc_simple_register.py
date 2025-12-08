#!/usr/bin/env python3
"""
NFC 태그 간단 자동 등록 스크립트
S02, M02, F01 순서로 자동 등록

사용법:
python3 scripts/nfc_simple_register.py

ESP32에서 NFC 태그 감지 시 자동으로 순서대로 등록
"""

import sqlite3
import sys
import json
import serial
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.nfc_service import NFCService

class NFCSimpleRegister:
    def __init__(self):
        self.nfc_service = NFCService()
        
        # 등록할 락커 순서
        self.target_lockers = ["S02", "M02", "F01"]
        self.current_index = 0
        self.registered_count = 0
        
        # ESP32 시리얼 포트 설정
        self.serial_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2']
        self.serial_conn = None
        
        print("🔖 NFC 태그 자동 등록 시스템 시작")
        print(f"📋 등록 대상: {' → '.join(self.target_lockers)}")
        print("=" * 50)

    def get_current_locker(self):
        """현재 등록할 락커 반환"""
        if self.current_index < len(self.target_lockers):
            return self.target_lockers[self.current_index]
        return None

    def connect_esp32(self):
        """ESP32 시리얼 연결"""
        for port in self.serial_ports:
            try:
                print(f"🔌 ESP32 연결 시도: {port}")
                self.serial_conn = serial.Serial(
                    port, 
                    115200, 
                    timeout=1.0,
                    write_timeout=1.0
                )
                time.sleep(2)  # ESP32 부팅 대기
                print(f"✅ ESP32 연결 성공: {port}")
                return True
            except Exception as e:
                print(f"❌ {port} 연결 실패: {e}")
                continue
        
        print("❌ 모든 ESP32 포트 연결 실패")
        return False

    def register_nfc_uid(self, nfc_uid: str):
        """NFC UID를 현재 락커에 등록"""
        current_locker = self.get_current_locker()
        if not current_locker:
            print("❌ 모든 락커 등록이 완료되었습니다!")
            return False

        print(f"\n🔖 NFC 감지: {nfc_uid}")
        print(f"📍 등록 대상: {current_locker}")
        
        # 이미 등록된 UID인지 확인
        existing_locker = self.nfc_service.get_locker_by_nfc_uid(nfc_uid)
        if existing_locker:
            print(f"⚠️  이미 등록된 UID입니다: {nfc_uid} → {existing_locker}")
            return False

        # NFC UID 등록
        result = self.nfc_service.register_nfc_tag(current_locker, nfc_uid)
        
        if result.get('success'):
            self.current_index += 1
            self.registered_count += 1
            print(f"✅ 등록 성공: {current_locker} → {nfc_uid}")
            print(f"📊 진행률: {self.registered_count}/{len(self.target_lockers)}")
            
            if self.current_index < len(self.target_lockers):
                next_locker = self.target_lockers[self.current_index]
                print(f"👉 다음 등록 대상: {next_locker}")
                print("💡 다음 NFC 태그를 ESP32에 가져다 대세요...")
            else:
                print("\n🎉 모든 NFC 태그 등록 완료!")
                self.print_final_summary()
                return True  # 완료 신호
        else:
            print(f"❌ 등록 실패: {result.get('error', '알 수 없는 오류')}")
        
        return False

    def print_final_summary(self):
        """최종 등록 결과 요약"""
        print("\n" + "=" * 50)
        print("📋 최종 등록 결과")
        print("=" * 50)
        
        # 등록된 NFC 태그 확인
        try:
            conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
            cursor = conn.cursor()
            
            for locker in self.target_lockers:
                cursor.execute('SELECT nfc_uid FROM locker_status WHERE locker_number = ?', (locker,))
                result = cursor.fetchone()
                if result and result[0]:
                    print(f"✅ {locker}: {result[0]}")
                else:
                    print(f"❌ {locker}: 미등록")
            
            conn.close()
        except Exception as e:
            print(f"❌ 확인 중 오류: {e}")
        
        print("=" * 50)

    def parse_serial_data(self, line):
        """시리얼 데이터에서 NFC UID 추출"""
        try:
            # JSON 파싱 시도
            data = json.loads(line)
            if 'nfc_uid' in data:
                return data['nfc_uid'].strip().upper()
        except:
            pass
        
        # 단순 텍스트에서 NFC UID 패턴 찾기
        line = line.strip()
        
        # [NFC] UID: XXXXXXXX 형태
        if '[NFC] UID:' in line:
            parts = line.split('[NFC] UID:')
            if len(parts) > 1:
                return parts[1].strip().upper()
        
        # NFC UID: XXXXXXXX 형태
        if 'NFC UID:' in line or 'nfc_uid' in line.lower():
            # 16진수 패턴 찾기 (4자리 이상)
            import re
            hex_pattern = r'[0-9A-Fa-f]{8,}'
            matches = re.findall(hex_pattern, line)
            if matches:
                return matches[0].upper()
        
        return None

    def start_monitoring(self):
        """ESP32 시리얼 모니터링 시작"""
        if not self.connect_esp32():
            return
        
        print("👂 ESP32 NFC 이벤트 대기 중...")
        print(f"📍 현재 등록 대기: {self.get_current_locker()}")
        print("💡 NFC 태그를 ESP32에 가져다 대세요...")
        print("\nCtrl+C로 종료")
        
        last_uid = None
        last_time = 0
        
        try:
            while self.current_index < len(self.target_lockers):
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        if not line.strip():
                            continue
                        
                        # NFC UID 추출
                        nfc_uid = self.parse_serial_data(line)
                        if not nfc_uid:
                            continue
                        
                        # 중복 방지 (1초 이내 같은 UID 무시)
                        current_time = time.time()
                        if nfc_uid == last_uid and (current_time - last_time) < 1.0:
                            continue
                        
                        last_uid = nfc_uid
                        last_time = current_time
                        
                        # 등록 처리
                        completed = self.register_nfc_uid(nfc_uid)
                        if completed:
                            break
                            
                    except Exception as e:
                        print(f"⚠️  데이터 처리 오류: {e}")
                
                time.sleep(0.1)  # CPU 사용량 줄이기
        
        except KeyboardInterrupt:
            print("\n👋 사용자 중단")
        finally:
            if self.serial_conn:
                self.serial_conn.close()
                print("🔌 시리얼 연결 해제")

def main():
    """메인 실행 함수"""
    print("🎯 NFC 태그 자동 등록 시작")
    
    try:
        # 현재 등록 상태 확인
        auto_register = NFCSimpleRegister()
        
        # 이미 등록된 락커 확인
        registered_already = []
        for locker in auto_register.target_lockers:
            try:
                conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
                cursor = conn.cursor()
                cursor.execute('SELECT nfc_uid FROM locker_status WHERE locker_number = ?', (locker,))
                result = cursor.fetchone()
                if result and result[0]:
                    registered_already.append(f"{locker}: {result[0]}")
                    auto_register.current_index += 1
                conn.close()
            except Exception as e:
                print(f"❌ 상태 확인 오류: {e}")
        
        if registered_already:
            print("\n📋 이미 등록된 락커:")
            for info in registered_already:
                print(f"  ✅ {info}")
        
        if auto_register.current_index >= len(auto_register.target_lockers):
            print("🎉 모든 락커가 이미 등록되어 있습니다!")
            auto_register.print_final_summary()
            return
        
        print(f"\n📍 현재 등록 대기: {auto_register.get_current_locker()}")
        
        # 시리얼 모니터링 시작
        auto_register.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n👋 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()