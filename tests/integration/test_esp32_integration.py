#!/usr/bin/env python3
"""
ESP32 통합 테스트 스크립트
실제 ESP32와 라즈베리파이 간 통신을 테스트
"""

import asyncio
import json
import logging
from core.esp32_manager import ESP32Manager
from hardware.protocol_handler import ProtocolHandler

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ESP32IntegrationTest:
    def __init__(self):
        self.esp32_manager = None
        self.protocol_handler = ProtocolHandler()
        
    async def setup(self):
        """테스트 환경 설정 - 자동 감지 사용"""
        print("🔧 ESP32 통합 테스트 시작")
        
        # ESP32 자동 감지 및 연결
        from core.esp32_manager import create_auto_esp32_manager
        
        self.esp32_manager = await create_auto_esp32_manager()
        
        if self.esp32_manager and len(self.esp32_manager.devices) > 0:
            print("✅ ESP32 자동 감지 및 연결 성공")
            
            # 이벤트 핸들러 등록
            self.esp32_manager.register_event_handler("barcode_scanned", self.handle_barcode_event)
            self.esp32_manager.register_event_handler("sensor_triggered", self.handle_sensor_event)
            self.esp32_manager.register_event_handler("motor_completed", self.handle_motor_event)
            self.esp32_manager.register_event_handler("device_status", self.handle_status_event)
            
            return True
        else:
            print("❌ ESP32 자동 감지 실패")
            return False
    
    async def handle_barcode_event(self, event_data):
        """바코드 스캔 이벤트 처리"""
        barcode = event_data.get("barcode", "unknown")
        device_id = event_data.get("device_id", "unknown")
        
        print(f"🔍 바코드 스캔됨: {barcode} (from {device_id})")
        
        # 여기서 실제 회원 검증 로직 호출 가능
        # member_valid = await self.validate_member(barcode)
        
        # 테스트: 3초 후 락카 열기 명령 전송
        await asyncio.sleep(3)
        await self.test_locker_open("A01")
    
    async def handle_sensor_event(self, event_data):
        """IR 센서 이벤트 처리"""
        chip_idx = event_data.get("chip_idx", "?")
        pin = event_data.get("pin", "?")
        active = event_data.get("active", False)
        
        print(f"📡 센서 감지: Chip{chip_idx} Pin{pin} = {'ACTIVE' if active else 'INACTIVE'}")
    
    async def handle_motor_event(self, event_data):
        """모터 완료 이벤트 처리"""
        action = event_data.get("action", "unknown")
        status = event_data.get("status", "unknown")
        
        print(f"⚙️ 모터 이벤트: {action} - {status}")
        
        if action == "rotate" and status == "completed":
            print("  → 모터 회전 완료, 락카 열림!")
    
    async def handle_status_event(self, event_data):
        """상태 이벤트 처리"""
        response_type = event_data.get("response_type", "unknown")
        
        if response_type == "status_response":
            print(f"📊 시스템 상태: {event_data.get('status', 'unknown')}")
            print(f"  - 업타임: {event_data.get('uptime_ms', 0)}ms")
            print(f"  - 스캔 횟수: {event_data.get('scanner', {}).get('total_scans', 0)}")
            print(f"  - 모터 이동: {event_data.get('motor', {}).get('total_moves', 0)}")
    
    async def test_locker_open(self, locker_id: str):
        """락카 열기 테스트"""
        print(f"🔓 락카 열기 명령 전송: {locker_id}")
        
        success = await self.esp32_manager.send_command(
            device_id="esp32_gym",
            command="OPEN_LOCKER",
            locker_id=locker_id,
            duration_ms=3000
        )
        
        if success:
            print(f"✅ 락카 열기 명령 전송 성공")
        else:
            print(f"❌ 락카 열기 명령 전송 실패")
    
    async def test_status_request(self):
        """상태 요청 테스트"""
        print("📊 상태 요청 전송")
        
        success = await self.esp32_manager.send_command(
            device_id="esp32_gym",
            command="GET_STATUS"
        )
        
        if success:
            print("✅ 상태 요청 전송 성공")
        else:
            print("❌ 상태 요청 전송 실패")
    
    async def test_auto_mode_toggle(self):
        """자동 모드 토글 테스트"""
        print("🔄 자동 모드 토글 테스트")
        
        # 자동 모드 비활성화
        await self.esp32_manager.send_command(
            device_id="esp32_gym",
            command="SET_AUTO_MODE",
            enabled=False
        )
        
        await asyncio.sleep(2)
        
        # 자동 모드 재활성화
        await self.esp32_manager.send_command(
            device_id="esp32_gym",
            command="SET_AUTO_MODE",
            enabled=True
        )
    
    async def run_tests(self):
        """전체 테스트 실행"""
        if not await self.setup():
            return
        
        try:
            print("\n🚀 통합 테스트 시작...")
            
            # 1. 상태 확인
            await self.test_status_request()
            await asyncio.sleep(2)
            
            # 2. 자동 모드 테스트
            await self.test_auto_mode_toggle()
            await asyncio.sleep(2)
            
            # 3. 수동 락카 열기 테스트
            await self.test_locker_open("A01")
            await asyncio.sleep(5)
            
            print("\n👀 바코드 스캔 대기 중... (30초)")
            print("ESP32에서 바코드를 스캔하면 자동으로 처리됩니다.")
            
            # 30초 동안 이벤트 대기
            await asyncio.sleep(30)
            
        except KeyboardInterrupt:
            print("\n⏹️ 사용자가 테스트를 중단했습니다.")
        except Exception as e:
            print(f"\n❌ 테스트 중 오류 발생: {e}")
        finally:
            print("\n🛑 통신 종료 중...")
            await self.esp32_manager.disconnect_all_devices()
            print("✅ 테스트 완료")

async def main():
    """메인 함수"""
    test = ESP32IntegrationTest()
    await test.run_tests()

if __name__ == "__main__":
    print("=" * 60)
    print("ESP32 + 라즈베리파이 통합 테스트")
    print("=" * 60)
    print()
    print("📋 테스트 항목:")
    print("  1. ESP32 연결 테스트")
    print("  2. 상태 요청/응답 테스트") 
    print("  3. 자동 모드 설정 테스트")
    print("  4. 락카 열기 명령 테스트")
    print("  5. 바코드 스캔 이벤트 처리 테스트")
    print("  6. IR 센서 이벤트 처리 테스트")
    print("  7. 모터 완료 이벤트 처리 테스트")
    print()
    print("⚠️ ESP32가 /dev/ttyUSB0에 연결되어 있는지 확인하세요!")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 안녕히 가세요!")
