#!/usr/bin/env python3
"""모든 구역 문 닫기 테스트"""
import asyncio
import sys
sys.path.insert(0, '/home/pi/gym-controller')

from app.hardware.esp32_manager import ESP32Manager

async def close_all_doors():
    manager = ESP32Manager()
    
    print("ESP32 연결 중...")
    await manager.connect_all_devices()
    print("연결 완료!")
    
    print("\n🚪 교직원용 문 닫기...")
    result = await manager.send_command('/dev/ttyUSB0', 'MOTOR', 0, 'CLOSE')
    print(f"결과: {result}")
    await asyncio.sleep(3)
    
    print("\n🚪 남성용 문 닫기...")
    result = await manager.send_command('/dev/ttyUSB1', 'MOTOR', 0, 'CLOSE')
    print(f"결과: {result}")
    await asyncio.sleep(3)
    
    print("\n🚪 여성용 문 닫기...")
    result = await manager.send_command('/dev/ttyUSB2', 'MOTOR', 0, 'CLOSE')
    print(f"결과: {result}")
    await asyncio.sleep(3)
    
    print("\n✅ 모든 문 닫기 완료!")
    await manager.close_all()

if __name__ == "__main__":
    asyncio.run(close_all_doors())

