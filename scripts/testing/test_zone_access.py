#!/usr/bin/env python3
"""
구역 접근 권한 테스트
각 회원이 올바른 구역에만 접근할 수 있는지 테스트
"""

import sys
import os
import asyncio

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.member_service import MemberService
from app.services.locker_service import LockerService


async def test_zone_access():
    """구역 접근 권한 테스트"""
    print("🔐 구역 접근 권한 테스트")
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
            'test_lockers': {
                'M01': True,   # 남자 구역 - 접근 가능
                'F01': False,  # 여자 구역 - 접근 불가
                'S01': True,   # 교직원 구역 - 접근 가능
            }
        },
        {
            'member_id': '20211377',  # 김진서 (여자 교직원)
            'name': '김진서',
            'type': '여자 교직원',
            'expected_zones': ['FEMALE', 'STAFF'],
            'test_lockers': {
                'M01': False,  # 남자 구역 - 접근 불가
                'F01': True,   # 여자 구역 - 접근 가능
                'S01': True,   # 교직원 구역 - 접근 가능
            }
        },
        {
            'member_id': '20240838',  # 손준표 (남자 일반회원)
            'name': '손준표',
            'type': '남자 일반회원',
            'expected_zones': ['MALE'],
            'test_lockers': {
                'M01': True,   # 남자 구역 - 접근 가능
                'F01': False,  # 여자 구역 - 접근 불가
                'S01': False,  # 교직원 구역 - 접근 불가
            }
        },
        {
            'member_id': '20211131',  # 엘레나 (여자 일반회원)
            'name': '엘레나',
            'type': '여자 일반회원',
            'expected_zones': ['FEMALE'],
            'test_lockers': {
                'M01': False,  # 남자 구역 - 접근 불가
                'F01': True,   # 여자 구역 - 접근 가능
                'S01': False,  # 교직원 구역 - 접근 불가
            }
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\n👤 {test_case['name']} ({test_case['type']}) 테스트")
        print("-" * 50)
        
        # 회원 정보 조회
        member = member_service.get_member(test_case['member_id'])
        if not member:
            print(f"❌ 회원을 찾을 수 없습니다: {test_case['member_id']}")
            all_passed = False
            continue
        
        # 기본 정보 확인
        print(f"📋 회원 정보:")
        print(f"   - 이름: {member.name}")
        print(f"   - 구분: {member.customer_type} ({member.member_category})")
        print(f"   - 성별: {member.gender}")
        print(f"   - 만료일: {member.membership_expires}")
        print(f"   - 유효성: {'✅ 유효' if member.is_valid else '❌ 만료'}")
        
        # 접근 가능 구역 확인
        actual_zones = member.allowed_zones
        expected_zones = test_case['expected_zones']
        
        print(f"\n🔑 구역 접근 권한:")
        print(f"   - 예상 구역: {expected_zones}")
        print(f"   - 실제 구역: {actual_zones}")
        
        if set(actual_zones) == set(expected_zones):
            print(f"   ✅ 구역 권한 일치")
        else:
            print(f"   ❌ 구역 권한 불일치")
            all_passed = False
        
        # 각 락커에 대한 접근 테스트
        print(f"\n🔐 락커 접근 테스트:")
        for locker_id, should_access in test_case['test_lockers'].items():
            try:
                # 락커 대여 시도 (시뮬레이션)
                result = await locker_service.rent_locker(locker_id, member.id)
                
                if should_access:
                    # 접근 가능해야 하는 경우
                    if result['success'] or result.get('step') == 'sensor_wait':
                        print(f"   ✅ {locker_id}: 접근 가능 (예상대로)")
                    else:
                        print(f"   ❌ {locker_id}: 접근 불가 (예상과 다름) - {result.get('error', 'Unknown error')}")
                        all_passed = False
                else:
                    # 접근 불가능해야 하는 경우
                    if not result['success'] and result.get('step') == 'zone_access_denied':
                        print(f"   ✅ {locker_id}: 접근 차단 (예상대로)")
                    elif not result['success']:
                        print(f"   ✅ {locker_id}: 접근 차단 (예상대로) - {result.get('error', 'Unknown error')}")
                    else:
                        print(f"   ❌ {locker_id}: 접근 허용 (예상과 다름)")
                        all_passed = False
                
            except Exception as e:
                print(f"   💥 {locker_id}: 테스트 오류 - {e}")
                all_passed = False
        
        # 트랜잭션 정리
        try:
            # 활성 트랜잭션이 있으면 완료 처리
            import sqlite3
            conn = sqlite3.connect('instance/gym_system.db')
            conn.execute("UPDATE active_transactions SET status = 'completed' WHERE member_id = ? AND status = 'active'", (member.id,))
            conn.commit()
            conn.close()
        except:
            pass
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 모든 구역 접근 권한 테스트 통과!")
    else:
        print("💥 일부 테스트 실패!")
    print("=" * 80)


async def test_invalid_member():
    """유효하지 않은 회원 테스트"""
    print("\n🚫 유효하지 않은 회원 테스트")
    print("-" * 50)
    
    member_service = MemberService('instance/gym_system.db')
    locker_service = LockerService('instance/gym_system.db')
    
    # 존재하지 않는 회원
    print("👻 존재하지 않는 회원 테스트:")
    result = await locker_service.rent_locker('M01', '99999999')
    if not result['success'] and 'member_validation' in result.get('step', ''):
        print("   ✅ 존재하지 않는 회원 차단됨")
    else:
        print("   ❌ 존재하지 않는 회원이 통과됨")
    
    print("-" * 50)


async def main():
    """메인 함수"""
    print("🏋️ 헬스장 락커 시스템 구역 접근 권한 테스트")
    
    await test_zone_access()
    await test_invalid_member()
    
    print("\n🎯 모든 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
