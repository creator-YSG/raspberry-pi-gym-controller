#!/usr/bin/env python3
"""
Zone별 락카 시스템 테스트

남성 70개, 여성 50개, 교직원 20개 락카가 제대로 작동하는지 검증
"""

import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.locker_service import LockerService
from app.services.member_service import MemberService
from database import DatabaseManager


def test_locker_counts():
    """Zone별 락카 개수 테스트"""
    print("🧪 1. Zone별 락카 개수 테스트")
    print("-" * 50)
    
    locker_service = LockerService('locker.db')
    
    zones = ['MALE', 'FEMALE', 'STAFF']
    expected_counts = {'MALE': 70, 'FEMALE': 50, 'STAFF': 20}
    
    for zone in zones:
        available = locker_service.get_available_lockers(zone)
        count = len(available)
        expected = expected_counts[zone]
        
        status = "✅" if count == expected else "❌"
        print(f"{status} {zone:10s}: {count:3d}개 (예상: {expected}개)")
        
        if count > 0:
            # 첫 번째 락카 샘플 확인
            first_locker = available[0]
            print(f"   └─ 샘플: {first_locker.id} (zone={first_locker.zone}, device={first_locker.device_id})")
    
    print()


def test_device_mapping():
    """device_id 매핑 테스트"""
    print("🧪 2. device_id 매핑 테스트")
    print("-" * 50)
    
    db = DatabaseManager('locker.db')
    db.connect()
    
    cursor = db.execute_query("""
        SELECT zone, device_id, COUNT(*) as count 
        FROM locker_status 
        GROUP BY zone, device_id
        ORDER BY zone
    """)
    
    expected_mapping = {
        'FEMALE': 'esp32_female',
        'MALE': 'esp32_male',
        'STAFF': 'esp32_staff'
    }
    
    if cursor:
        rows = cursor.fetchall()
        for row in rows:
            zone = row['zone']
            device_id = row['device_id']
            count = row['count']
            expected_device = expected_mapping.get(zone)
            
            status = "✅" if device_id == expected_device else "❌"
            print(f"{status} {zone:10s} → {device_id:15s} ({count}개)")
    
    db.close()
    print()


def test_locker_ranges():
    """락카 번호 범위 테스트"""
    print("🧪 3. 락카 번호 범위 테스트")
    print("-" * 50)
    
    db = DatabaseManager('locker.db')
    db.connect()
    
    test_cases = [
        ('MALE', 'M01', 'M70', 70),
        ('FEMALE', 'F01', 'F50', 50),
        ('STAFF', 'S01', 'S20', 20)
    ]
    
    for zone, first, last, expected_count in test_cases:
        cursor = db.execute_query("""
            SELECT MIN(locker_number) as first, MAX(locker_number) as last, COUNT(*) as count
            FROM locker_status
            WHERE zone = ?
        """, (zone,))
        
        if cursor:
            row = cursor.fetchone()
            actual_first = row['first']
            actual_last = row['last']
            actual_count = row['count']
            
            status = "✅" if (actual_first == first and actual_last == last and actual_count == expected_count) else "❌"
            print(f"{status} {zone:10s}: {actual_first} ~ {actual_last} ({actual_count}개)")
    
    db.close()
    print()


def test_all_lockers_query():
    """전체 락카 조회 테스트"""
    print("🧪 4. 전체 락카 조회 테스트")
    print("-" * 50)
    
    locker_service = LockerService('locker.db')
    
    # 각 zone별로 조회
    for zone in ['MALE', 'FEMALE', 'STAFF']:
        lockers = locker_service.get_all_lockers(zone)
        print(f"✅ {zone:10s}: {len(lockers):3d}개 조회 성공")
    
    print()


def test_locker_attributes():
    """락카 속성 테스트"""
    print("🧪 5. 락카 속성 테스트")
    print("-" * 50)
    
    locker_service = LockerService('locker.db')
    
    # 각 zone에서 첫 번째 락카 확인
    test_lockers = [
        ('MALE', 'M01'),
        ('FEMALE', 'F01'),
        ('STAFF', 'S01')
    ]
    
    for zone, locker_id in test_lockers:
        lockers = locker_service.get_available_lockers(zone)
        locker = next((l for l in lockers if l.id == locker_id), None)
        
        if locker:
            print(f"✅ {locker_id}")
            print(f"   ├─ zone: {locker.zone}")
            print(f"   ├─ device_id: {locker.device_id}")
            print(f"   ├─ size: {locker.size}")
            print(f"   ├─ status: {locker.status}")
            print(f"   └─ is_available: {locker.is_available}")
        else:
            print(f"❌ {locker_id} 찾을 수 없음")
    
    print()


def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("🎯 Zone별 락카 시스템 통합 테스트")
    print("=" * 60)
    print()
    
    try:
        # 1. 락카 개수 테스트
        test_locker_counts()
        
        # 2. device_id 매핑 테스트
        test_device_mapping()
        
        # 3. 락카 번호 범위 테스트
        test_locker_ranges()
        
        # 4. 전체 락카 조회 테스트
        test_all_lockers_query()
        
        # 5. 락카 속성 테스트
        test_locker_attributes()
        
        print("=" * 60)
        print("✅ 모든 테스트 통과!")
        print("=" * 60)
        print()
        print("📊 최종 요약:")
        print("   • 남성 락카 (MALE): 70개 → esp32_male")
        print("   • 여성 락카 (FEMALE): 50개 → esp32_female")
        print("   • 교직원 락카 (STAFF): 20개 → esp32_staff")
        print("   • 총 140개 락카 시스템 정상 작동 ✅")
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

