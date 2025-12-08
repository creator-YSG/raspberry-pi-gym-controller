#!/usr/bin/env python3
"""
NFC 태그 자동 등록 스크립트
S02, M02, F01 순서로 자동 등록

사용법:
python3 scripts/nfc_auto_register.py

ESP32에서 NFC 태그가 감지되면 자동으로 순서대로 등록됩니다.
"""

import asyncio
import json
import sqlite3
import sys
import os
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.nfc_service import NFCService
from hardware.protocol_handler import ProtocolHandler

class NFCAutoRegister:
    def __init__(self):
        self.nfc_service = NFCService()
        self.protocol_handler = ProtocolHandler()
        
        # 등록할 락커 순서
        self.target_lockers = ["S02", "M02", "F01"]
        self.current_index = 0
        self.registered_count = 0
        
        print("🔖 NFC 태그 자동 등록 시스템 시작")
        print(f"📋 등록 대상: {' → '.join(self.target_lockers)}")
        print("=" * 50)

    def get_current_locker(self):
        """현재 등록할 락커 반환"""
        if self.current_index < len(self.target_lockers):
            return self.target_lockers[self.current_index]
        return None

    async def register_nfc_uid(self, nfc_uid: str):
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

    async def handle_nfc_event(self, event_data):
        """NFC 이벤트 처리"""
        nfc_uid = event_data.get('nfc_uid')
        if not nfc_uid:
            return
        
        # UID 정규화 (대문자, 공백 제거)
        nfc_uid = nfc_uid.strip().upper()
        
        # 등록 처리
        completed = await self.register_nfc_uid(nfc_uid)
        if completed:
            return True  # 모든 등록 완료
        
        return False

    async def start_monitoring(self):
        """ESP32 NFC 이벤트 모니터링 시작"""
        print("👂 ESP32 NFC 이벤트 대기 중...")
        
        try:
            # ESP32 연결 시도
            connected = await self.protocol_handler.connect()
            if not connected:
                print("❌ ESP32 연결 실패")
                return
            
            print("✅ ESP32 연결 성공")
            print(f"📍 현재 등록 대기: {self.get_current_locker()}")
            print("💡 NFC 태그를 ESP32에 가져다 대세요...")
            
            # 이벤트 루프
            while self.current_index < len(self.target_lockers):
                try:
                    # ESP32에서 이벤트 수신
                    event_data = await asyncio.wait_for(
                        self.protocol_handler.receive_event(), 
                        timeout=1.0
                    )
                    
                    if event_data and event_data.get('type') == 'nfc_detected':
                        completed = await self.handle_nfc_event(event_data)
                        if completed:
                            break
                            
                except asyncio.TimeoutError:
                    # 타임아웃은 정상 (1초마다 체크)
                    continue
                except KeyboardInterrupt:
                    print("\n👋 사용자 중단")
                    break
                except Exception as e:
                    print(f"⚠️  이벤트 처리 오류: {e}")
                    await asyncio.sleep(1)
        
        finally:
            await self.protocol_handler.disconnect()
            print("🔌 ESP32 연결 해제")

def main():
    """메인 실행 함수"""
    print("🎯 NFC 태그 자동 등록 시작")
    
    try:
        # 현재 등록 상태 확인
        auto_register = NFCAutoRegister()
        
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
        print("\nCtrl+C로 종료할 수 있습니다.")
        
        # 비동기 모니터링 시작
        asyncio.run(auto_register.start_monitoring())
        
    except KeyboardInterrupt:
        print("\n👋 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()