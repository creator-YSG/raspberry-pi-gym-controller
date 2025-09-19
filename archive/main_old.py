#!/usr/bin/env python3
"""
라즈베리파이 락카키 대여기 메인 실행 파일

ESP32와 시리얼 통신하며 터치스크린 GUI로 락카키 대여/반납을 관리
구글시트로 회원 정보와 대여 기록을 관리
"""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from core.esp32_manager import create_default_esp32_manager
from data_sources.google_sheets import GoogleSheetsManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LockerSystemApp:
    """락카키 대여기 메인 애플리케이션"""
    
    def __init__(self, test_mode=False, debug=False):
        self.test_mode = test_mode
        self.debug = debug
        
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # 핵심 컴포넌트들
        self.esp32_manager = None
        self.google_sheets = None
        self.gui_controller = None
        
        # 상태
        self.running = False
        
    async def initialize(self):
        """시스템 초기화"""
        logger.info("🎯 라즈베리파이 락카키 대여기 시스템 초기화")
        
        try:
            # ESP32 매니저 초기화
            self.esp32_manager = create_default_esp32_manager()
            
            # 이벤트 핸들러 등록
            self.esp32_manager.register_event_handler("barcode_scanned", self._handle_barcode_scan)
            self.esp32_manager.register_event_handler("qr_scanned", self._handle_qr_scan)
            
            # ESP32 디바이스들 연결
            if await self.esp32_manager.connect_all_devices():
                logger.info("✅ ESP32 디바이스 연결 성공")
            else:
                logger.warning("⚠️ 일부 ESP32 디바이스 연결 실패")
            
            # 구글시트 연결 (선택적)
            try:
                credentials_file = project_root / "config" / "google_credentials.json"
                if credentials_file.exists():
                    # 실제 구글시트 ID는 설정 파일에서 읽어야 함
                    sheet_id = "your_google_sheet_id_here"
                    self.google_sheets = GoogleSheetsManager(str(credentials_file), sheet_id)
                    
                    if await self.google_sheets.connect():
                        logger.info("✅ 구글시트 연결 성공")
                    else:
                        logger.warning("⚠️ 구글시트 연결 실패 - 오프라인 모드")
                else:
                    logger.info("📄 구글 인증 파일 없음 - 로컬 모드")
            except Exception as e:
                logger.error(f"구글시트 초기화 실패: {e}")
            
            # TODO: GUI 컨트롤러 초기화
            # self.gui_controller = GUIController(self.esp32_manager, self.google_sheets)
            
            logger.info("🚀 시스템 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 시스템 초기화 실패: {e}")
            return False
    
    async def _handle_barcode_scan(self, event_data):
        """바코드 스캔 이벤트 처리"""
        logger.info(f"📱 바코드 스캔: {event_data}")
        
        # 회원 바코드인지 락카키 바코드인지 판단하여 처리
        barcode = event_data.get("barcode", "")
        
        if self.google_sheets:
            # 회원 확인 시도
            member = await self.google_sheets.validate_member(barcode)
            if member:
                logger.info(f"👤 유효한 회원: {member.name}")
                # TODO: 락카 선택 화면 표시
                return
            
            # 락카키 반납 시도
            rental_record = await self.google_sheets.process_return(barcode)
            if rental_record:
                logger.info(f"🔑 락카키 반납: {rental_record.locker_id}")
                # TODO: 락카 열기 명령 전송
                await self._open_locker(rental_record.locker_id)
                return
        
        logger.warning(f"❓ 인식되지 않은 바코드: {barcode}")
    
    async def _handle_qr_scan(self, event_data):
        """QR 코드 스캔 이벤트 처리"""
        logger.info(f"📲 QR 코드 스캔: {event_data}")
        # TODO: QR 코드 처리 로직 구현
    
    async def _open_locker(self, locker_id: str):
        """락카 열기"""
        # 락카 ID를 기반으로 적절한 ESP32 모터 컨트롤러 선택
        if locker_id.startswith("A"):
            device_id = "esp32_motor1"
        elif locker_id.startswith("B"):
            device_id = "esp32_motor2"
        else:
            device_id = "esp32_motor1"  # 기본값
        
        success = await self.esp32_manager.send_command(
            device_id, "OPEN_LOCKER", 
            locker_id=locker_id, duration_ms=3000
        )
        
        if success:
            logger.info(f"🔓 락카 열기 성공: {locker_id}")
        else:
            logger.error(f"❌ 락카 열기 실패: {locker_id}")
    
    async def run(self):
        """메인 실행 루프"""
        if not await self.initialize():
            logger.error("초기화 실패로 종료")
            return False
        
        self.running = True
        
        try:
            # ESP32 통신 시작
            await self.esp32_manager.start_communication()
            
            if self.test_mode:
                logger.info("🧪 테스트 모드 - 10초 후 종료")
                await asyncio.sleep(10)
            else:
                logger.info("🔄 메인 루프 시작 - Ctrl+C로 종료")
                # TODO: GUI 메인 루프 실행
                # await self.gui_controller.run()
                
                # 임시: 무한 루프
                while self.running:
                    await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("👋 사용자 종료 요청")
        except Exception as e:
            logger.error(f"❌ 실행 중 오류: {e}")
        finally:
            await self.shutdown()
        
        return True
    
    async def shutdown(self):
        """시스템 종료"""
        logger.info("🔄 시스템 종료 중...")
        
        self.running = False
        
        if self.esp32_manager:
            await self.esp32_manager.stop_communication()
            await self.esp32_manager.disconnect_all_devices()
        
        # TODO: GUI 종료
        # if self.gui_controller:
        #     await self.gui_controller.shutdown()
        
        logger.info("✅ 시스템 종료 완료")


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='라즈베리파이 락카키 대여기 시스템')
    parser.add_argument('--test-mode', action='store_true', help='테스트 모드로 실행')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')
    
    args = parser.parse_args()
    
    print("🎯 라즈베리파이 락카키 대여기 시스템")
    print("=" * 50)
    
    app = LockerSystemApp(test_mode=args.test_mode, debug=args.debug)
    success = await app.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 프로그램 종료")
        sys.exit(0)
