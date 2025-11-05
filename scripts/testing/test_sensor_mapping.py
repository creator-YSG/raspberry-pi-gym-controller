#!/usr/bin/env python3
"""
센서 매핑 테스트 도구

각 센서를 실제로 테스트해서 어떤 락커에 연결되어 있는지 확인합니다.
물리적으로 키를 넣었다 뺐다 하면서 센서 번호와 락커 번호를 매핑합니다.

사용법:
    python3 scripts/testing/test_sensor_mapping.py
"""

import sys
import json
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import logging
from datetime import datetime
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SensorMappingTester:
    """센서 매핑 테스트 클래스"""
    
    def __init__(self):
        self.detected_sensors = deque(maxlen=100)
        self.mapping = {}
        self.config_file = project_root / "config" / "sensor_mapping.json"
    
    def load_current_mapping(self):
        """현재 매핑 로드"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.mapping = config.get("mapping", {})
                    logger.info(f"✅ 현재 매핑 로드 완료: {len(self.mapping)}개")
            else:
                logger.warning("⚠️ 매핑 파일 없음, 새로 생성합니다")
                self.mapping = {}
        except Exception as e:
            logger.error(f"❌ 매핑 로드 실패: {e}")
            self.mapping = {}
    
    def save_mapping(self):
        """매핑을 파일에 저장"""
        try:
            config = {
                "description": "센서 번호와 락커 ID 매핑 (실제 물리적 연결 기준)",
                "note": "이 파일은 test_sensor_mapping.py로 생성되었습니다",
                "total_sensors": len(self.mapping),
                "last_updated": datetime.now().isoformat(),
                "mapping": self.mapping
            }
            
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 매핑 저장 완료: {self.config_file}")
            logger.info(f"   총 {len(self.mapping)}개 센서 매핑")
            
        except Exception as e:
            logger.error(f"❌ 매핑 저장 실패: {e}")
    
    async def monitor_sensors(self):
        """센서 이벤트 모니터링"""
        from core.esp32_manager import create_auto_esp32_manager
        
        logger.info("🔍 ESP32 연결 중...")
        manager = await create_auto_esp32_manager()
        
        if not manager or len(manager.devices) == 0:
            logger.error("❌ ESP32 연결 실패")
            return
        
        logger.info(f"✅ {len(manager.devices)}개 ESP32 연결 완료")
        logger.info("")
        logger.info("=" * 60)
        logger.info("센서 매핑 테스트 시작")
        logger.info("=" * 60)
        logger.info("")
        logger.info("📋 작업 순서:")
        logger.info("  1. 락커에서 키를 빼세요")
        logger.info("  2. 어떤 센서 번호가 감지되는지 확인")
        logger.info("  3. 락커 번호를 입력")
        logger.info("  4. 다음 락커로 진행")
        logger.info("")
        logger.info("💡 팁: 키를 빼고 다시 넣으면 같은 센서의 HIGH/LOW 이벤트를 볼 수 있습니다")
        logger.info("")
        
        # 센서 이벤트 핸들러
        async def handle_sensor(event_data):
            sensor_num = event_data.get("chip_idx", 0) * 100 + event_data.get("pin", 0)
            state = event_data.get("state", "UNKNOWN")
            
            # 간단한 센서 번호 매핑 (실제 핀 번호 사용)
            pin = event_data.get("pin", 0)
            chip = event_data.get("chip_idx", 0)
            
            # 실제 센서 번호 계산 (칩당 16핀 가정)
            actual_sensor = chip * 16 + pin + 1
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 🔔 센서 감지: #{actual_sensor} (Chip{chip} Pin{pin}) → {state}")
            
            self.detected_sensors.append({
                "sensor_num": actual_sensor,
                "chip": chip,
                "pin": pin,
                "state": state,
                "time": timestamp
            })
        
        # 이벤트 핸들러 등록
        manager.register_event_handler("sensor_triggered", handle_sensor)
        
        logger.info("⏳ 센서 모니터링 중... (Ctrl+C로 종료)")
        logger.info("")
        
        try:
            # 백그라운드에서 계속 모니터링
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️ 모니터링 중지")
    
    async def interactive_mapping(self):
        """대화형 매핑 작업"""
        self.load_current_mapping()
        
        print("\n" + "=" * 60)
        print("🗺️  센서 매핑 대화형 모드")
        print("=" * 60)
        print()
        print("명령어:")
        print("  add <센서번호> <락커ID>  - 매핑 추가 (예: add 15 M05)")
        print("  show                      - 현재 매핑 보기")
        print("  save                      - 파일에 저장")
        print("  load                      - 파일에서 로드")
        print("  delete <센서번호>         - 매핑 삭제")
        print("  exit                      - 종료")
        print()
        
        while True:
            try:
                cmd = input("명령> ").strip()
                
                if not cmd:
                    continue
                
                parts = cmd.split()
                action = parts[0].lower()
                
                if action == "exit":
                    print("👋 종료합니다")
                    break
                
                elif action == "add" and len(parts) == 3:
                    sensor_num = parts[1]
                    locker_id = parts[2].upper()
                    self.mapping[sensor_num] = locker_id
                    print(f"✅ 추가: 센서 {sensor_num} → {locker_id}")
                
                elif action == "show":
                    print(f"\n현재 매핑: {len(self.mapping)}개")
                    for sensor, locker in sorted(self.mapping.items(), key=lambda x: int(x[0])):
                        print(f"  센서 {sensor:>3} → {locker}")
                    print()
                
                elif action == "save":
                    self.save_mapping()
                
                elif action == "load":
                    self.load_current_mapping()
                
                elif action == "delete" and len(parts) == 2:
                    sensor_num = parts[1]
                    if sensor_num in self.mapping:
                        del self.mapping[sensor_num]
                        print(f"✅ 삭제: 센서 {sensor_num}")
                    else:
                        print(f"❌ 센서 {sensor_num} 없음")
                
                else:
                    print("❌ 잘못된 명령어")
            
            except KeyboardInterrupt:
                print("\n👋 종료합니다")
                break
            except Exception as e:
                print(f"❌ 오류: {e}")


async def main():
    """메인 함수"""
    tester = SensorMappingTester()
    
    print("\n센서 매핑 테스트 도구")
    print("=" * 60)
    print("1. 센서 모니터링 (실시간 센서 이벤트 보기)")
    print("2. 대화형 매핑 편집")
    print()
    
    choice = input("선택 (1/2): ").strip()
    
    if choice == "1":
        await tester.monitor_sensors()
    elif choice == "2":
        await tester.interactive_mapping()
    else:
        print("❌ 잘못된 선택")


if __name__ == "__main__":
    asyncio.run(main())

