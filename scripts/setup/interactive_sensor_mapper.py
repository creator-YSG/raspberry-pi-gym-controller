#!/usr/bin/env python3
"""
인터랙티브 센서 매핑 도구
- 실시간으로 센서 이벤트를 모니터링하면서 락커 번호 매핑
- 시리얼 포트, 칩 번호, 핀 번호를 포함한 상세 매핑 정보 저장
"""

import sys
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import serial.tools.list_ports

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.esp32_manager import ESP32Manager
from hardware.protocol_handler import ProtocolHandler


class InteractiveSensorMapper:
    """인터랙티브 센서 매핑 도구"""
    
    def __init__(self):
        """초기화"""
        self.mapping = {}  # locker_id -> 상세 매핑 정보
        self.reverse_mapping = {}  # (serial_port, chip_idx, pin) -> locker_id (중복 체크용)
        self.config_file = project_root / "config" / "sensor_mapping_detailed.json"
        self.esp32_manager = None
        self.last_sensor_event = None
        
        # 기존 매핑 로드 (있다면)
        self.load_existing_mapping()
        
    def load_existing_mapping(self):
        """기존 매핑 파일 로드"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.mapping = data.get('mapping', {})
                    
                    # 역매핑 테이블 구축
                    for locker_id, info in self.mapping.items():
                        key = (info['serial_port'], info['chip_index'], info['pin'])
                        self.reverse_mapping[key] = locker_id
                    
                    print(f"✅ 기존 매핑 로드됨: {len(self.mapping)}개")
            except Exception as e:
                print(f"⚠️ 기존 매핑 로드 실패: {e}")
    
    def save_mapping(self):
        """매핑 정보를 JSON 파일로 저장"""
        try:
            data = {
                "description": "센서 상세 매핑 (시리얼 포트, 칩, 핀 번호 포함)",
                "last_updated": datetime.now().isoformat(),
                "total_lockers": len(self.mapping),
                "mapping": self.mapping
            }
            
            # 파일 저장
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 매핑 정보 저장 완료: {self.config_file}")
            
            # 기존 sensor_mapping.json도 업데이트 (하위 호환성)
            self._update_legacy_mapping()
            
        except Exception as e:
            print(f"❌ 매핑 저장 실패: {e}")
    
    def _update_legacy_mapping(self):
        """기존 sensor_mapping.json 형식도 업데이트 (하위 호환성)"""
        try:
            legacy_file = project_root / "config" / "sensor_mapping.json"
            
            # 센서 번호 계산 (간단하게 순차적으로 할당)
            # 실제로는 (chip_idx * 16 + pin + 1) 공식을 사용할 수 있음
            legacy_mapping = {}
            sensor_num = 1
            
            # 락커 ID 순서로 정렬하여 할당
            sorted_lockers = sorted(self.mapping.keys())
            for locker_id in sorted_lockers:
                info = self.mapping[locker_id]
                # 센서 번호 계산: chip_idx * 16 + pin + 1
                calculated_sensor_num = info['chip_index'] * 16 + info['pin'] + 1
                legacy_mapping[str(calculated_sensor_num)] = locker_id
            
            legacy_data = {
                "description": "센서 번호와 락커 ID 매핑 (실제 물리적 연결 기준)",
                "note": "interactive_sensor_mapper.py로 생성됨",
                "last_updated": datetime.now().isoformat(),
                "total_sensors": len(legacy_mapping),
                "mapping": legacy_mapping
            }
            
            with open(legacy_file, 'w', encoding='utf-8') as f:
                json.dump(legacy_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 기존 형식 매핑 파일도 업데이트: {legacy_file}")
            
        except Exception as e:
            print(f"⚠️ 기존 형식 업데이트 실패: {e}")
    
    async def setup_esp32_connection(self):
        """ESP32 연결 설정"""
        print("\n🔌 사용 가능한 시리얼 포트 검색 중...")
        
        ports = list(serial.tools.list_ports.comports())
        usb_ports = [p for p in ports if 'USB' in p.device or 'ACM' in p.device]
        
        if not usb_ports:
            print("❌ USB 시리얼 포트를 찾을 수 없습니다.")
            return False
        
        print(f"\n📍 발견된 USB 포트: {len(usb_ports)}개")
        for i, port in enumerate(usb_ports):
            print(f"  {i+1}. {port.device} - {port.description}")
        
        # ESP32 Manager 초기화
        try:
            self.esp32_manager = ESP32Manager()
            await self.esp32_manager.initialize()
            
            # 센서 이벤트 핸들러 등록
            self.esp32_manager.register_sensor_callback(self.sensor_event_callback)
            
            print(f"✅ ESP32 연결 성공!")
            return True
            
        except Exception as e:
            print(f"❌ ESP32 연결 실패: {e}")
            return False
    
    def sensor_event_callback(self, event_data: Dict):
        """센서 이벤트 콜백 - 실시간으로 센서 감지"""
        # LOW 상태 (키 제거) 이벤트만 처리
        if event_data.get('state') == 'LOW':
            self.last_sensor_event = event_data
            
            serial_port = event_data.get('serial_port', 'unknown')
            chip_idx = event_data.get('chip_idx', 0)
            pin = event_data.get('pin', 0)
            addr = event_data.get('addr', '0x00')
            
            # 이미 매핑된 센서인지 확인
            key = (serial_port, chip_idx, pin)
            existing_locker = self.reverse_mapping.get(key)
            
            if existing_locker:
                print(f"\n🔔 센서 감지: Port={serial_port}, Chip={chip_idx}, Pin={pin} → 이미 매핑됨: {existing_locker}")
            else:
                print(f"\n🔔 새 센서 감지: Port={serial_port}, Chip={chip_idx}(Addr={addr}), Pin={pin}")
    
    async def start_interactive_mapping(self, locker_list: list):
        """인터랙티브 매핑 프로세스 시작
        
        Args:
            locker_list: 매핑할 락커 ID 리스트 (예: ['S01', 'S02', ...])
        """
        print("\n" + "="*60)
        print("🎯 인터랙티브 센서 매핑 시작")
        print("="*60)
        print(f"\n총 {len(locker_list)}개의 락커를 매핑합니다.")
        print("각 락커의 키를 순서대로 빼주세요.\n")
        
        for idx, locker_id in enumerate(locker_list, 1):
            # 이미 매핑된 락커는 건너뛰기 옵션
            if locker_id in self.mapping:
                print(f"\n[{idx}/{len(locker_list)}] {locker_id} - 이미 매핑됨")
                response = input("  다시 매핑하시겠습니까? (y/N): ").strip().lower()
                if response != 'y':
                    print("  ⏭️  건너뜀")
                    continue
            
            print(f"\n[{idx}/{len(locker_list)}] 📍 {locker_id} 락커의 키를 빼주세요...")
            print("  (대기 중... 'skip'을 입력하면 건너뜀, 'quit'을 입력하면 종료)")
            
            # 센서 이벤트 대기
            self.last_sensor_event = None
            
            while True:
                # 비동기로 입력 대기 (타임아웃 설정)
                try:
                    await asyncio.sleep(0.1)  # 센서 이벤트 체크
                    
                    if self.last_sensor_event:
                        # 센서 이벤트 발생!
                        event = self.last_sensor_event
                        serial_port = event.get('serial_port', 'unknown')
                        chip_idx = event.get('chip_idx', 0)
                        pin = event.get('pin', 0)
                        addr = event.get('addr', '0x00')
                        
                        print(f"\n  ✅ 센서 감지됨!")
                        print(f"     Port: {serial_port}")
                        print(f"     Chip: {chip_idx} (Addr: {addr})")
                        print(f"     Pin:  {pin}")
                        
                        # 확인
                        response = input(f"\n  이 센서를 {locker_id}에 매핑하시겠습니까? (Y/n/retry): ").strip().lower()
                        
                        if response == 'n':
                            print("  ❌ 취소됨. 다시 시도해주세요.")
                            self.last_sensor_event = None
                            continue
                        elif response == 'retry':
                            print("  🔄 다시 시도...")
                            self.last_sensor_event = None
                            continue
                        else:
                            # 매핑 저장
                            zone = self._determine_zone(locker_id)
                            self.mapping[locker_id] = {
                                "serial_port": serial_port,
                                "chip_index": chip_idx,
                                "chip_address": addr,
                                "pin": pin,
                                "zone": zone,
                                "verified": True,
                                "verified_at": datetime.now().isoformat()
                            }
                            
                            # 역매핑 테이블 업데이트
                            key = (serial_port, chip_idx, pin)
                            self.reverse_mapping[key] = locker_id
                            
                            print(f"  ✅ {locker_id} 매핑 완료!")
                            
                            # 자동 저장
                            self.save_mapping()
                            break
                    
                    # 사용자 입력 체크 (non-blocking)
                    # Note: 실제 non-blocking 입력은 복잡하므로, 여기서는 간단히 타임아웃 사용
                    
                except KeyboardInterrupt:
                    print("\n\n⚠️ 중단됨 (Ctrl+C)")
                    response = input("매핑을 저장하고 종료하시겠습니까? (Y/n): ").strip().lower()
                    if response != 'n':
                        self.save_mapping()
                    return False
        
        print("\n" + "="*60)
        print("🎉 모든 락커 매핑 완료!")
        print("="*60)
        self.save_mapping()
        return True
    
    def _determine_zone(self, locker_id: str) -> str:
        """락커 ID로부터 구역 결정"""
        if locker_id.startswith('S'):
            return 'STAFF'
        elif locker_id.startswith('M'):
            return 'MALE'
        elif locker_id.startswith('F'):
            return 'FEMALE'
        else:
            return 'UNKNOWN'
    
    def print_mapping_summary(self):
        """매핑 요약 출력"""
        print("\n" + "="*60)
        print("📊 매핑 요약")
        print("="*60)
        
        if not self.mapping:
            print("매핑된 락커가 없습니다.")
            return
        
        # 구역별로 그룹화
        zones = {}
        for locker_id, info in sorted(self.mapping.items()):
            zone = info['zone']
            if zone not in zones:
                zones[zone] = []
            zones[zone].append(locker_id)
        
        for zone, lockers in zones.items():
            print(f"\n{zone} 구역: {len(lockers)}개")
            for locker_id in lockers:
                info = self.mapping[locker_id]
                print(f"  {locker_id}: Port={info['serial_port']}, "
                      f"Chip={info['chip_index']}({info['chip_address']}), "
                      f"Pin={info['pin']}")
        
        print(f"\n총 {len(self.mapping)}개 락커 매핑됨")
    
    async def run(self):
        """메인 실행 함수"""
        print("="*60)
        print("🔧 인터랙티브 센서 매핑 도구")
        print("="*60)
        
        # ESP32 연결
        if not await self.setup_esp32_connection():
            print("❌ ESP32 연결에 실패했습니다. 프로그램을 종료합니다.")
            return
        
        # 매핑할 락커 리스트 입력
        print("\n매핑 모드 선택:")
        print("  1. 교직원 (S01~S10)")
        print("  2. 남성 (M01~M40)")
        print("  3. 여성 (F01~F10)")
        print("  4. 사용자 정의")
        
        choice = input("\n선택 (1-4): ").strip()
        
        if choice == '1':
            locker_list = [f"S{i:02d}" for i in range(1, 11)]
        elif choice == '2':
            locker_list = [f"M{i:02d}" for i in range(1, 41)]
        elif choice == '3':
            locker_list = [f"F{i:02d}" for i in range(1, 11)]
        elif choice == '4':
            locker_input = input("락커 ID를 쉼표로 구분하여 입력하세요 (예: S01,S02,S03): ").strip()
            locker_list = [l.strip() for l in locker_input.split(',')]
        else:
            print("❌ 잘못된 선택입니다.")
            return
        
        # 인터랙티브 매핑 시작
        await self.start_interactive_mapping(locker_list)
        
        # 매핑 요약 출력
        self.print_mapping_summary()
        
        # ESP32 연결 종료
        if self.esp32_manager:
            await self.esp32_manager.close()
        
        print("\n✅ 프로그램 종료")


async def main():
    """메인 함수"""
    mapper = InteractiveSensorMapper()
    try:
        await mapper.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ 프로그램이 중단되었습니다.")
        mapper.save_mapping()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        mapper.save_mapping()


if __name__ == "__main__":
    asyncio.run(main())

