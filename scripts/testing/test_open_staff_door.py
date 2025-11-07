#!/usr/bin/env python3
"""교직원 문 열기 테스트 스크립트"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.esp32_manager import ESP32Manager


async def open_staff_door():
    """교직원용 문 열기"""
    print("🔌 ESP32 매니저 초기화 중...")
    
    manager = ESP32Manager()
    
    # 장치 추가
    manager.add_device('esp32_staff', '/dev/ttyUSB1', 'motor_controller')
    
    # 연결
    print("📡 ESP32 연결 중...")
    connected = await manager.connect_all_devices()
    
    if not connected:
        print("❌ ESP32 연결 실패")
        return
    
    print("✅ ESP32 연결 성공!")
    
    # 통신 시작
    await manager.start_communication()
    
    # 문 열기 명령
    print("🚪 문 열기 명령 전송 중...")
    result = await manager.send_command('esp32_staff', 'MOTOR_MOVE', revs=0.917, rpm=30)
    
    print(f"결과: {result}")
    
    # 대기
    await asyncio.sleep(2)
    
    # 종료
    print("✅ 완료!")


if __name__ == "__main__":
    asyncio.run(open_staff_door())

