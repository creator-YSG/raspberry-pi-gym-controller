#!/usr/bin/env python3
"""
ESP32 자동 감지 간단 테스트
라즈베리파이 부팅시 ESP32 연결 테스트용
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def main():
    """ESP32 자동 감지 테스트"""
    print("🔍 ESP32 자동 감지 테스트")
    print("=" * 50)
    
    try:
        # ESP32 자동 감지 테스트 실행
        from core.esp32_manager import test_esp32_auto_detection
        await test_esp32_auto_detection()
        
    except KeyboardInterrupt:
        print("\n⏹️ 사용자가 테스트를 중단했습니다.")
    except ImportError as e:
        print(f"❌ 모듈 import 오류: {e}")
        print("💡 다음 명령으로 필요한 패키지를 설치하세요:")
        print("   pip install pyserial")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return 1
    
    return 0


def test_serial_ports():
    """시리얼 포트 간단 확인"""
    print("\n📋 시리얼 포트 확인...")
    
    try:
        import serial.tools.list_ports
        
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("❌ 감지된 시리얼 포트 없음")
            return
        
        print(f"📱 감지된 포트: {len(ports)}개")
        
        for i, port in enumerate(ports, 1):
            print(f"  {i}. {port.device}")
            print(f"     설명: {port.description}")
            print(f"     제조사: {port.manufacturer}")
            print(f"     HWID: {port.hwid}")
            print()
        
    except ImportError:
        print("❌ pyserial이 설치되지 않았습니다")
        print("💡 설치 명령: pip install pyserial")
    except Exception as e:
        print(f"❌ 포트 확인 오류: {e}")


if __name__ == "__main__":
    print("🚀 라즈베리파이 ESP32 자동 감지 테스트")
    print()
    
    # 1. 시리얼 포트 확인
    test_serial_ports()
    
    # 2. ESP32 자동 감지 테스트
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ 실행 오류: {e}")
        sys.exit(1)
