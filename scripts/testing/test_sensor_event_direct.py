#!/usr/bin/env python3
"""
센서 이벤트 직접 테스트
"""

import sys
import os
import asyncio
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.locker_service import LockerService
from app.services.sensor_event_handler import SensorEventHandler


async def test_sensor_event_direct():
    """센서 이벤트 직접 테스트"""
    
    print("🔍 센서 이벤트 직접 테스트 시작...")
    
    # 서비스 초기화
    locker_service = LockerService('instance/gym_system.db')
    sensor_handler = SensorEventHandler('instance/gym_system.db')
    
    try:
        member_id = 'TEST001'  # 테스트회원1 (VIP)
        locker_id = 'A03'    # A03 락카
        sensor_num = 3       # 센서 3번
        
        print(f"\n1️⃣ 대여 트랜잭션 시작")
        rental_result = await locker_service.rent_locker(locker_id, member_id)
        
        if not rental_result['success']:
            print(f"❌ 대여 실패: {rental_result['error']}")
            return
        
        tx_id = rental_result['transaction_id']
        print(f"✅ 트랜잭션 생성: {tx_id}")
        
        print(f"\n2️⃣ 활성 트랜잭션 확인")
        active_txs = await sensor_handler.tx_manager.get_active_transactions()
        print(f"활성 트랜잭션 수: {len(active_txs)}")
        
        for tx in active_txs:
            print(f"  - ID: {tx['transaction_id']}")
            print(f"    단계: {tx['step']}")
            print(f"    타입: {tx['transaction_type']}")
            print(f"    락카: {tx.get('locker_number', 'None')}")
            print(f"    회원: {tx['member_id']}")
        
        print(f"\n3️⃣ 센서 이벤트 처리 (LOW)")
        result = await sensor_handler.handle_sensor_event(sensor_num, 'LOW')
        
        print(f"센서 이벤트 결과:")
        print(f"  성공: {result['success']}")
        print(f"  완료: {result.get('completed', False)}")
        print(f"  메시지: {result['message']}")
        
        if result.get('completed'):
            print(f"  🎉 이벤트 타입: {result.get('event_type')}")
        
        print(f"\n4️⃣ 트랜잭션 상태 재확인")
        active_txs_after = await sensor_handler.tx_manager.get_active_transactions()
        print(f"활성 트랜잭션 수: {len(active_txs_after)}")
        
        print(f"\n5️⃣ 락카 상태 확인")
        locker = locker_service.get_locker_by_id(locker_id)
        if locker:
            print(f"  락카 상태: {locker.status}")
            print(f"  대여자: {locker.rented_by}")
        
        print(f"\n6️⃣ 대여 기록 확인")
        cursor = sensor_handler.db.execute_query("""
            SELECT * FROM rentals WHERE transaction_id = ?
        """, (tx_id,))
        
        if cursor:
            rental_row = cursor.fetchone()
            if rental_row:
                print(f"  대여 기록 상태: {rental_row['status']}")
                print(f"  센서 검증: {rental_row['rental_verified']}")
                print(f"  센서 시간: {rental_row['rental_sensor_time']}")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        locker_service.close()
        sensor_handler.close()
        print("\n✅ 센서 이벤트 직접 테스트 완료!")


if __name__ == '__main__':
    asyncio.run(test_sensor_event_direct())
