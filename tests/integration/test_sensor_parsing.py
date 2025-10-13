#!/usr/bin/env python3
"""
ESP32 센서 데이터 파싱 테스트
"""

import sys
import os
sys.path.append('.')

from hardware.protocol_handler import ProtocolHandler

# 실제 ESP32에서 나오는 센서 데이터
test_messages = [
    '{"device_id":"esp32_gym","message_type":"event","timestamp":"2025-09-23T0:7:48Z","event_type":"sensor_triggered","data":{"chip_idx":0,"addr":"0x26","pin":0,"raw":"LOW","active":false}}',
    '{"device_id":"esp32_gym","message_type":"event","timestamp":"2025-09-23T0:7:49Z","event_type":"sensor_triggered","data":{"chip_idx":0,"addr":"0x26","pin":0,"raw":"HIGH","active":true}}',
    '{"device_id":"esp32_gym","message_type":"event","timestamp":"2025-09-23T0:7:56Z","event_type":"sensor_triggered","data":{"chip_idx":0,"addr":"0x26","pin":1,"raw":"LOW","active":false}}'
]

def test_parsing():
    handler = ProtocolHandler()
    
    print("=== ESP32 센서 데이터 파싱 테스트 ===")
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n테스트 {i}:")
        print(f"입력: {message}")
        
        try:
            parsed = handler.parse_message(message)
            if parsed:
                print(f"파싱 성공!")
                print(f"  타입: {parsed.type}")
                print(f"  데이터: {parsed.data}")
            else:
                print("파싱 실패!")
        except Exception as e:
            print(f"파싱 오류: {e}")

if __name__ == "__main__":
    test_parsing()
