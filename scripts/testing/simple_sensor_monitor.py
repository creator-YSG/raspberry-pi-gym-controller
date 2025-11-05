#!/usr/bin/env python3
"""
단순 센서 모니터 - 직접 시리얼 포트 읽기
"""

import sys
import serial
import time
import json
import re
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def monitor_serial(port='/dev/ttyUSB2', duration=60):
    """시리얼 포트를 직접 읽어서 센서 모니터링"""
    
    print("\n" + "=" * 60)
    print(f"🔍 센서 모니터링 시작: {port}")
    print("=" * 60)
    print()
    
    detected_sensors = []
    sensor_set = set()
    
    try:
        ser = serial.Serial(port, 115200, timeout=0.1)
        print(f"✅ 시리얼 포트 연결: {port}")
        print()
        print("📋 준비:")
        print("  - 교직원 락커 10개를 순서대로 건드려주세요")
        print("  - 키를 빼면 감지됩니다")
        print()
        
        # 5초 카운트다운
        for i in range(5, 0, -1):
            print(f"⏳ {i}초 후 시작...")
            time.sleep(1)
        
        print()
        print("🟢 모니터링 시작! (60초)")
        print("─" * 60)
        
        start_time = time.time()
        buffer = ""
        
        while time.time() - start_time < duration:
            if ser.in_waiting > 0:
                try:
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    
                    # 줄바꿈으로 분리
                    lines = buffer.split('\n')
                    buffer = lines[-1]  # 마지막 불완전한 줄은 버퍼에 유지
                    
                    for line in lines[:-1]:
                        line = line.strip()
                        if not line or not '{' in line:
                            continue
                        
                        # JSON 추출
                        try:
                            # 중괄호로 둘러싸인 부분 찾기
                            json_match = re.search(r'\{.*\}', line)
                            if not json_match:
                                continue
                            
                            json_str = json_match.group()
                            data = json.loads(json_str)
                            
                            # 센서 이벤트만 처리
                            if data.get('event_type') == 'sensor_triggered':
                                event_data = data.get('data', {})
                                chip = event_data.get('chip_idx', 0)
                                pin = event_data.get('pin', 0)
                                state = event_data.get('state', '')
                                
                                # LOW 상태 (키 뺌)만 카운트
                                if state == 'LOW':
                                    sensor_num = chip * 16 + pin + 1
                                    
                                    if sensor_num not in sensor_set:
                                        order = len(detected_sensors) + 1
                                        timestamp = datetime.now().strftime("%H:%M:%S")
                                        
                                        detected_sensors.append({
                                            "order": order,
                                            "sensor_num": sensor_num,
                                            "chip": chip,
                                            "pin": pin,
                                            "time": timestamp
                                        })
                                        sensor_set.add(sensor_num)
                                        
                                        print(f"[{timestamp}] ✅ #{order:2d}번째: 센서 {sensor_num:3d}번 (Chip{chip} Pin{pin:2d})")
                        
                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            pass
                
                except Exception as e:
                    pass
            
            time.sleep(0.01)
        
        print()
        print("─" * 60)
        print("🛑 모니터링 종료")
        print()
        
        ser.close()
        return detected_sensors
    
    except Exception as e:
        print(f"❌ 오류: {e}")
        return []


def main():
    # 교직원용 ESP32 모니터링
    sensors = monitor_serial('/dev/ttyUSB2', duration=60)
    
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
        config["note"] = f"교직원 구역 매핑 완료 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        config["last_updated"] = datetime.now().isoformat()
        config["total_sensors"] = len(config["mapping"])
        
        # 저장
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 저장 완료: {config_file}")
        print()
        print("📋 저장된 매핑:")
        for sensor, locker in sorted(mapping.items(), key=lambda x: int(x[0])):
            print(f"  센서 {sensor:>3} → {locker}")
    else:
        print("❌ 저장 취소")


if __name__ == "__main__":
    main()

