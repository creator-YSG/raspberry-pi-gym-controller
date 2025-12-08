#!/usr/bin/env python3
"""
NFC 태그 실시간 모니터링 및 등록 스크립트
S02, M02, F01 순서로 자동 등록

ESP32 시리얼 출력을 모니터링하여 NFC 태그 자동 등록
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

class NFCMonitorRegister:
    def __init__(self):
        self.nfc_service = NFCService()
        
        # 등록할 락커 순서
        self.target_lockers = ["S02", "M02", "F01"]
        self.current_index = 0
        self.registered_count = 0
        
        # ESP32 시리얼 포트 설정
        self.serial_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2']
        self.serial_conn = None
        
        print("🔖 NFC 태그 실시간 등록 시스템")
        print(f"📋 등록 순서: {' → '.join(self.target_lockers)}")
        print("=" * 50)

    def get_current_locker(self):
        """현재 등록할 락커 반환"""
        if self.current_index < len(self.target_lockers):
            return self.target_lockers[self.current_index]
        return None

    def find_esp32_port(self):
        """사용 가능한 ESP32 포트 찾기"""
        for port in self.serial_ports:
            try:
                print(f"🔍 ESP32 포트 확인: {port}")
                test_conn = serial.Serial(port, 115200, timeout=0.5)
                test_conn.close()
                return port
            except Exception as e:
                continue
        return None

    def connect_esp32(self):
        """ESP32 시리얼 연결"""
        port = self.find_esp32_port()
        if not port:
            print("❌ 사용 가능한 ESP32 포트가 없습니다")
            return False
        
        try:
            print(f"🔌 ESP32 연결: {port}")
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
            print(f"❌ ESP32 연결 실패: {e}")
            return False

    def register_nfc_uid(self, nfc_uid: str):
        """NFC UID를 현재 락커에 등록"""
        current_locker = self.get_current_locker()
        if not current_locker:
            print("✅ 모든 락커 등록이 완료되었습니다!")
            return True

        print(f"\n🔖 NFC 감지: {nfc_uid}")
        print(f"📍 등록 대상: {current_locker}")
        
        # 이미 등록된 UID인지 확인
        existing_locker = self.nfc_service.get_locker_by_nfc_uid(nfc_uid)
        if existing_locker:
            print(f"⚠️  이미 등록된 UID: {nfc_uid} → {existing_locker}")
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
                print(f"👉 다음: {next_locker} 태그를 ESP32에 대세요")
            else:
                print("\n🎉 모든 NFC 태그 등록 완료!")
                self.print_final_summary()
                return True  # 완료 신호
        else:
            print(f"❌ 등록 실패: {result.get('error', '알 수 없는 오류')}")
        
        return False

    def parse_esp32_message(self, line):
        """ESP32 메시지에서 NFC UID 추출"""
        line = line.strip()
        if not line:
            return None
        
        try:
            # JSON 메시지 파싱
            if line.startswith('{') and line.endswith('}'):
                data = json.loads(line)
                if (data.get('message_type') == 'event' and 
                    data.get('event_type') == 'nfc_scanned'):
                    nfc_uid = data.get('data', {}).get('nfc_uid')
                    if nfc_uid:
                        return nfc_uid.strip().upper()
        except:
            pass
        
        # 단순 텍스트에서 NFC UID 패턴 찾기
        if '[NFC] UID:' in line:
            parts = line.split('[NFC] UID:')
            if len(parts) > 1:
                return parts[1].strip().upper()
        
        # 16진수 패턴 찾기
        if 'nfc' in line.lower() or 'uid' in line.lower():
            import re
            hex_pattern = r'[0-9A-Fa-f]{8,}'
            matches = re.findall(hex_pattern, line)
            if matches:
                return matches[0].upper()
        
        return None

    def print_final_summary(self):
        """최종 등록 결과 요약"""
        print("\n" + "=" * 50)
        print("📋 최종 등록 결과")
        print("=" * 50)
        
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

    def start_monitoring(self):
        """ESP32 시리얼 모니터링 시작"""
        if not self.connect_esp32():
            return
        
        print("👂 ESP32 NFC 메시지 모니터링 시작...")
        print(f"📍 현재 등록 대기: {self.get_current_locker()}")
        print("💡 NFC 태그를 ESP32 리더에 가져다 대세요")
        print("🛑 Ctrl+C로 종료\n")
        
        last_uid = None
        last_time = 0
        
        try:
            while self.current_index < len(self.target_lockers):
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        if not line.strip():
                            continue
                        
                        # 디버그: 모든 메시지 출력
                        print(f"📡 ESP32: {line.strip()}")
                        
                        # NFC UID 추출
                        nfc_uid = self.parse_esp32_message(line)
                        if not nfc_uid:
                            continue
                        
                        # 중복 방지 (2초 이내 같은 UID 무시)
                        current_time = time.time()
                        if nfc_uid == last_uid and (current_time - last_time) < 2.0:
                            continue
                        
                        last_uid = nfc_uid
                        last_time = current_time
                        
                        # 등록 처리
                        completed = self.register_nfc_uid(nfc_uid)
                        if completed:
                            break
                            
                    except Exception as e:
                        print(f"⚠️  메시지 처리 오류: {e}")
                
                time.sleep(0.1)  # CPU 사용량 줄이기
        
        except KeyboardInterrupt:
            print("\n👋 사용자 중단")
        finally:
            if self.serial_conn:
                self.serial_conn.close()
                print("🔌 ESP32 연결 해제")

def main():
    """메인 실행 함수"""
    print("🎯 NFC 태그 실시간 등록 시작")
    
    try:
        monitor = NFCMonitorRegister()
        
        # 이미 등록된 락커 확인
        registered_already = []
        for locker in monitor.target_lockers:
            try:
                conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
                cursor = conn.cursor()
                cursor.execute('SELECT nfc_uid FROM locker_status WHERE locker_number = ?', (locker,))
                result = cursor.fetchone()
                if result and result[0]:
                    registered_already.append(f"{locker}: {result[0]}")
                    monitor.current_index += 1
                conn.close()
            except Exception as e:
                print(f"❌ 상태 확인 오류: {e}")
        
        if registered_already:
            print("\n📋 이미 등록된 락커:")
            for info in registered_already:
                print(f"  ✅ {info}")
        
        if monitor.current_index >= len(monitor.target_lockers):
            print("🎉 모든 락커가 이미 등록되어 있습니다!")
            monitor.print_final_summary()
            return
        
        print(f"\n📍 현재 등록 대기: {monitor.get_current_locker()}")
        
        # 모니터링 시작
        monitor.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n👋 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()