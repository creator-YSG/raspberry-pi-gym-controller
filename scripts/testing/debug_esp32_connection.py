#!/usr/bin/env python3
"""
ESP32 연결 및 시리얼 통신 디버그 스크립트
"""

import asyncio
import time
from core.esp32_manager import create_auto_esp32_manager

async def debug_esp32():
    print("=== ESP32 연결 디버그 시작 ===")
    
    # ESP32Manager 생성
    manager = await create_auto_esp32_manager()
    
    if not manager:
        print("❌ ESP32Manager 생성 실패")
        return
    
    # 디바이스 상태 확인
    devices = manager.get_all_devices_status()
    print(f"📱 연결된 디바이스: {len(devices)}개")
    
    for device_id, status in devices.items():
        print(f"  - {device_id}: {'온라인' if status['is_online'] else '오프라인'}")
        print(f"    포트: {status['serial_port']}")
        print(f"    타입: {status['device_type']}")
        print(f"    통계: {status['stats']}")
    
    # 센서 이벤트 핸들러 등록
    sensor_count = 0
    
    def sensor_handler(event_data):
        nonlocal sensor_count
        sensor_count += 1
        print(f"🔥 센서 이벤트 #{sensor_count}: {event_data}")
    
    manager.register_event_handler("sensor_triggered", sensor_handler)
    
    # 15초간 이벤트 대기
    print("\n⏳ 15초간 센서 이벤트 대기 중...")
    print("센서를 건드려보세요!")
    await asyncio.sleep(15)
    
    print(f"\n📊 결과: 총 {sensor_count}개 센서 이벤트 수신")
    
    # 정리
    await manager.stop_communication()
    await manager.disconnect_all_devices()

if __name__ == "__main__":
    asyncio.run(debug_esp32())
