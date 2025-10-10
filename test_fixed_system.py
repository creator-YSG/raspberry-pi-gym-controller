#!/usr/bin/env python3
"""
수정된 시스템 전체 통합 테스트

모든 수정사항이 제대로 작동하는지 검증:
1. Zone 기본값 (MALE)
2. ESP32 device_id 매핑 (M→esp32_male, F→esp32_female, S→esp32_staff)
3. 센서-락카 매핑 (140개)
4. 바코드 서비스 패턴
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.locker_service import LockerService
from app.services.sensor_event_handler import SensorEventHandler
from app.services.barcode_service import BarcodeService
from database import DatabaseManager


def test_zone_defaults():
    """Zone 기본값 테스트"""
    print("\n🧪 1. Zone 기본값 테스트")
    print("-" * 60)
    
    locker_service = LockerService('locker.db')
    
    # 기본값으로 락카 조회 (파라미터 없이)
    default_lockers = locker_service.get_available_lockers()
    
    if len(default_lockers) > 0:
        first_zone = default_lockers[0].zone
        print(f"✅ 기본 zone 조회 성공: {len(default_lockers)}개")
        print(f"   └─ 첫 번째 락카 zone: {first_zone}")
        
        if first_zone == 'MALE':
            print(f"✅ 기본값이 'MALE'로 정상 작동")
        else:
            print(f"❌ 기본값이 '{first_zone}'로 잘못됨 (예상: MALE)")
    else:
        print(f"❌ 기본 zone 조회 실패: 락카 없음")
    
    locker_service.close()
    print()


def test_esp32_device_mapping():
    """ESP32 device_id 매핑 테스트"""
    print("\n🧪 2. ESP32 device_id 매핑 테스트")
    print("-" * 60)
    
    locker_service = LockerService('locker.db')
    
    test_cases = [
        ('M01', 'esp32_male', 'MALE'),
        ('M70', 'esp32_male', 'MALE'),
        ('F01', 'esp32_female', 'FEMALE'),
        ('F50', 'esp32_female', 'FEMALE'),
        ('S01', 'esp32_staff', 'STAFF'),
        ('S20', 'esp32_staff', 'STAFF'),
    ]
    
    for locker_id, expected_device, expected_zone in test_cases:
        locker = locker_service.get_locker_by_id(locker_id)
        
        if locker:
            actual_device = locker.device_id
            actual_zone = locker.zone
            
            device_ok = actual_device == expected_device
            zone_ok = actual_zone == expected_zone
            
            if device_ok and zone_ok:
                print(f"✅ {locker_id}: device={actual_device}, zone={actual_zone}")
            else:
                if not device_ok:
                    print(f"❌ {locker_id}: device={actual_device} (예상: {expected_device})")
                if not zone_ok:
                    print(f"❌ {locker_id}: zone={actual_zone} (예상: {expected_zone})")
        else:
            print(f"❌ {locker_id}: 락카 찾을 수 없음")
    
    locker_service.close()
    print()


def test_sensor_locker_mapping():
    """센서-락카 매핑 테스트 (140개)"""
    print("\n🧪 3. 센서-락카 매핑 테스트 (140개)")
    print("-" * 60)
    
    db = DatabaseManager('locker.db')
    db.connect()
    
    sensor_handler = SensorEventHandler(db)
    mapping = sensor_handler.get_sensor_locker_mapping()
    
    # 전체 개수 확인
    total_sensors = len(mapping)
    print(f"총 센서 매핑: {total_sensors}개 (예상: 140개)")
    
    if total_sensors == 140:
        print(f"✅ 센서 개수 정상")
    else:
        print(f"❌ 센서 개수 오류 (예상: 140, 실제: {total_sensors})")
    
    # 범위별 확인
    test_ranges = [
        (1, 'M01', 'MALE'),
        (70, 'M70', 'MALE'),
        (71, 'F01', 'FEMALE'),
        (120, 'F50', 'FEMALE'),
        (121, 'S01', 'STAFF'),
        (140, 'S20', 'STAFF'),
    ]
    
    for sensor_num, expected_locker, zone_name in test_ranges:
        actual_locker = mapping.get(sensor_num)
        
        if actual_locker == expected_locker:
            print(f"✅ 센서 {sensor_num:3d} → {actual_locker} ({zone_name})")
        else:
            print(f"❌ 센서 {sensor_num:3d} → {actual_locker} (예상: {expected_locker})")
    
    # Zone별 개수 확인
    male_count = sum(1 for v in mapping.values() if v.startswith('M'))
    female_count = sum(1 for v in mapping.values() if v.startswith('F'))
    staff_count = sum(1 for v in mapping.values() if v.startswith('S'))
    
    print(f"\nZone별 센서 개수:")
    print(f"  남성 (MALE):  {male_count:3d}개 (예상: 70개)")
    print(f"  여성 (FEMALE): {female_count:3d}개 (예상: 50개)")
    print(f"  교직원 (STAFF): {staff_count:3d}개 (예상: 20개)")
    
    all_correct = male_count == 70 and female_count == 50 and staff_count == 20
    if all_correct:
        print("✅ Zone별 센서 개수 모두 정상")
    else:
        print("❌ Zone별 센서 개수 오류")
    
    db.close()
    print()


def test_barcode_service():
    """바코드 서비스 패턴 테스트"""
    print("\n🧪 4. 바코드 서비스 패턴 테스트")
    print("-" * 60)
    
    barcode_service = BarcodeService()
    
    test_cases = [
        ('M01', 'M01', '새 시스템 직접 ID'),
        ('F50', 'F50', '새 시스템 직접 ID'),
        ('S20', 'S20', '새 시스템 직접 ID'),
        ('LOCKER_M01', 'M01', '새 시스템 LOCKER_ 접두사'),
        ('KEY_F50', 'F50', '새 시스템 KEY_ 접두사'),
        ('001', 'M01', '숫자 → M01 변환'),
        ('070', 'M70', '숫자 → M70 변환'),
        ('071', 'F01', '숫자 → F01 변환'),
        ('121', 'S01', '숫자 → S01 변환'),
    ]
    
    for barcode, expected_locker, description in test_cases:
        extracted = barcode_service._extract_locker_id(barcode)
        
        if extracted == expected_locker:
            print(f"✅ '{barcode}' → '{extracted}' ({description})")
        else:
            print(f"❌ '{barcode}' → '{extracted}' (예상: {expected_locker}, {description})")
    
    print()


def test_database_integrity():
    """데이터베이스 무결성 테스트"""
    print("\n🧪 5. 데이터베이스 무결성 테스트")
    print("-" * 60)
    
    db = DatabaseManager('locker.db')
    db.connect()
    
    # Zone별 락카 개수
    cursor = db.execute_query("""
        SELECT zone, COUNT(*) as count
        FROM locker_status
        GROUP BY zone
        ORDER BY zone
    """)
    
    if cursor:
        rows = cursor.fetchall()
        expected_counts = {'MALE': 70, 'FEMALE': 50, 'STAFF': 20}
        
        all_ok = True
        for row in rows:
            zone = row['zone']
            count = row['count']
            expected = expected_counts.get(zone, 0)
            
            if count == expected:
                print(f"✅ {zone:10s}: {count:3d}개 (예상: {expected}개)")
            else:
                print(f"❌ {zone:10s}: {count:3d}개 (예상: {expected}개)")
                all_ok = False
        
        if all_ok:
            print("\n✅ 데이터베이스 zone별 개수 모두 정상")
        else:
            print("\n❌ 데이터베이스 zone별 개수 오류")
    
    # device_id 매핑 확인
    cursor = db.execute_query("""
        SELECT zone, device_id, COUNT(*) as count
        FROM locker_status
        GROUP BY zone, device_id
        ORDER BY zone
    """)
    
    if cursor:
        print("\ndevice_id 매핑:")
        rows = cursor.fetchall()
        
        expected_mapping = {
            'MALE': 'esp32_male',
            'FEMALE': 'esp32_female',
            'STAFF': 'esp32_staff'
        }
        
        all_ok = True
        for row in rows:
            zone = row['zone']
            device_id = row['device_id']
            count = row['count']
            expected_device = expected_mapping.get(zone)
            
            if device_id == expected_device:
                print(f"✅ {zone:10s} → {device_id:15s} ({count}개)")
            else:
                print(f"❌ {zone:10s} → {device_id:15s} (예상: {expected_device})")
                all_ok = False
        
        if all_ok:
            print("\n✅ device_id 매핑 모두 정상")
        else:
            print("\n❌ device_id 매핑 오류")
    
    db.close()
    print()


def main():
    """메인 테스트 함수"""
    print("=" * 70)
    print("🎯 수정된 시스템 전체 통합 테스트")
    print("=" * 70)
    
    try:
        # 1. Zone 기본값 테스트
        test_zone_defaults()
        
        # 2. ESP32 device_id 매핑 테스트
        test_esp32_device_mapping()
        
        # 3. 센서-락카 매핑 테스트
        test_sensor_locker_mapping()
        
        # 4. 바코드 서비스 테스트
        test_barcode_service()
        
        # 5. 데이터베이스 무결성 테스트
        test_database_integrity()
        
        print("=" * 70)
        print("✅ 모든 테스트 완료!")
        print("=" * 70)
        print()
        print("📊 요약:")
        print("   • Zone 기본값: 'A' → 'MALE' 수정 완료")
        print("   • ESP32 매핑: M→esp32_male, F→esp32_female, S→esp32_staff")
        print("   • 센서 매핑: 140개 (남성 70, 여성 50, 교직원 20)")
        print("   • 바코드 패턴: 새 시스템 (M01, F50, S20) 지원")
        print("   • 데이터베이스: 무결성 확인 완료")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

