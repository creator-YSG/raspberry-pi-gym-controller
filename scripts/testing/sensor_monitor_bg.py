#!/usr/bin/env python3
"""
백그라운드 센서 모니터 - 결과를 파일로 저장
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
    
    output = []
    output.append("\n" + "=" * 60)
    output.append(f"🔍 센서 모니터링 시작: {port}")
    output.append("=" * 60)
    output.append("")
    
    detected_sensors = []
    sensor_set = set()
    
    try:
        ser = serial.Serial(port, 115200, timeout=0.1)
        output.append(f"✅ 시리얼 포트 연결: {port}")
        output.append("")
        output.append("📋 교직원 락커 10개를 순서대로 건드리는 중...")
        output.append("")
        
        # 5초 대기
        output.append("⏳ 5초 후 시작...")
        for line in output:
            print(line)
        
        for i in range(5, 0, -1):
            time.sleep(1)
        
        print("")
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
                    buffer = lines[-1]
                    
                    for line in lines[:-1]:
                        line = line.strip()
                        if not line or not '{' in line:
                            continue
                        
                        # JSON 추출
                        try:
                            json_match = re.search(r'\{[^{}]*"event_type"[^{}]*\}', line)
                            if not json_match:
                                # 더 긴 JSON 시도
                                json_match = re.search(r'\{.*?"event_type".*?\}', line)
                            
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
                                        
                                        msg = f"[{timestamp}] ✅ #{order:2d}번째: 센서 {sensor_num:3d}번 (Chip{chip} Pin{pin:2d})"
                                        print(msg)
                                        output.append(msg)
                        
                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            pass
                
                except Exception as e:
                    pass
            
            time.sleep(0.01)
        
        print("")
        print("─" * 60)
        print("🛑 모니터링 종료")
        output.append("")
        output.append("─" * 60)
        output.append("🛑 모니터링 종료")
        
        ser.close()
        return detected_sensors, output
    
    except Exception as e:
        error_msg = f"❌ 오류: {e}"
        print(error_msg)
        output.append(error_msg)
        return [], output


def main():
    result_file = project_root / "instance" / "sensor_monitor_result.json"
    log_file = project_root / "instance" / "sensor_monitor_log.txt"
    
    # 교직원용 ESP32 모니터링
    sensors, output_lines = monitor_serial('/dev/ttyUSB2', duration=60)
    
    # 로그 파일 저장
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print()
    print("=" * 60)
    print(f"📊 결과: {len(sensors)}개 센서 감지")
    print("=" * 60)
    print()
    
    # 교직원 락커 매핑 (S01~S10)
    mapping = {}
    for item in sensors[:10]:
        order = item["order"]
        sensor_num = item["sensor_num"]
        locker_id = f"S{order:02d}"
        mapping[str(sensor_num)] = locker_id
        print(f"  센서 {sensor_num:3d}번 → {locker_id}")
    
    print()
    
    if len(sensors) >= 10:
        print("✅ 10개 센서가 모두 감지되었습니다!")
    else:
        print(f"⚠️ {len(sensors)}개만 감지되었습니다")
    
    # 결과 파일 저장 (자동)
    result = {
        "detected_sensors": sensors,
        "mapping": mapping,
        "total_count": len(sensors),
        "timestamp": datetime.now().isoformat()
    }
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"💾 결과 저장: {result_file}")
    print(f"📝 로그 저장: {log_file}")
    
    # sensor_mapping.json에 저장
    if mapping:
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
        
        print(f"✅ 매핑 저장 완료: {config_file}")


if __name__ == "__main__":
    main()

