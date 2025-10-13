#!/usr/bin/env python3
"""
LockerService 테스트 스크립트
"""

import sys
import os
import asyncio
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.locker_service import LockerService


async def test_locker_service():
    """LockerService 테스트"""
    
    print("🚀 LockerService 테스트 시작...")
    
    # LockerService 초기화
    locker_service = LockerService('instance/gym_system.db')
    
    try:
        # 1. 사용 가능한 락카 조회
        print("\n📋 1. 사용 가능한 락카 조회")
        available_lockers = locker_service.get_available_lockers('A')
        print(f"A구역 사용 가능한 락카: {len(available_lockers)}개")
        
        if available_lockers:
            for locker in available_lockers[:5]:  # 처음 5개만 표시
                print(f"  ✅ {locker.id}: {locker.status} ({locker.size})")
        
        # 2. 사용중인 락카 조회
        print("\n📋 2. 사용중인 락카 조회")
        occupied_lockers = locker_service.get_occupied_lockers('A')
        print(f"A구역 사용중인 락카: {len(occupied_lockers)}개")
        
        if occupied_lockers:
            for locker in occupied_lockers:
                print(f"  🔒 {locker.id}: {locker.status} (대여자: {locker.rented_by})")
        
        # 3. 특정 락카 조회
        print("\n📋 3. 특정 락카 조회")
        test_locker_id = 'A01'
        locker = locker_service.get_locker_by_id(test_locker_id)
        if locker:
            print(f"  📍 {locker.id}: {locker.status} ({locker.zone}구역, {locker.size})")
        else:
            print(f"  ❌ {test_locker_id} 락카를 찾을 수 없습니다.")
        
        # 4. 락카 대여 테스트
        print("\n🔑 4. 락카 대여 테스트")
        
        # 유효한 회원으로 대여 시도
        member_id = '12345'  # 이전에 추가한 테스트 회원
        locker_id = 'A01'
        
        print(f"대여 시도: {member_id} -> {locker_id}")
        
        result = await locker_service.rent_locker(locker_id, member_id)
        
        if result['success']:
            print(f"  ✅ 대여 성공!")
            print(f"     트랜잭션 ID: {result['transaction_id']}")
            print(f"     회원: {result['member_name']}")
            print(f"     락카: {result['locker_id']}")
            print(f"     단계: {result['step']}")
            print(f"     메시지: {result['message']}")
            print(f"     타임아웃: {result['timeout_seconds']}초")
        else:
            print(f"  ❌ 대여 실패: {result['error']}")
            print(f"     단계: {result.get('step', 'unknown')}")
        
        # 5. 중복 대여 시도 (실패해야 함)
        print("\n🔑 5. 중복 대여 시도 (실패 테스트)")
        
        result2 = await locker_service.rent_locker('A02', member_id)
        
        if result2['success']:
            print(f"  ⚠️  예상치 못한 성공: {result2}")
        else:
            print(f"  ✅ 예상된 실패: {result2['error']}")
        
        # 6. 존재하지 않는 회원으로 대여 시도
        print("\n🔑 6. 존재하지 않는 회원 대여 시도")
        
        result3 = await locker_service.rent_locker('A03', 'NOTFOUND')
        
        if result3['success']:
            print(f"  ⚠️  예상치 못한 성공: {result3}")
        else:
            print(f"  ✅ 예상된 실패: {result3['error']}")
        
        # 7. 만료된 회원으로 대여 시도
        print("\n🔑 7. 만료된 회원 대여 시도")
        
        result4 = await locker_service.rent_locker('A04', 'expired123')
        
        if result4['success']:
            print(f"  ⚠️  예상치 못한 성공: {result4}")
        else:
            print(f"  ✅ 예상된 실패: {result4['error']}")
        
        # 8. 대여 후 락카 상태 확인
        print("\n📋 8. 대여 후 락카 상태 확인")
        
        updated_locker = locker_service.get_locker_by_id(locker_id)
        if updated_locker:
            print(f"  📍 {updated_locker.id}: {updated_locker.status}")
            if updated_locker.rented_by:
                print(f"     대여자: {updated_locker.rented_by}")
        
        # 9. 사용 가능한 락카 수 재확인
        print("\n📋 9. 대여 후 사용 가능한 락카 수")
        available_after = locker_service.get_available_lockers('A')
        occupied_after = locker_service.get_occupied_lockers('A')
        
        print(f"A구역 사용 가능: {len(available_after)}개")
        print(f"A구역 사용중: {len(occupied_after)}개")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        locker_service.close()
        print("\n✅ LockerService 테스트 완료!")


if __name__ == '__main__':
    asyncio.run(test_locker_service())
