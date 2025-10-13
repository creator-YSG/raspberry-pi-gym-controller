#!/usr/bin/env python3
"""
API 기능 직접 테스트 (서버 없이)
"""

import sys
import os
import asyncio
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.locker_service import LockerService
from app.services.member_service import MemberService
from app.services.sensor_event_handler import SensorEventHandler
from database import DatabaseManager, TransactionManager


async def test_api_functionality():
    """API 기능을 직접 테스트"""
    
    print("🧪 API 기능 직접 테스트 시작...")
    
    # 서비스 초기화
    member_service = MemberService('instance/gym_system.db')
    locker_service = LockerService('instance/gym_system.db')
    sensor_handler = SensorEventHandler('instance/gym_system.db')
    
    db = DatabaseManager('instance/gym_system.db')
    db.connect()
    tx_manager = TransactionManager(db)
    
    try:
        # 1. 회원 검증 테스트
        print(f"\n👤 1. 회원 검증 테스트")
        
        test_members = ['TEST001', '54321', 'expired123', 'NOTFOUND']
        
        for member_id in test_members:
            result = member_service.validate_member(member_id)
            status = "✅" if result.get('valid') else "❌"
            message = result.get('message', result.get('error', ''))
            print(f"  {status} {member_id}: {message}")
        
        # 2. 활성 트랜잭션 조회
        print(f"\n🔄 2. 활성 트랜잭션 조회")
        
        transactions = await tx_manager.get_active_transactions()
        print(f"  ✅ 활성 트랜잭션: {len(transactions)}개")
        
        for tx in transactions:
            print(f"    - ID: {tx['transaction_id'][:8]}...")
            print(f"      단계: {tx['step']}, 타입: {tx['transaction_type']}")
            print(f"      회원: {tx['member_id']}, 락카: {tx.get('locker_number', 'None')}")
        
        # 3. 락카 대여 테스트
        print(f"\n🔑 3. 락카 대여 테스트")
        
        member_id = 'TEST002'
        locker_id = 'A06'
        
        result = await locker_service.rent_locker(locker_id, member_id)
        
        if result['success']:
            print(f"  ✅ 대여 성공!")
            print(f"    트랜잭션 ID: {result['transaction_id']}")
            print(f"    회원: {result['member_name']}")
            print(f"    락카: {result['locker_id']}")
            print(f"    단계: {result['step']}")
            print(f"    메시지: {result['message']}")
            
            tx_id = result['transaction_id']
            
            # 4. 트랜잭션 상태 조회
            print(f"\n📋 4. 트랜잭션 상태 조회")
            
            status = await tx_manager.get_transaction_status(tx_id)
            if status:
                print(f"  ✅ 트랜잭션 상태: {status['step']}")
                print(f"    타입: {status['transaction_type']}")
                print(f"    회원: {status['member_id']}")
                print(f"    락카: {status.get('locker_number', 'None')}")
            else:
                print(f"  ❌ 트랜잭션 상태 조회 실패")
            
            # 5. 센서 이벤트 시뮬레이션
            print(f"\n🔍 5. 센서 이벤트 시뮬레이션")
            
            sensor_num = 6  # A06 → 센서 6번
            state = 'LOW'   # 키 제거
            
            sensor_result = await sensor_handler.handle_sensor_event(sensor_num, state)
            
            if sensor_result['success']:
                print(f"  ✅ 센서 이벤트 처리 성공!")
                print(f"    완료 여부: {sensor_result.get('completed', False)}")
                print(f"    메시지: {sensor_result['message']}")
                
                if sensor_result.get('completed'):
                    print(f"  🎉 이벤트 타입: {sensor_result.get('event_type')}")
            else:
                print(f"  ❌ 센서 이벤트 처리 실패: {sensor_result['error']}")
            
            # 6. 최종 트랜잭션 상태 확인
            print(f"\n📊 6. 최종 트랜잭션 상태 확인")
            
            final_status = await tx_manager.get_transaction_status(tx_id)
            if final_status:
                print(f"  📋 트랜잭션 상태: {final_status['step']}")
                print(f"    상태: {final_status['status']}")
            else:
                print(f"  ✅ 트랜잭션이 완료되어 조회되지 않음 (정상)")
            
        else:
            print(f"  ❌ 대여 실패: {result['error']}")
        
        # 7. 최종 활성 트랜잭션 확인
        print(f"\n🔄 7. 최종 활성 트랜잭션 확인")
        
        final_transactions = await tx_manager.get_active_transactions()
        print(f"  ✅ 활성 트랜잭션: {len(final_transactions)}개")
        
        if final_transactions:
            for tx in final_transactions:
                print(f"    - ID: {tx['transaction_id'][:8]}...")
                print(f"      단계: {tx['step']}, 상태: {tx['status']}")
        else:
            print(f"  🎉 모든 트랜잭션이 완료되었습니다!")
        
        # 8. 락카 상태 확인
        print(f"\n🏠 8. 락카 상태 확인")
        
        available_lockers = locker_service.get_available_lockers('A')
        occupied_lockers = locker_service.get_occupied_lockers('A')
        
        print(f"  A구역 사용 가능: {len(available_lockers)}개")
        print(f"  A구역 사용중: {len(occupied_lockers)}개")
        
        if occupied_lockers:
            for locker in occupied_lockers[:3]:  # 처음 3개만 표시
                print(f"    🔒 {locker.id}: {locker.rented_by}")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        member_service.close()
        locker_service.close()
        sensor_handler.close()
        db.close()
        print(f"\n✅ API 기능 직접 테스트 완료!")


if __name__ == '__main__':
    asyncio.run(test_api_functionality())
