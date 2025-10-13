#!/usr/bin/env python3
"""
락커 권한 시스템 테스트 스크립트
"""

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.member_service import MemberService
from app.services.locker_service import LockerService


def test_member_permissions():
    """회원 권한 테스트"""
    print("🧪 락커 권한 시스템 테스트")
    print("=" * 50)
    
    member_service = MemberService('instance/gym_system.db')
    locker_service = LockerService('instance/gym_system.db')
    
    # 테스트 회원들
    test_members = [
        '20156111',  # 김현 (대학교수 - 남자) -> 교직원 권한
        '20211377',  # 김진서 (대학직원 - 여자) -> 교직원 권한  
        '20240838',  # 손준표 (학부 - 남자) -> 일반 남자 권한
        '20211131',  # 엘레나 (학부 - 여자) -> 일반 여자 권한
    ]
    
    for member_id in test_members:
        print(f"\n👤 회원 테스트: {member_id}")
        
        # 회원 정보 조회
        member = member_service.get_member(member_id)
        if not member:
            print(f"   ❌ 회원을 찾을 수 없습니다.")
            continue
        
        print(f"   📋 이름: {member.name}")
        print(f"   👔 구분: {member.customer_type} ({member.member_category})")
        print(f"   🚻 성별: {member.gender}")
        print(f"   🔑 접근 가능 구역: {member.allowed_zones}")
        
        # 각 구역별 접근 권한 테스트
        zones = ['MALE', 'FEMALE', 'STAFF']
        for zone in zones:
            can_access = member.can_access_zone(zone)
            status = "✅ 가능" if can_access else "❌ 불가"
            print(f"   🏢 {zone} 구역: {status}")
        
        # 사용 가능한 락커 조회 테스트
        for zone in member.allowed_zones:
            available_lockers = locker_service.get_available_lockers(zone, member_id)
            print(f"   🔓 {zone} 구역 사용 가능 락커: {len(available_lockers)}개")
    
    print("\n" + "=" * 50)
    print("✅ 테스트 완료!")


def test_zone_access_scenarios():
    """구역 접근 시나리오 테스트"""
    print("\n🎯 구역 접근 시나리오 테스트")
    print("=" * 50)
    
    member_service = MemberService('instance/gym_system.db')
    
    scenarios = [
        {
            'member_id': '20156111',  # 김현 (대학교수 - 남자)
            'expected_zones': ['MALE', 'STAFF'],
            'description': '남자 교직원 -> 남자구역 + 교직원구역'
        },
        {
            'member_id': '20211377',  # 김진서 (대학직원 - 여자)  
            'expected_zones': ['FEMALE', 'STAFF'],
            'description': '여자 교직원 -> 여자구역 + 교직원구역'
        },
        {
            'member_id': '20240838',  # 손준표 (학부 - 남자)
            'expected_zones': ['MALE'],
            'description': '남자 일반회원 -> 남자구역만'
        },
        {
            'member_id': '20211131',  # 엘레나 (학부 - 여자)
            'expected_zones': ['FEMALE'],
            'description': '여자 일반회원 -> 여자구역만'
        }
    ]
    
    for scenario in scenarios:
        member = member_service.get_member(scenario['member_id'])
        if not member:
            print(f"❌ 회원 {scenario['member_id']}를 찾을 수 없습니다.")
            continue
        
        print(f"\n📝 시나리오: {scenario['description']}")
        print(f"   👤 회원: {member.name} ({scenario['member_id']})")
        print(f"   🎯 예상 구역: {scenario['expected_zones']}")
        print(f"   🔍 실제 구역: {member.allowed_zones}")
        
        if set(member.allowed_zones) == set(scenario['expected_zones']):
            print(f"   ✅ 테스트 통과!")
        else:
            print(f"   ❌ 테스트 실패!")
    
    print("\n" + "=" * 50)
    print("✅ 시나리오 테스트 완료!")


def main():
    """메인 함수"""
    try:
        test_member_permissions()
        test_zone_access_scenarios()
    except Exception as e:
        print(f"❌ 테스트 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
