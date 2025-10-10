"""
라즈베리파이 하드웨어 컨트롤러 테스트

기본적인 하드웨어 기능 테스트 및 스텁 모드 검증
"""

import asyncio
import sys
import os

# 상위 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hardware.raspberry_hardware_controller import RaspberryHardwareController
from hardware.serial_scanner import SerialBarcodeScanner
from hardware.protocol_handler import ProtocolHandler
from hardware.barcode_utils import generate_member_barcode, validate_barcode_format


async def test_hardware_controller():
    """하드웨어 컨트롤러 기본 테스트"""
    print("🔧 라즈베리파이 하드웨어 컨트롤러 테스트 시작")
    
    # 컨트롤러 생성
    controller = RaspberryHardwareController.create_default()
    
    # 스캔 콜백 등록
    def on_scan(scan_type, data):
        print(f"📱 스캔 감지: {scan_type} = {data}")
    
    def on_status_change(status):
        print(f"🔄 상태 변경: {status.value}")
    
    controller.add_scan_callback(on_scan)
    controller.add_status_callback(on_status_change)
    
    try:
        # 컨트롤러 시작
        if await controller.start():
            print("✅ 컨트롤러 시작 성공")
            
            # 디바이스 상태 확인
            print(f"📊 디바이스 상태: {controller.device_status}")
            
            # 문 열기 테스트
            print("🚪 문 열기 테스트...")
            await controller.open_door(duration_ms=1000)
            
            # 락카 열기 테스트
            print("🔐 락카 열기 테스트...")
            await controller.open_locker("L001", duration_ms=1000)
            
            # 5초간 스캔 대기
            print("⏳ 5초간 스캔 대기...")
            await asyncio.sleep(5)
            
            # 통계 출력
            print(f"📈 통계: {controller.stats}")
            
        else:
            print("❌ 컨트롤러 시작 실패")
            
    finally:
        # 컨트롤러 정지
        await controller.stop()
        print("⏹️ 컨트롤러 정지 완료")


async def test_serial_scanner():
    """시리얼 스캐너 테스트"""
    print("\n📡 시리얼 스캐너 테스트 시작")
    
    scanner = SerialBarcodeScanner(auto_detect=True)
    
    try:
        if await scanner.connect():
            print("✅ 스캐너 연결 성공")
            
            # 5초간 스캔 데이터 읽기
            print("⏳ 5초간 스캔 데이터 읽기...")
            for i in range(50):  # 0.1초 간격으로 50회
                scan_data = await scanner.read_scan()
                if scan_data:
                    scan_type, data = scan_data
                    print(f"📱 스캔: {scan_type} = {data}")
                await asyncio.sleep(0.1)
            
            print(f"📈 스캐너 통계: {scanner.stats}")
            
        else:
            print("❌ 스캐너 연결 실패 (스텁 모드일 수 있음)")
            
    finally:
        await scanner.disconnect()
        print("⏹️ 스캐너 연결 해제 완료")


def test_protocol_handler():
    """프로토콜 핸들러 테스트"""
    print("\n📋 프로토콜 핸들러 테스트 시작")
    
    handler = ProtocolHandler()
    
    # 테스트 메시지들
    test_messages = [
        "QR:M20250001",
        "BARCODE:123456789",
        "123456789",  # 순수 바코드
        "STATUS:door=closed,scanner=ready",
        "HEARTBEAT",
        "ERROR:Test error message",
        "UNKNOWN_FORMAT"
    ]
    
    for msg in test_messages:
        parsed = handler.parse_message(msg)
        if parsed:
            print(f"✅ 파싱 성공: {msg} -> {parsed.type.value}")
        else:
            print(f"❌ 파싱 실패: {msg}")
    
    # 명령어 생성 테스트
    door_cmd = handler.create_door_open_command(3000)
    locker_cmd = handler.create_locker_open_command("L001", 5000)
    ping_cmd = handler.create_ping_command()
    
    print(f"🚪 문 열기 명령: {door_cmd}")
    print(f"🔐 락카 열기 명령: {locker_cmd}")
    print(f"🏓 핑 명령: {ping_cmd}")
    
    print(f"📈 핸들러 통계: {handler.stats}")


def test_barcode_utils():
    """바코드 유틸리티 테스트"""
    print("\n🏷️ 바코드 유틸리티 테스트 시작")
    
    # 회원 바코드 생성
    member_id = "M20250001"
    barcode = generate_member_barcode(member_id)
    print(f"👤 {member_id} 바코드: {barcode}")
    
    # 바코드 검증
    test_barcodes = [
        "123456789",     # 유효
        "12345",         # 너무 짧음
        "1234567890123456",  # 너무 김
        "ABC123DEF",     # 영숫자 (유효)
        "ABCDEFGHI",     # 숫자 없음 (무효)
        ""               # 빈 문자열
    ]
    
    for test_barcode in test_barcodes:
        is_valid = validate_barcode_format(test_barcode)
        status = "✅" if is_valid else "❌"
        print(f"{status} 바코드 '{test_barcode}': {'유효' if is_valid else '무효'}")
    
    # 시스템 능력 확인
    from hardware.barcode_utils import get_system_barcode_capabilities
    capabilities = get_system_barcode_capabilities()
    print(f"🔧 시스템 능력: {capabilities}")


async def main():
    """메인 테스트 함수"""
    print("🎯 라즈베리파이 헬스장 시스템 하드웨어 테스트")
    print("=" * 60)
    
    # 각 모듈별 테스트 실행
    await test_hardware_controller()
    await test_serial_scanner()
    test_protocol_handler()
    test_barcode_utils()
    
    print("\n✅ 모든 테스트 완료!")


if __name__ == "__main__":
    # 비동기 메인 실행
    asyncio.run(main())

