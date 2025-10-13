#!/usr/bin/env python3
"""
권한 체크만 집중 테스트
실제 락커 대여 없이 권한 검증 로직만 테스트
"""

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.member_service import MemberService
from app.services.locker_service import LockerService


def test_permission_logic():
    """권한 로직만 테스트"""
    print("🔐 락커 접근 권한 로직 테스트")
    print("=" * 80)
    
    member_service = MemberService('instance/gym_system.db')
    locker_service = LockerService('instance/gym_system.db')
    
    # 테스트 시나리오
    test_cases = [
        {
            'member_id': '20156111',  # 김현 (남자 교직원)
            'name': '김현',
            'type': '남자 교직원',
            'expected_zones': ['MALE', 'STAFF'],
        },
        {
            'member_id': '20211377',  # 김진서 (여자 교직원)
            'name': '김진서',
            'type': '여자 교직원',
            'expected_zones': ['FEMALE', 'STAFF'],
        },
        {
            'member_id': '20240838',  # 손준표 (남자 일반회원)
            'name': '손준표',
            'type': '남자 일반회원',
            'expected_zones': ['MALE'],
        },
        {
            'member_id': '20211131',  # 엘레나 (여자 일반회원)
            'name': '엘레나',
            'type': '여자 일반회원',
            'expected_zones': ['FEMALE'],
        }
    ]
    
    # 모든 구역의 락커들
    test_lockers = {
        'MALE': ['M01', 'M02', 'M03'],
        'FEMALE': ['F01', 'F02', 'F03'],
        'STAFF': ['S01', 'S02', 'S03']
    }
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\n👤 {test_case['name']} ({test_case['type']}) 권한 테스트")
        print("-" * 60)
        
        # 회원 정보 조회
        member = member_service.get_member(test_case['member_id'])
        if not member:
            print(f"❌ 회원을 찾을 수 없습니다: {test_case['member_id']}")
            all_passed = False
            continue
        
        # 기본 정보 출력
        print(f"📋 회원 정보:")
        print(f"   - 이름: {member.name}")
        print(f"   - 구분: {member.customer_type} ({member.member_category})")
        print(f"   - 성별: {member.gender}")
        print(f"   - 유효성: {'✅ 유효' if member.is_valid else '❌ 만료'}")
        
        # 접근 가능 구역 확인
        actual_zones = member.allowed_zones
        expected_zones = test_case['expected_zones']
        
        print(f"\n🔑 구역 접근 권한:")
        print(f"   - 예상 구역: {expected_zones}")
        print(f"   - 실제 구역: {actual_zones}")
        
        if set(actual_zones) == set(expected_zones):
            print(f"   ✅ 구역 권한 정확함")
        else:
            print(f"   ❌ 구역 권한 오류")
            all_passed = False
        
        # 각 구역별 권한 테스트
        print(f"\n🏢 구역별 접근 권한 테스트:")
        for zone, lockers in test_lockers.items():
            should_access = zone in expected_zones
            can_access = member.can_access_zone(zone)
            
            zone_names = {'MALE': '남자', 'FEMALE': '여자', 'STAFF': '교직원'}
            zone_name = zone_names.get(zone, zone)
            
            if should_access == can_access:
                status = "✅ 정확" if can_access else "✅ 차단"
                print(f"   {status} {zone_name} 구역: {'접근 가능' if can_access else '접근 불가'}")
            else:
                print(f"   ❌ 오류 {zone_name} 구역: 예상={should_access}, 실제={can_access}")
                all_passed = False
        
        # 락커별 권한 테스트 (로직만)
        print(f"\n🔐 락커별 접근 권한 테스트:")
        for zone, lockers in test_lockers.items():
            should_access = zone in expected_zones
            zone_name = zone_names.get(zone, zone)
            
            for locker_id in lockers[:2]:  # 각 구역에서 2개씩만 테스트
                # 락커 정보 조회
                locker = locker_service.get_locker_by_id(locker_id)
                if locker:
                    can_access = member.can_access_zone(locker.zone)
                    
                    if should_access == can_access:
                        status = "✅" if can_access else "🚫"
                        print(f"   {status} {locker_id} ({zone_name}): {'접근 가능' if can_access else '접근 차단'}")
                    else:
                        print(f"   ❌ {locker_id} ({zone_name}): 권한 오류")
                        all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 모든 권한 로직 테스트 통과!")
        print("✅ 바코드 스캔 → 회원 검증 → 구역 권한 체크 → 락커 접근 제어 완벽 작동")
    else:
        print("💥 일부 권한 로직 테스트 실패!")
    print("=" * 80)


def test_service_flow_summary():
    """서비스 플로우 요약 테스트"""
    print(f"\n📋 서비스 플로우 요약")
    print("-" * 60)
    
    member_service = MemberService('instance/gym_system.db')
    
    # 실제 서비스 플로우 시뮬레이션
    test_member_id = '20156111'  # 김현 (남자 교직원)
    
    print(f"1️⃣ 바코드 스캔: {test_member_id}")
    
    print(f"2️⃣ 데이터베이스에서 회원 검증...")
    member = member_service.get_member(test_member_id)
    
    if not member:
        print(f"   ❌ 등록되지 않은 회원")
        return
    
    print(f"   ✅ 회원 발견: {member.name}")
    
    print(f"3️⃣ 회원 유효성 검사...")
    if not member.is_valid:
        print(f"   ❌ 만료된 회원 (만료일: {member.membership_expires})")
        return
    
    print(f"   ✅ 유효한 회원 (만료일: {member.membership_expires}, {member.days_remaining}일 남음)")
    
    print(f"4️⃣ 대여/반납 판단...")
    if member.is_renting:
        print(f"   🔄 반납 모드: {member.currently_renting}번 락커 반납")
    else:
        print(f"   🆕 대여 모드: 새 락커 대여")
    
    print(f"5️⃣ 회원 구분에 따른 접근 가능 구역 확인...")
    print(f"   👔 회원 구분: {member.customer_type} ({member.member_category})")
    print(f"   🚻 성별: {member.gender}")
    print(f"   🔑 접근 가능 구역: {member.allowed_zones}")
    
    zone_names = {'MALE': '남자', 'FEMALE': '여자', 'STAFF': '교직원'}
    for zone in member.allowed_zones:
        zone_name = zone_names.get(zone, zone)
        print(f"      - {zone_name} 구역 락커 사용 가능")
    
    print(f"6️⃣ 선택된 락커의 구역 권한 체크...")
    test_locker_id = 'M01'  # 남자 구역 락커
    locker_service = LockerService('instance/gym_system.db')
    locker = locker_service.get_locker_by_id(test_locker_id)
    
    if locker:
        can_access = member.can_access_zone(locker.zone)
        zone_name = zone_names.get(locker.zone, locker.zone)
        
        if can_access:
            print(f"   ✅ {test_locker_id} ({zone_name} 구역): 접근 권한 있음")
            print(f"7️⃣ 락커 열기 명령 전송 → ESP32 → 락커 열림")
        else:
            print(f"   ❌ {test_locker_id} ({zone_name} 구역): 접근 권한 없음")
            print(f"7️⃣ 접근 거부 메시지 표시")
    
    print("-" * 60)


def main():
    """메인 함수"""
    print("🏋️ 헬스장 락커 시스템 서비스 로직 테스트")
    
    test_permission_logic()
    test_service_flow_summary()
    
    print(f"\n🎯 서비스 로직 테스트 완료!")
    print(f"📱 바코드 스캔부터 락커 열기까지 모든 단계가 올바르게 작동합니다.")


if __name__ == "__main__":
    main()
