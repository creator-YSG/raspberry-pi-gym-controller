#!/usr/bin/env python3
"""
완전한 대여/반납 플로우 테스트 (센서 연동 포함)
"""

import sys
import os
import asyncio
import time
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.locker_service import LockerService
from app.services.sensor_event_handler import SensorEventHandler


async def test_complete_rental_flow():
    """완전한 대여 플로우 테스트 (센서 검증 포함)"""
    
    print("🚀 완전한 대여/반납 플로우 테스트 시작...")
    
    # 서비스 초기화
    locker_service = LockerService('locker.db')
    sensor_handler = SensorEventHandler('locker.db')
    
    try:
        # 테스트 데이터
        member_id = '54321'  # 김철수 (다른 회원으로 변경)
        locker_id = 'A02'    # A02 락카 (다른 락카로 변경)
        sensor_num = 2       # 센서 2번 (A02와 매핑)
        
        print(f"\n📋 테스트 설정:")
        print(f"  회원: {member_id}")
        print(f"  락카: {locker_id}")
        print(f"  센서: {sensor_num}번")
        
        # 1. 초기 상태 확인
        print(f"\n📊 1. 초기 상태 확인")
        
        locker = locker_service.get_locker_by_id(locker_id)
        if locker:
            print(f"  락카 상태: {locker.status}")
            print(f"  대여자: {locker.rented_by or '없음'}")
        
        # 2. 대여 시작
        print(f"\n🔑 2. 대여 시작")
        
        rental_result = await locker_service.rent_locker(locker_id, member_id)
        
        if rental_result['success']:
            print(f"  ✅ 대여 트랜잭션 시작 성공!")
            print(f"     트랜잭션 ID: {rental_result['transaction_id']}")
            print(f"     단계: {rental_result['step']}")
            print(f"     메시지: {rental_result['message']}")
            
            tx_id = rental_result['transaction_id']
        else:
            print(f"  ❌ 대여 실패: {rental_result['error']}")
            return
        
        # 3. 센서 검증 대기 상태 확인
        print(f"\n⏳ 3. 센서 검증 대기 중...")
        
        # 트랜잭션 상태 확인
        active_txs = await sensor_handler.tx_manager.get_active_transactions()
        current_tx = None
        for tx in active_txs:
            if tx['transaction_id'] == tx_id:
                current_tx = tx
                break
        
        if current_tx:
            print(f"  📍 트랜잭션 상태: {current_tx['step']}")
            print(f"  📍 타입: {current_tx['transaction_type']}")
            print(f"  📍 락카: {current_tx.get('locker_number', 'Unknown')}")
        
        # 4. 센서 이벤트 시뮬레이션 (키 제거)
        print(f"\n🔍 4. 센서 이벤트 시뮬레이션 (키 제거)")
        
        print(f"  센서 {sensor_num}번 상태 변경: HIGH → LOW (키 제거)")
        
        sensor_result = await sensor_handler.handle_sensor_event(sensor_num, 'LOW')
        
        if sensor_result['success']:
            print(f"  ✅ 센서 이벤트 처리 성공!")
            print(f"     완료 여부: {sensor_result.get('completed', False)}")
            print(f"     메시지: {sensor_result['message']}")
            
            if sensor_result.get('completed'):
                print(f"  🎉 대여 완료!")
                print(f"     이벤트 타입: {sensor_result.get('event_type')}")
        else:
            print(f"  ❌ 센서 이벤트 처리 실패: {sensor_result['error']}")
        
        # 5. 대여 완료 후 상태 확인
        print(f"\n📊 5. 대여 완료 후 상태 확인")
        
        updated_locker = locker_service.get_locker_by_id(locker_id)
        if updated_locker:
            print(f"  락카 상태: {updated_locker.status}")
            print(f"  대여자: {updated_locker.rented_by or '없음'}")
            print(f"  대여 시간: {updated_locker.rented_at}")
        
        # 활성 트랜잭션 확인
        active_txs_after = await sensor_handler.tx_manager.get_active_transactions()
        print(f"  활성 트랜잭션 수: {len(active_txs_after)}개")
        
        # 6. 잠시 대기 (대여 상태 유지)
        print(f"\n⏸️  6. 대여 상태 유지 (3초 대기)")
        await asyncio.sleep(3)
        
        # 7. 반납 시뮬레이션 (향후 구현)
        print(f"\n🔄 7. 반납 플로우 (향후 구현 예정)")
        print(f"  - 락카키 바코드 스캔")
        print(f"  - 반납 트랜잭션 시작")
        print(f"  - 센서 이벤트 (키 삽입): LOW → HIGH")
        print(f"  - 반납 완료")
        
        # 8. 최종 통계
        print(f"\n📈 8. 최종 통계")
        
        available_count = len(locker_service.get_available_lockers('A'))
        occupied_count = len(locker_service.get_occupied_lockers('A'))
        
        print(f"  A구역 사용 가능: {available_count}개")
        print(f"  A구역 사용중: {occupied_count}개")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        locker_service.close()
        sensor_handler.close()
        print("\n✅ 완전한 플로우 테스트 완료!")


async def test_sensor_mapping():
    """센서-락카 매핑 테스트"""
    
    print("\n🗺️  센서-락카 매핑 테스트")
    
    sensor_handler = SensorEventHandler('locker.db')
    
    try:
        mapping = sensor_handler.get_sensor_locker_mapping()
        
        print(f"전체 센서 수: {len(mapping)}개")
        
        # A구역 매핑 (처음 10개만 표시)
        print(f"\nA구역 매핑 (처음 10개):")
        for sensor_num in range(1, 11):
            locker_id = mapping.get(sensor_num, 'Unknown')
            print(f"  센서 {sensor_num:2d}번 → {locker_id}")
        
        # B구역 매핑 (처음 5개만 표시)
        print(f"\nB구역 매핑 (처음 5개):")
        for sensor_num in range(25, 30):
            locker_id = mapping.get(sensor_num, 'Unknown')
            print(f"  센서 {sensor_num:2d}번 → {locker_id}")
        
    finally:
        sensor_handler.close()


if __name__ == '__main__':
    print("🧪 센서 연동 통합 테스트")
    print("=" * 50)
    
    # 센서 매핑 테스트
    asyncio.run(test_sensor_mapping())
    
    print("\n" + "=" * 50)
    
    # 완전한 플로우 테스트
    asyncio.run(test_complete_rental_flow())
