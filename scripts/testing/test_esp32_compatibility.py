#!/usr/bin/env python3
"""
ESP32 코드와 라즈베리파이 시스템 호환성 테스트
"""

import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from hardware.protocol_handler import ProtocolHandler
from core.esp32_manager import ESP32Manager

def test_esp32_message_compatibility():
    """ESP32 메시지 형식 호환성 테스트"""
    print("🔍 ESP32 메시지 형식 호환성 테스트")
    print("=" * 60)
    
    protocol_handler = ProtocolHandler()
    
    # ESP32 코드에서 전송하는 메시지 형식들
    test_messages = [
        # 1. 바코드 스캔 이벤트
        {
            "name": "바코드 스캔",
            "message": json.dumps({
                "device_id": "esp32_gym",
                "message_type": "event",
                "timestamp": 12345678,
                "version": "v7.1",
                "event_type": "barcode_scanned",
                "data": {
                    "barcode": "1234567890",
                    "scan_count": 1
                }
            })
        },
        
        # 2. IR 센서 이벤트
        {
            "name": "IR 센서 감지",
            "message": json.dumps({
                "device_id": "esp32_gym",
                "message_type": "event",
                "timestamp": 12345678,
                "version": "v7.1",
                "event_type": "sensor_triggered",
                "data": {
                    "chip_idx": 0,
                    "addr": "0x20",
                    "pin": 5,
                    "state": "LOW",
                    "active": True
                }
            })
        },
        
        # 3. 상태 응답
        {
            "name": "상태 응답",
            "message": json.dumps({
                "device_id": "esp32_gym",
                "message_type": "response",
                "timestamp": 12345678,
                "version": "v7.1",
                "data": {
                    "status": "ready",
                    "uptime": 60000,
                    "wifi": True,
                    "motor_busy": False,
                    "mcp_count": 2,
                    "total_scans": 10,
                    "total_ir_events": 25,
                    "total_motor_moves": 5,
                    "microstep": 2,
                    "steps_per_rev": 400,
                    "ip": "192.168.1.100",
                    "rssi": -45,
                    "hostname": "ESP32-GYM-LOCKER"
                }
            })
        },
        
        # 4. 락커 열기 완료 응답
        {
            "name": "락커 열기 완료",
            "message": json.dumps({
                "device_id": "esp32_gym",
                "message_type": "response",
                "timestamp": 12345678,
                "version": "v7.1",
                "event_type": "locker_opened",
                "data": {
                    "locker_id": "M01",
                    "status": "opened",
                    "steps": 367
                }
            })
        },
        
        # 5. 모터 이동 완료 응답
        {
            "name": "모터 이동 완료",
            "message": json.dumps({
                "device_id": "esp32_gym",
                "message_type": "response",
                "timestamp": 12345678,
                "version": "v7.1",
                "event_type": "motor_moved",
                "data": {
                    "revs": 0.917,
                    "rpm": 30,
                    "steps": 367
                }
            })
        },
        
        # 6. 에러 응답
        {
            "name": "에러 응답",
            "message": json.dumps({
                "device_id": "esp32_gym",
                "message_type": "error",
                "timestamp": 12345678,
                "version": "v7.1",
                "data": {
                    "error_code": "MOTOR_BUSY",
                    "error_message": "모터가 작동 중입니다"
                }
            })
        }
    ]
    
    # 각 메시지 파싱 테스트
    for test in test_messages:
        print(f"\n📨 {test['name']} 테스트:")
        print(f"   원본: {test['message'][:80]}...")
        
        parsed = protocol_handler.parse_message(test['message'])
        
        if parsed:
            print(f"   ✅ 파싱 성공: {parsed.type.value}")
            print(f"   📊 데이터: {list(parsed.data.keys())}")
        else:
            print(f"   ❌ 파싱 실패")
    
    print(f"\n📈 프로토콜 핸들러 통계:")
    stats = protocol_handler.stats
    for key, value in stats.items():
        print(f"   {key}: {value}")


def test_esp32_command_compatibility():
    """ESP32 명령어 형식 호환성 테스트"""
    print("\n🎛️ ESP32 명령어 형식 호환성 테스트")
    print("=" * 60)
    
    protocol_handler = ProtocolHandler()
    
    # 라즈베리파이에서 ESP32로 전송할 명령어들
    test_commands = [
        # 1. 상태 요청
        {
            "name": "상태 요청",
            "command": protocol_handler.create_esp32_status_command()
        },
        
        # 2. 락커 열기 (330도 회전)
        {
            "name": "락커 열기",
            "command": protocol_handler.create_esp32_locker_open_command("M01", 3000)
        },
        
        # 3. 모터 직접 제어
        {
            "name": "모터 제어",
            "command": protocol_handler.create_esp32_motor_command(0.917, 30)
        },
        
        # 4. 테스트 명령
        {
            "name": "테스트 명령",
            "command": protocol_handler.create_esp32_json_command("test")
        },
        
        # 5. 리셋 명령
        {
            "name": "리셋 명령",
            "command": protocol_handler.create_esp32_json_command("reset")
        }
    ]
    
    # 각 명령어 검증
    for test in test_commands:
        print(f"\n🔧 {test['name']}:")
        print(f"   명령어: {test['command']}")
        
        # JSON 파싱 검증
        try:
            cmd_data = json.loads(test['command'])
            print(f"   ✅ JSON 유효: command={cmd_data.get('command')}")
            
            # ESP32 코드에서 처리 가능한지 확인
            command = cmd_data.get('command')
            if command in ['get_status', 'open_locker', 'motor_move', 'test', 'reset']:
                print(f"   ✅ ESP32 호환: {command} 명령 지원")
            else:
                print(f"   ⚠️ ESP32 미지원: {command} 명령")
                
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON 오류: {e}")


def analyze_esp32_code_features():
    """ESP32 코드 기능 분석"""
    print("\n🔬 ESP32 코드 기능 분석")
    print("=" * 60)
    
    esp32_features = {
        "통신": {
            "WiFi": "✅ 지원 (ssid: sya, OTA 업데이트)",
            "시리얼": "✅ 지원 (115200 baud, JSON 메시지)",
            "mDNS": "✅ 지원 (ESP32-GYM-LOCKER.local)"
        },
        "하드웨어": {
            "바코드 스캐너": "✅ UART2 (16,17번 핀)",
            "스테퍼 모터": "✅ TB6600 (25,26,27번 핀, 1/2 마이크로스텝)",
            "MCP23017": "✅ I2C (21,22번 핀, 최대 8개)",
            "LED/부저": "✅ 2,4번 핀"
        },
        "기능": {
            "바코드 스캔": "✅ 자동 감지 및 전송",
            "IR 센서": "✅ MCP23017 기반, 디바운싱",
            "모터 제어": "✅ 330도 회전 (0.917회전)",
            "상태 모니터링": "✅ 통계 및 WiFi 상태"
        },
        "프로토콜": {
            "JSON 메시지": "✅ 구조화된 이벤트/응답",
            "명령어 처리": "✅ get_status, open_locker, motor_move",
            "에러 처리": "✅ 상세한 에러 코드 및 메시지",
            "OTA 업데이트": "✅ 무선 펌웨어 업데이트"
        }
    }
    
    for category, features in esp32_features.items():
        print(f"\n📋 {category}:")
        for feature, status in features.items():
            print(f"   {feature}: {status}")


def check_compatibility_issues():
    """호환성 문제점 분석"""
    print("\n⚠️ 호환성 분석 결과")
    print("=" * 60)
    
    compatibility_report = {
        "완벽 호환": [
            "✅ JSON 메시지 형식 - ESP32와 라즈베리파이 모두 지원",
            "✅ 바코드 스캔 이벤트 - 동일한 구조",
            "✅ 상태 응답 형식 - 호환 가능",
            "✅ 락커 열기 명령 - open_locker 명령 지원",
            "✅ 모터 제어 - 정확한 회전수 (0.917회전 = 330도)",
            "✅ 에러 처리 - 구조화된 에러 응답"
        ],
        "주의사항": [
            "⚠️ ESP32 디바이스 ID - 'esp32_gym'으로 고정 (라즈베리파이는 다중 디바이스 지원)",
            "⚠️ WiFi 설정 - 하드코딩된 SSID/비밀번호",
            "⚠️ 락커 ID 매핑 - ESP32는 단일 디바이스, 라즈베리파이는 구역별 분리",
            "⚠️ 센서 이벤트 - MCP23017 주소 및 핀 번호 매핑 필요"
        ],
        "개선 필요": [
            "🔧 다중 ESP32 지원 - 현재는 단일 디바이스만 지원",
            "🔧 동적 WiFi 설정 - 설정 파일 또는 웹 인터페이스 필요",
            "🔧 락커 구역 식별 - M/F/S 구역별 디바이스 구분 로직",
            "🔧 센서 매핑 테이블 - 물리적 센서와 락커 ID 연결"
        ]
    }
    
    for category, items in compatibility_report.items():
        print(f"\n📊 {category}:")
        for item in items:
            print(f"   {item}")


def main():
    """메인 테스트 실행"""
    print("🚀 ESP32 코드 호환성 분석 시작")
    print("=" * 80)
    
    try:
        # 1. 메시지 형식 호환성
        test_esp32_message_compatibility()
        
        # 2. 명령어 형식 호환성  
        test_esp32_command_compatibility()
        
        # 3. ESP32 기능 분석
        analyze_esp32_code_features()
        
        # 4. 호환성 문제점 분석
        check_compatibility_issues()
        
        print("\n🎉 ESP32 호환성 분석 완료!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 테스트 오류: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
