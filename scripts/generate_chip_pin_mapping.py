#!/usr/bin/env python3
"""sensor_mapping.json의 센서 번호를 역산해서 Chip+Pin 매핑 생성"""

import json
from pathlib import Path

# sensor_mapping.json에서 센서 번호 추출
config_file = Path(__file__).parent.parent / "config" / "sensor_mapping.json"
with open(config_file, 'r') as f:
    config = json.load(f)
    sensor_numbers = [int(k) for k in config['mapping'].keys()]

# 센서 번호를 역산해서 Chip+Pin 매핑 생성
# 공식: sensor_num = (chip_idx * 16) + pin + 1
# 역산: chip_idx = (sensor_num - 1) // 16, pin = (sensor_num - 1) % 16

chip_pin_to_sensor = {}

for sensor_num in sorted(sensor_numbers):
    chip_idx = (sensor_num - 1) // 16
    pin = (sensor_num - 1) % 16
    chip_pin_to_sensor[(chip_idx, pin)] = sensor_num
    locker_id = config['mapping'][str(sensor_num)]
    print(f"  ({chip_idx}, {pin:2d}): {sensor_num:2d},  # 센서 {sensor_num:2d}번 → {locker_id}")

print(f"\n총 {len(chip_pin_to_sensor)}개 매핑 생성됨")

# Chip별로 그룹화
chips = {}
for (chip, pin), sensor in chip_pin_to_sensor.items():
    if chip not in chips:
        chips[chip] = []
    chips[chip].append((pin, sensor, config['mapping'][str(sensor)]))

print("\n" + "="*60)
print("Chip별 분류 (app/__init__.py에 사용할 형식):")
print("="*60)

for chip in sorted(chips.keys()):
    print(f"\n            # Chip{chip} 매핑")
    for pin, sensor, locker in sorted(chips[chip]):
        print(f"            ({chip}, {pin:2d}): {sensor:2d},  # 센서 {sensor:2d}번 → {locker}")

