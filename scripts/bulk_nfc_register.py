#!/usr/bin/env python3
"""
60개 NFC 태그 대량 순차 등록 시스템

사용법:
python3 bulk_nfc_register.py

등록 순서:
1. S01-S10 (10개, 직원)
2. M01-M40 (40개, 남성) 
3. F01-F10 (10개, 여성)

총 60개 락커에 NFC 태그를 순서대로 등록합니다.
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

class BulkNFCRegister:
    def __init__(self):
        self.nfc_service = NFCService()
        
        # 60개 락커 순서 정의
        self.locker_sequence = []
        
        # S01-S10 (직원)
        for i in range(1, 11):
            self.locker_sequence.append(f"S{i:02d}")
        
        # M01-M40 (남성)
        for i in range(1, 41):
            self.locker_sequence.append(f"M{i:02d}")
        
        # F01-F10 (여성)
        for i in range(1, 11):
            self.locker_sequence.append(f"F{i:02d}")
        
        self.current_index = 0
        self.registered_count = 0
        self.skipped_count = 0
        
        # ESP32 포트 설정
        self.serial_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2']
        self.serial_conn = None
        
        print("🔖 60개 NFC 태그 대량 등록 시스템")
        print("=" * 60)
        print(f"📋 등록 순서: S01-S10 → M01-M40 → F01-F10 (총 {len(self.locker_sequence)}개)")
        print("=" * 60)

    def get_current_locker(self):
        """현재 등록할 락커 반환"""
        if self.current_index < len(self.locker_sequence):
            return self.locker_sequence[self.current_index]
        return None

    def connect_esp32(self):
        """ESP32 시리얼 연결"""
        for port in self.serial_ports:
            try:
                print(f"🔍 ESP32 연결 시도: {port}")
                self.serial_conn = serial.Serial(port, 115200, timeout=1)
                time.sleep(1)
                print(f"✅ ESP32 연결 성공: {port}")
                return True
            except Exception as e:
                continue
        
        print("❌ ESP32 연결 실패 - 모든 포트 시도됨")
        return False

    def register_nfc_uid(self, nfc_uid: str):
        """NFC UID를 현재 락커에 등록"""
        current_locker = self.get_current_locker()
        if not current_locker:
            print("\n🎉 모든 60개 락커 등록이 완료되었습니다!")
            return True

        print(f"\n🔖 NFC 감지: {nfc_uid}")
        print(f"📍 등록 대상: {current_locker} [{self.current_index + 1}/60]")
        
        # 이미 등록된 UID인지 확인
        existing_locker = self.nfc_service.get_locker_by_nfc_uid(nfc_uid)
        if existing_locker:
            print(f"⚠️  이미 등록된 UID: {nfc_uid} → {existing_locker}")
            print("   🔄 다음 락커로 건너뜁니다...")
            return False

        # 현재 락커에 이미 다른 UID가 등록되어 있는지 확인
        try:
            conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
            cursor = conn.cursor()
            cursor.execute('SELECT nfc_uid FROM locker_status WHERE locker_number = ?', (current_locker,))
            existing_uid = cursor.fetchone()
            conn.close()
            
            if existing_uid and existing_uid[0]:
                print(f"⚠️  {current_locker}에 이미 UID 등록됨: {existing_uid[0]}")
                print("   🔄 다음 락커로 건너뜁니다...")
                self.skip_current_locker()
                return False
        except Exception as e:
            print(f"⚠️  상태 확인 오류: {e}")

        # NFC UID 등록
        result = self.nfc_service.register_nfc_tag(current_locker, nfc_uid)
        
        if result.get('success'):
            self.current_index += 1
            self.registered_count += 1
            print(f"✅ 등록 성공: {current_locker} → {nfc_uid}")
            self.print_progress()
            
            if self.current_index < len(self.locker_sequence):
                next_locker = self.locker_sequence[self.current_index]
                print(f"👉 다음: {next_locker} [{self.current_index + 1}/60] - NFC 태그를 대세요")
            else:
                print("\n🎉 모든 NFC 태그 등록 완료!")
                self.print_final_summary()
                return True  # 완료 신호
        else:
            print(f"❌ 등록 실패: {result.get('error', '알 수 없는 오류')}")
        
        return False

    def skip_current_locker(self):
        """현재 락커를 건너뛰고 다음으로 이동"""
        if self.current_index < len(self.locker_sequence):
            self.current_index += 1
            self.skipped_count += 1
            print(f"⏭️  건너뜀: {self.locker_sequence[self.current_index - 1]}")
            self.print_progress()

    def print_progress(self):
        """진행률 표시"""
        total = len(self.locker_sequence)
        processed = self.current_index
        percentage = (processed / total * 100) if total > 0 else 0
        
        print(f"📊 진행률: {processed}/{total} ({percentage:.1f}%)")
        print(f"   등록: {self.registered_count}개 | 건너뜀: {self.skipped_count}개")

    def extract_nfc_uid(self, line):
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
                return uid if len(uid) >= 6 else None
        
        return None

    def print_final_summary(self):
        """최종 등록 결과 요약"""
        print("\n" + "=" * 60)
        print("📋 60개 락커 대량 등록 최종 결과")
        print("=" * 60)
        
        try:
            conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
            cursor = conn.cursor()
            
            # 구역별 등록 현황
            zones = [('STAFF', 'S'), ('MALE', 'M'), ('FEMALE', 'F')]
            total_registered = 0
            
            for zone_name, prefix in zones:
                cursor.execute('''
                    SELECT COUNT(*) FROM locker_status 
                    WHERE locker_number LIKE ? AND nfc_uid IS NOT NULL
                ''', (f'{prefix}%',))
                count = cursor.fetchone()[0]
                total_registered += count
                
                if prefix == 'S':
                    expected = 10
                elif prefix == 'M':
                    expected = 40
                else:  # F
                    expected = 10
                
                percentage = (count / expected * 100) if expected > 0 else 0
                print(f"{zone_name:8}: {count:2d}/{expected:2d} ({percentage:5.1f}%)")
            
            print("-" * 40)
            print(f"전체:     {total_registered:2d}/60 ({total_registered/60*100:5.1f}%)")
            
            # 미등록 락커 목록 (간략히)
            cursor.execute('''
                SELECT locker_number FROM locker_status 
                WHERE nfc_uid IS NULL 
                ORDER BY locker_number
            ''')
            unregistered = [row[0] for row in cursor.fetchall()]
            
            if unregistered:
                print(f"\n⚠️  미등록 락커 ({len(unregistered)}개):")
                # 구역별로 그룹화해서 표시
                staff = [l for l in unregistered if l.startswith('S')]
                male = [l for l in unregistered if l.startswith('M')]
                female = [l for l in unregistered if l.startswith('F')]
                
                if staff:
                    print(f"   직원: {', '.join(staff)}")
                if male:
                    male_str = ', '.join(male[:10]) + ('...' if len(male) > 10 else '')
                    print(f"   남성: {male_str}")
                if female:
                    print(f"   여성: {', '.join(female)}")
            
            conn.close()
        except Exception as e:
            print(f"❌ 요약 생성 오류: {e}")
        
        print("=" * 60)

    def check_initial_status(self):
        """시작 전 현재 상태 확인"""
        print("\n📊 등록 시작 전 현재 상태")
        print("-" * 40)
        
        try:
            conn = sqlite3.connect('/home/pi/gym-controller/instance/gym_system.db')
            cursor = conn.cursor()
            
            already_registered = []
            for i, locker in enumerate(self.locker_sequence):
                cursor.execute('SELECT nfc_uid FROM locker_status WHERE locker_number = ?', (locker,))
                result = cursor.fetchone()
                if result and result[0]:
                    already_registered.append((i, locker, result[0]))
                    self.current_index = i + 1
            
            if already_registered:
                print(f"✅ 이미 등록된 락커: {len(already_registered)}개")
                for idx, locker, uid in already_registered[-5:]:  # 최근 5개만 표시
                    print(f"   {locker}: {uid}")
                if len(already_registered) > 5:
                    print(f"   ... 외 {len(already_registered) - 5}개")
            
            remaining = len(self.locker_sequence) - self.current_index
            print(f"⏳ 등록 대기 중: {remaining}개")
            
            if self.current_index < len(self.locker_sequence):
                next_locker = self.locker_sequence[self.current_index]
                print(f"📍 다음 등록 대상: {next_locker} [{self.current_index + 1}/60]")
            
            conn.close()
        except Exception as e:
            print(f"⚠️ 상태 확인 오류: {e}")
        
        print("-" * 40)

    def start_monitoring(self):
        """ESP32 시리얼 모니터링 시작"""
        if not self.connect_esp32():
            return
        
        print("👂 ESP32 NFC 메시지 모니터링 시작...")
        print("💡 NFC 태그를 ESP32에 순서대로 가져다 대세요")
        print("🛑 Ctrl+C로 종료\n")
        
        last_uid = None
        last_time = 0
        
        try:
            while self.current_index < len(self.locker_sequence):
                if self.serial_conn.in_waiting > 0:
                    try:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        if not line.strip():
                            continue
                        
                        # 디버깅: ESP32 메시지 표시 (선택적)
                        if '[NFC]' in line or '{"device_id"' in line:
                            print(f"📡 {line.strip()}")
                        
                        # NFC UID 추출
                        nfc_uid = self.extract_nfc_uid(line)
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
            print(f"\n👋 사용자 중단 (진행률: {self.current_index}/{len(self.locker_sequence)})")
        finally:
            if self.serial_conn:
                self.serial_conn.close()
                print("🔌 ESP32 연결 해제")

def main():
    """메인 실행 함수"""
    print("🎯 60개 락커 NFC 태그 대량 등록 시작")
    
    try:
        # 등록 시스템 초기화
        bulk_register = BulkNFCRegister()
        
        # 현재 상태 확인
        bulk_register.check_initial_status()
        
        if bulk_register.current_index >= len(bulk_register.locker_sequence):
            print("🎉 모든 락커가 이미 등록되어 있습니다!")
            bulk_register.print_final_summary()
            return
        
        print(f"\n시작하려면 Enter를 누르세요... (Ctrl+C로 취소)")
        input()
        
        # 모니터링 시작
        bulk_register.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n👋 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()