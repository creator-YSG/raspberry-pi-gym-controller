#!/usr/bin/env python3
"""
수동 센서 매핑 도구
- 실시간 로그를 보면서 수동으로 센서 정보를 입력
- 라즈베리파이 SSH 연결 없이도 사용 가능
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class ManualSensorMapper:
    """수동 센서 매핑 도구"""
    
    def __init__(self):
        """초기화"""
        self.mapping = {}  # locker_id -> 상세 매핑 정보
        self.reverse_mapping = {}  # (serial_port, chip_idx, pin) -> locker_id
        
        # 설정 파일 경로
        project_root = Path(__file__).parent.parent.parent
        self.config_file = project_root / "config" / "sensor_mapping_detailed.json"
        self.legacy_file = project_root / "config" / "sensor_mapping.json"
        
        # 기존 매핑 로드
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
            
            print(f"\n✅ 상세 매핑 저장: {self.config_file}")
            
            # 기존 형식 매핑도 업데이트
            self._update_legacy_mapping()
            
        except Exception as e:
            print(f"❌ 매핑 저장 실패: {e}")
    
    def _update_legacy_mapping(self):
        """기존 sensor_mapping.json 형식도 업데이트"""
        try:
            legacy_mapping = {}
            
            # 센서 번호 계산: chip_idx * 16 + pin + 1
            for locker_id, info in self.mapping.items():
                sensor_num = info['chip_index'] * 16 + info['pin'] + 1
                legacy_mapping[str(sensor_num)] = locker_id
            
            legacy_data = {
                "description": "센서 번호와 락커 ID 매핑 (실제 물리적 연결 기준)",
                "note": "manual_sensor_mapper.py로 생성됨",
                "last_updated": datetime.now().isoformat(),
                "total_sensors": len(legacy_mapping),
                "mapping": legacy_mapping
            }
            
            with open(self.legacy_file, 'w', encoding='utf-8') as f:
                json.dump(legacy_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 기존 형식 매핑 저장: {self.legacy_file}")
            
        except Exception as e:
            print(f"⚠️ 기존 형식 업데이트 실패: {e}")
    
    def add_mapping(self, locker_id: str, serial_port: str, chip_idx: int, 
                    chip_addr: str, pin: int) -> bool:
        """매핑 추가
        
        Args:
            locker_id: 락커 ID (예: S01, M01, F01)
            serial_port: 시리얼 포트 (예: /dev/ttyUSB0)
            chip_idx: 칩 인덱스 (0부터 시작)
            chip_addr: 칩 주소 (예: 0x26)
            pin: 핀 번호 (0-15)
            
        Returns:
            성공 여부
        """
        try:
            # 중복 체크
            key = (serial_port, chip_idx, pin)
            if key in self.reverse_mapping:
                existing = self.reverse_mapping[key]
                print(f"⚠️ 경고: 이 센서는 이미 {existing}에 매핑되어 있습니다!")
                response = input("덮어쓰시겠습니까? (y/N): ").strip().lower()
                if response != 'y':
                    return False
                # 기존 매핑 제거
                del self.mapping[existing]
            
            # 구역 판정
            if locker_id.startswith('S'):
                zone = 'STAFF'
            elif locker_id.startswith('M'):
                zone = 'MALE'
            elif locker_id.startswith('F'):
                zone = 'FEMALE'
            else:
                zone = 'UNKNOWN'
            
            # 매핑 추가
            self.mapping[locker_id] = {
                "serial_port": serial_port,
                "chip_index": chip_idx,
                "chip_address": chip_addr,
                "pin": pin,
                "zone": zone,
                "verified": True,
                "verified_at": datetime.now().isoformat()
            }
            
            # 역매핑 업데이트
            self.reverse_mapping[key] = locker_id
            
            print(f"✅ {locker_id} 매핑 추가 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 매핑 추가 실패: {e}")
            return False
    
    def remove_mapping(self, locker_id: str) -> bool:
        """매핑 제거"""
        if locker_id not in self.mapping:
            print(f"⚠️ {locker_id}는 매핑되어 있지 않습니다.")
            return False
        
        info = self.mapping[locker_id]
        key = (info['serial_port'], info['chip_index'], info['pin'])
        
        del self.mapping[locker_id]
        if key in self.reverse_mapping:
            del self.reverse_mapping[key]
        
        print(f"✅ {locker_id} 매핑 제거 완료!")
        return True
    
    def print_mapping_summary(self):
        """매핑 요약 출력"""
        print("\n" + "="*70)
        print("📊 현재 매핑 상태")
        print("="*70)
        
        if not self.mapping:
            print("매핑된 락커가 없습니다.")
            return
        
        # 구역별로 그룹화
        zones = {'STAFF': [], 'MALE': [], 'FEMALE': [], 'UNKNOWN': []}
        for locker_id in sorted(self.mapping.keys()):
            zone = self.mapping[locker_id]['zone']
            zones[zone].append(locker_id)
        
        for zone in ['STAFF', 'MALE', 'FEMALE', 'UNKNOWN']:
            lockers = zones[zone]
            if not lockers:
                continue
            
            zone_names = {
                'STAFF': '교직원',
                'MALE': '남성',
                'FEMALE': '여성',
                'UNKNOWN': '기타'
            }
            
            print(f"\n{zone_names[zone]} 구역: {len(lockers)}개")
            print("-" * 70)
            
            for locker_id in lockers:
                info = self.mapping[locker_id]
                print(f"  {locker_id}: {info['serial_port']:12s} | "
                      f"Chip={info['chip_index']}({info['chip_address']}) | "
                      f"Pin={info['pin']:2d}")
        
        print(f"\n{'='*70}")
        print(f"총 {len(self.mapping)}개 락커 매핑됨")
        print("="*70)
    
    def interactive_mode(self):
        """인터랙티브 모드"""
        print("="*70)
        print("🔧 수동 센서 매핑 도구")
        print("="*70)
        print("\n사용 방법:")
        print("1. 터미널에서 라즈베리파이 로그를 모니터링합니다:")
        print("   ssh pi@raspberry-pi 'tail -f ~/gym-controller/logs/locker_system.log | grep LOW'")
        print("\n2. 락커 키를 순서대로 빼면서 로그에서 센서 정보를 확인합니다.")
        print("\n3. 이 프로그램에서 락커 ID와 센서 정보를 입력합니다.")
        print("\n명령어:")
        print("  add    - 새 매핑 추가")
        print("  remove - 매핑 제거")
        print("  list   - 현재 매핑 목록 보기")
        print("  save   - 매핑 저장")
        print("  quit   - 종료")
        print("="*70)
        
        while True:
            print()
            command = input("명령어 입력 (add/remove/list/save/quit): ").strip().lower()
            
            if command == 'quit' or command == 'q':
                response = input("\n저장하고 종료하시겠습니까? (Y/n): ").strip().lower()
                if response != 'n':
                    self.save_mapping()
                print("👋 프로그램을 종료합니다.")
                break
            
            elif command == 'add' or command == 'a':
                self._interactive_add()
            
            elif command == 'remove' or command == 'r':
                locker_id = input("제거할 락커 ID: ").strip().upper()
                self.remove_mapping(locker_id)
            
            elif command == 'list' or command == 'l':
                self.print_mapping_summary()
            
            elif command == 'save' or command == 's':
                self.save_mapping()
            
            else:
                print("❌ 알 수 없는 명령어입니다.")
    
    def _interactive_add(self):
        """인터랙티브 매핑 추가"""
        try:
            print("\n--- 새 매핑 추가 ---")
            
            # 락커 ID 입력
            locker_id = input("락커 ID (예: S01, M01, F01): ").strip().upper()
            if not locker_id:
                print("❌ 취소됨")
                return
            
            # 시리얼 포트 입력
            print("\n시리얼 포트 선택:")
            print("  1. /dev/ttyUSB0 (남녀 혼성)")
            print("  2. /dev/ttyUSB1 (교직원)")
            print("  3. 직접 입력")
            
            port_choice = input("선택 (1-3): ").strip()
            if port_choice == '1':
                serial_port = '/dev/ttyUSB0'
            elif port_choice == '2':
                serial_port = '/dev/ttyUSB1'
            elif port_choice == '3':
                serial_port = input("시리얼 포트 입력: ").strip()
            else:
                print("❌ 취소됨")
                return
            
            # 칩 인덱스 입력
            chip_idx_str = input("칩 인덱스 (0-15, 보통 0): ").strip()
            chip_idx = int(chip_idx_str) if chip_idx_str else 0
            
            # 칩 주소 입력
            chip_addr = input("칩 주소 (예: 0x26, 로그에서 'addr' 확인): ").strip()
            if not chip_addr:
                chip_addr = "0x00"
            
            # 핀 번호 입력
            pin_str = input("핀 번호 (0-15, 로그에서 'pin' 확인): ").strip()
            if not pin_str:
                print("❌ 핀 번호는 필수입니다.")
                return
            pin = int(pin_str)
            
            # 매핑 추가
            if self.add_mapping(locker_id, serial_port, chip_idx, chip_addr, pin):
                # 자동 저장 옵션
                response = input("지금 저장하시겠습니까? (Y/n): ").strip().lower()
                if response != 'n':
                    self.save_mapping()
        
        except ValueError as e:
            print(f"❌ 입력 오류: 숫자를 입력해주세요. ({e})")
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
    
    def batch_mode(self, locker_list: list):
        """배치 모드 - 여러 락커를 순서대로 입력"""
        print("\n" + "="*70)
        print(f"📝 배치 모드: {len(locker_list)}개 락커 매핑")
        print("="*70)
        print("\n순서대로 락커 키를 빼면서 센서 정보를 입력하세요.")
        print("(Enter만 입력하면 건너뜀, 'quit'을 입력하면 종료)\n")
        
        for idx, locker_id in enumerate(locker_list, 1):
            print(f"\n[{idx}/{len(locker_list)}] {locker_id}")
            
            # 이미 매핑된 경우
            if locker_id in self.mapping:
                info = self.mapping[locker_id]
                print(f"  현재: {info['serial_port']} | Chip={info['chip_index']} | Pin={info['pin']}")
                response = input("  다시 입력하시겠습니까? (y/N): ").strip().lower()
                if response != 'y':
                    continue
            
            # 센서 정보 입력
            print("  로그에서 센서 정보를 확인하고 입력하세요:")
            
            # 시리얼 포트
            port_input = input("    시리얼 포트 (1=USB0, 2=USB1, 직접입력): ").strip()
            if port_input.lower() == 'quit':
                break
            if not port_input:
                print("  ⏭️  건너뜀")
                continue
            
            if port_input == '1':
                serial_port = '/dev/ttyUSB0'
            elif port_input == '2':
                serial_port = '/dev/ttyUSB1'
            else:
                serial_port = port_input
            
            # 칩 인덱스
            chip_input = input("    칩 인덱스 (기본 0): ").strip()
            chip_idx = int(chip_input) if chip_input else 0
            
            # 칩 주소
            addr_input = input("    칩 주소 (예: 0x26): ").strip()
            chip_addr = addr_input if addr_input else "0x00"
            
            # 핀 번호
            pin_input = input("    핀 번호 (0-15): ").strip()
            if not pin_input:
                print("  ⏭️  핀 번호 없음, 건너뜀")
                continue
            
            try:
                pin = int(pin_input)
                self.add_mapping(locker_id, serial_port, chip_idx, chip_addr, pin)
            except ValueError:
                print(f"  ❌ 잘못된 핀 번호: {pin_input}")
        
        # 완료 후 저장
        print("\n" + "="*70)
        print("✅ 배치 입력 완료!")
        self.print_mapping_summary()
        
        response = input("\n저장하시겠습니까? (Y/n): ").strip().lower()
        if response != 'n':
            self.save_mapping()


def main():
    """메인 함수"""
    import sys
    
    mapper = ManualSensorMapper()
    
    # 명령줄 인자 확인
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == 'staff':
            # 교직원 배치 모드
            locker_list = [f"S{i:02d}" for i in range(1, 11)]
            mapper.batch_mode(locker_list)
        
        elif mode == 'male':
            # 남성 배치 모드
            locker_list = [f"M{i:02d}" for i in range(1, 41)]
            mapper.batch_mode(locker_list)
        
        elif mode == 'female':
            # 여성 배치 모드
            locker_list = [f"F{i:02d}" for i in range(1, 11)]
            mapper.batch_mode(locker_list)
        
        elif mode == 'list':
            # 목록 보기
            mapper.print_mapping_summary()
        
        else:
            print(f"알 수 없는 모드: {mode}")
            print("사용법: python manual_sensor_mapper.py [staff|male|female|list]")
    
    else:
        # 인터랙티브 모드
        try:
            mapper.interactive_mode()
        except KeyboardInterrupt:
            print("\n\n⚠️ 중단됨 (Ctrl+C)")
            response = input("저장하시겠습니까? (Y/n): ").strip().lower()
            if response != 'n':
                mapper.save_mapping()


if __name__ == "__main__":
    main()

