#!/usr/bin/env python3
"""
자동 센서 매핑 도구
- 실시간으로 센서 이벤트를 모니터링하면서 자동으로 순서대로 매핑
- 사용자가 순서대로 센서를 건드리면 자동으로 기록
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.esp32_manager import ESP32Manager


class AutoSensorMapper:
    """자동 센서 매핑 도구"""
    
    def __init__(self):
        """초기화"""
        self.mapping = {}  # locker_id -> 상세 매핑 정보
        self.config_file = project_root / "config" / "sensor_mapping_detailed.json"
        self.legacy_file = project_root / "config" / "sensor_mapping.json"
        
        self.esp32_manager = None
        self.current_index = 0
        self.locker_list = []
        self.waiting_for_sensor = False
        self.last_sensor_event = None
        
        # 기존 매핑 로드
        self.load_existing_mapping()
    
    def load_existing_mapping(self):
        """기존 매핑 파일 로드"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.mapping = data.get('mapping', {})
                    print(f"✅ 기존 매핑 로드됨: {len(self.mapping)}개")
            except Exception as e:
                print(f"⚠️ 기존 매핑 로드 실패: {e}")
    
    def save_mapping(self):
        """매핑 정보 저장"""
        try:
            # 상세 매핑 저장
            data = {
                "description": "센서 상세 매핑 (시리얼 포트, 칩, 핀 번호 포함)",
                "last_updated": datetime.now().isoformat(),
                "total_lockers": len(self.mapping),
                "mapping": self.mapping
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 상세 매핑 저장: {self.config_file}")
            
            # 기존 형식도 저장
            self._update_legacy_mapping()
            
        except Exception as e:
            print(f"❌ 매핑 저장 실패: {e}")
    
    def _update_legacy_mapping(self):
        """기존 sensor_mapping.json 형식도 업데이트"""
        try:
            legacy_mapping = {}
            
            for locker_id, info in self.mapping.items():
                # 센서 번호 계산: chip_idx * 16 + pin + 1
                sensor_num = info['chip_index'] * 16 + info['pin'] + 1
                legacy_mapping[str(sensor_num)] = locker_id
            
            legacy_data = {
                "description": "센서 번호와 락커 ID 매핑 (실제 물리적 연결 기준)",
                "note": "auto_sensor_mapper.py로 생성됨",
                "last_updated": datetime.now().isoformat(),
                "total_sensors": len(legacy_mapping),
                "mapping": legacy_mapping
            }
            
            with open(self.legacy_file, 'w', encoding='utf-8') as f:
                json.dump(legacy_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 기존 형식 매핑 저장: {self.legacy_file}")
            
        except Exception as e:
            print(f"⚠️ 기존 형식 업데이트 실패: {e}")
    
    def sensor_event_callback(self, event_data: dict):
        """센서 이벤트 콜백 - 센서가 감지되면 자동으로 호출됨"""
        # LOW 상태 (키 제거) 이벤트만 처리
        if event_data.get('state') == 'LOW' and self.waiting_for_sensor:
            self.last_sensor_event = event_data
            print(f"\n🔔 센서 감지!")
    
    async def setup_esp32(self):
        """ESP32 연결 설정"""
        print("\n🔌 ESP32 매니저 초기화 중...")
        
        self.esp32_manager = ESP32Manager()
        
        # 두 개의 ESP32 추가 (실제 설정에 맞게)
        self.esp32_manager.add_device('esp32_auto_0', '/dev/ttyUSB0', 'motor_controller')
        self.esp32_manager.add_device('esp32_staff', '/dev/ttyUSB1', 'motor_controller')
        
        # 센서 콜백 등록
        self.esp32_manager.register_sensor_callback(self.sensor_event_callback)
        
        # 연결
        print("📡 ESP32 연결 중...")
        connected = await self.esp32_manager.connect_all_devices()
        
        if not connected:
            print("❌ ESP32 연결 실패")
            return False
        
        print("✅ ESP32 연결 성공!")
        
        # 통신 시작
        await self.esp32_manager.start_communication()
        
        return True
    
    async def start_mapping(self, locker_list: list):
        """자동 매핑 시작
        
        Args:
            locker_list: 매핑할 락커 ID 리스트 (예: ['S01', 'S02', ...])
        """
        self.locker_list = locker_list
        self.current_index = 0
        
        print("\n" + "="*70)
        print(f"🎯 자동 센서 매핑 시작: {len(locker_list)}개 락커")
        print("="*70)
        print("\n📌 작업 방법:")
        print("  1. 각 락커의 키를 순서대로 빼주세요")
        print("  2. 센서가 감지되면 자동으로 기록됩니다")
        print("  3. 'y'를 입력하여 다음으로 진행하거나, 'r'로 재시도, 'q'로 종료")
        print("="*70)
        
        for idx, locker_id in enumerate(locker_list):
            self.current_index = idx
            
            # 이미 매핑된 락커 확인
            if locker_id in self.mapping:
                info = self.mapping[locker_id]
                print(f"\n[{idx+1}/{len(locker_list)}] {locker_id} - 이미 매핑됨")
                print(f"  현재: Port={info['serial_port']}, Chip={info['chip_index']}, Pin={info['pin']}")
                
                # 건너뛸지 물어봄
                user_input = input("  건너뛰시겠습니까? (Y/n): ").strip().lower()
                if user_input != 'n':
                    print("  ⏭️  건너뜀")
                    continue
            
            # 센서 대기
            success = await self._wait_for_sensor(locker_id, idx)
            
            if not success:
                print("\n⚠️ 매핑 중단됨")
                break
        
        print("\n" + "="*70)
        print("🎉 매핑 완료!")
        print("="*70)
        
        # 최종 저장
        self.save_mapping()
        self._print_summary()
    
    async def _wait_for_sensor(self, locker_id: str, idx: int) -> bool:
        """센서 감지 대기
        
        Args:
            locker_id: 락커 ID
            idx: 현재 인덱스
            
        Returns:
            성공 여부 (False면 중단)
        """
        while True:
            print(f"\n[{idx+1}/{len(self.locker_list)}] 📍 {locker_id}")
            print(f"  락커 키를 빼주세요... (대기 중)")
            
            # 센서 감지 대기
            self.last_sensor_event = None
            self.waiting_for_sensor = True
            
            # 타임아웃 30초
            timeout = 30
            for i in range(timeout * 10):  # 0.1초 간격으로 체크
                await asyncio.sleep(0.1)
                
                if self.last_sensor_event:
                    # 센서 감지됨!
                    self.waiting_for_sensor = False
                    event = self.last_sensor_event
                    
                    serial_port = event.get('serial_port', 'unknown')
                    chip_idx = event.get('chip_idx', 0)
                    pin = event.get('pin', 0)
                    addr = event.get('addr', '0x00')
                    device_id = event.get('device_id', 'unknown')
                    
                    print(f"\n  ✅ 센서 감지됨!")
                    print(f"     Device: {device_id}")
                    print(f"     Port:   {serial_port}")
                    print(f"     Chip:   {chip_idx} (Addr: {addr})")
                    print(f"     Pin:    {pin}")
                    
                    # 확인
                    while True:
                        user_input = input(f"\n  이 센서를 {locker_id}에 매핑할까요? (Y/n/r=재시도/q=종료): ").strip().lower()
                        
                        if user_input == 'q':
                            return False
                        elif user_input == 'n' or user_input == 'r':
                            print("  🔄 다시 시도...")
                            break
                        else:  # y 또는 엔터
                            # 매핑 저장
                            zone = self._determine_zone(locker_id)
                            self.mapping[locker_id] = {
                                "serial_port": serial_port,
                                "chip_index": chip_idx,
                                "chip_address": addr,
                                "pin": pin,
                                "zone": zone,
                                "device_id": device_id,
                                "verified": True,
                                "verified_at": datetime.now().isoformat()
                            }
                            
                            print(f"  ✅ {locker_id} 매핑 저장!")
                            
                            # 자동 저장
                            self.save_mapping()
                            
                            return True
                    
                    # retry를 선택한 경우 다시 시작
                    if user_input == 'n' or user_input == 'r':
                        break
            
            # 타임아웃
            if not self.last_sensor_event:
                self.waiting_for_sensor = False
                print(f"\n  ⏰ 타임아웃 ({timeout}초)")
                user_input = input("  재시도(r), 건너뛰기(s), 종료(q)?: ").strip().lower()
                
                if user_input == 'q':
                    return False
                elif user_input == 's':
                    print("  ⏭️  건너뜀")
                    return True
                # 아니면 재시도
    
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
    
    def _print_summary(self):
        """매핑 요약 출력"""
        print("\n" + "="*70)
        print("📊 매핑 요약")
        print("="*70)
        
        zones = {'STAFF': [], 'MALE': [], 'FEMALE': []}
        for locker_id in sorted(self.mapping.keys()):
            zone = self.mapping[locker_id]['zone']
            if zone in zones:
                zones[zone].append(locker_id)
        
        zone_names = {'STAFF': '교직원', 'MALE': '남성', 'FEMALE': '여성'}
        
        for zone, lockers in zones.items():
            if lockers:
                print(f"\n{zone_names[zone]} 구역: {len(lockers)}개")
                for locker_id in lockers:
                    info = self.mapping[locker_id]
                    print(f"  {locker_id}: {info['serial_port']} | "
                          f"Chip={info['chip_index']} | Pin={info['pin']}")
        
        print(f"\n총 {len(self.mapping)}개 락커 매핑됨")
    
    async def run(self):
        """메인 실행"""
        print("="*70)
        print("🔧 자동 센서 매핑 도구")
        print("="*70)
        
        # ESP32 연결
        if not await self.setup_esp32():
            print("❌ ESP32 연결 실패")
            return
        
        # 매핑 모드 선택
        print("\n매핑할 구역을 선택하세요:")
        print("  1. 교직원 (S01~S10)")
        print("  2. 남성 (M01~M40)")
        print("  3. 여성 (F01~F10)")
        print("  4. 전체")
        
        choice = input("\n선택 (1-4): ").strip()
        
        if choice == '1':
            locker_list = [f"S{i:02d}" for i in range(1, 11)]
        elif choice == '2':
            locker_list = [f"M{i:02d}" for i in range(1, 41)]
        elif choice == '3':
            locker_list = [f"F{i:02d}" for i in range(1, 11)]
        elif choice == '4':
            locker_list = [f"S{i:02d}" for i in range(1, 11)]
            locker_list += [f"M{i:02d}" for i in range(1, 41)]
            locker_list += [f"F{i:02d}" for i in range(1, 11)]
        else:
            print("❌ 잘못된 선택")
            return
        
        # 자동 매핑 시작
        await self.start_mapping(locker_list)
        
        print("\n✅ 프로그램 종료")


async def main():
    """메인 함수"""
    mapper = AutoSensorMapper()
    try:
        await mapper.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ 중단됨 (Ctrl+C)")
        mapper.save_mapping()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        mapper.save_mapping()


if __name__ == "__main__":
    asyncio.run(main())

