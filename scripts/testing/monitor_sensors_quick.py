#!/usr/bin/env python3
"""
빠른 센서 모니터링 도구
1분 동안 센서 이벤트를 감시하고 순서대로 기록합니다.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


async def monitor_sensors_timed():
    """센서 이벤트를 시간제한으로 모니터링"""
    from core.esp32_manager import create_auto_esp32_manager
    
    print("\n" + "=" * 60)
    print("🔍 센서 모니터링 시작")
    print("=" * 60)
    print()
    
    # ESP32 연결
    manager = await create_auto_esp32_manager()
    
    if not manager or len(manager.devices) == 0:
        print("❌ ESP32 연결 실패")
        return []
    
    print(f"✅ {len(manager.devices)}개 ESP32 연결 완료")
    print()
    print("📋 준비:")
    print("  - 교직원 락커 10개를 순서대로 건드려주세요")
    print("  - 키를 빼거나 넣으면 감지됩니다")
    print("  - 1분 동안 모니터링합니다")
    print()
    
    detected_sensors = []
    sensor_set = set()
    
    async def handle_sensor(event_data):
        chip = event_data.get("chip_idx", 0)
        pin = event_data.get("pin", 0)
        state = event_data.get("state", "UNKNOWN")
        
        # 실제 센서 번호 계산
        actual_sensor = chip * 16 + pin + 1
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # LOW 상태 (키 뺌)만 카운트
        if state == "LOW":
            if actual_sensor not in sensor_set:
                order = len(detected_sensors) + 1
                detected_sensors.append({
                    "order": order,
                    "sensor_num": actual_sensor,
                    "chip": chip,
                    "pin": pin,
                    "time": timestamp
                })
                sensor_set.add(actual_sensor)
                
                print(f"[{timestamp}] ✅ #{order:2d}번째 센서: 센서 {actual_sensor:3d}번 (Chip{chip} Pin{pin:2d})")
            else:
                print(f"[{timestamp}] ⚪ 센서 {actual_sensor:3d}번 (이미 기록됨)")
    
    # 이벤트 핸들러 등록
    manager.register_event_handler("sensor_triggered", handle_sensor)
    
    # 5초 카운트다운
    for i in range(5, 0, -1):
        print(f"⏳ {i}초 후 시작...")
        await asyncio.sleep(1)
    
    print()
    print("🟢 모니터링 시작! (60초)")
    print("─" * 60)
    
    # 60초 대기
    await asyncio.sleep(60)
    
    print()
    print("─" * 60)
    print("🛑 모니터링 종료")
    print()
    
    return detected_sensors


async def main():
    sensors = await monitor_sensors_timed()
    
    if not sensors:
        print("❌ 감지된 센서가 없습니다")
        return
    
    print()
    print("=" * 60)
    print(f"📊 결과: {len(sensors)}개 센서 감지")
    print("=" * 60)
    print()
    
    # 교직원 락커 매핑 (S01~S10)
    mapping = {}
    for item in sensors[:10]:  # 최대 10개만
        order = item["order"]
        sensor_num = item["sensor_num"]
        locker_id = f"S{order:02d}"
        mapping[str(sensor_num)] = locker_id
        print(f"  센서 {sensor_num:3d}번 → {locker_id}")
    
    print()
    
    # 저장 여부 확인
    if len(sensors) >= 10:
        print("✅ 10개 센서가 모두 감지되었습니다!")
    else:
        print(f"⚠️ {len(sensors)}개만 감지되었습니다 (10개 필요)")
    
    print()
    answer = input("이 매핑을 sensor_mapping.json에 저장할까요? (y/n): ").strip().lower()
    
    if answer == 'y':
        import json
        
        # 기존 매핑 로드
        config_file = project_root / "config" / "sensor_mapping.json"
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            config = {"mapping": {}}
        
        # 교직원 매핑 업데이트
        config["mapping"].update(mapping)
        config["description"] = "센서 번호와 락커 ID 매핑 (실제 물리적 연결 기준)"
        config["note"] = "교직원 구역 매핑 완료 - monitor_sensors_quick.py"
        config["last_updated"] = datetime.now().isoformat()
        config["total_sensors"] = len(config["mapping"])
        
        # 저장
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 저장 완료: {config_file}")
        print()
        print("🚀 서버를 재시작하면 새 매핑이 적용됩니다")
    else:
        print("❌ 저장 취소")


if __name__ == "__main__":
    asyncio.run(main())

