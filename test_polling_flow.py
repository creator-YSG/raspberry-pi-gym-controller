#!/usr/bin/env python3
"""
폴링 방식 전체 플로우 테스트
바코드 스캔 → 회원 인증 → 센서 감지 → 대여/반납 완료
"""

import time
import queue
from app import create_app

# Flask 앱 생성
app = create_app()

def simulate_barcode_scan(barcode):
    """바코드 스캔 시뮬레이션"""
    print(f"\n{'='*80}")
    print(f"📱 바코드 스캔: {barcode}")
    print(f"{'='*80}")
    
    # 바코드 큐에 추가
    try:
        app.barcode_queue.put_nowait({
            'barcode': barcode,
            'device_id': 'test_simulator'
        })
        print(f"✅ 바코드 큐에 저장됨")
    except queue.Full:
        # 큐가 꽉 찼으면 비우고 다시 시도
        try:
            app.barcode_queue.get_nowait()
            app.barcode_queue.put_nowait({
                'barcode': barcode,
                'device_id': 'test_simulator'
            })
            print(f"✅ 바코드 큐에 저장됨 (기존 데이터 덮어씀)")
        except:
            print(f"❌ 바코드 큐 저장 실패")

def simulate_sensor_event(sensor_num, state):
    """센서 이벤트 시뮬레이션"""
    print(f"\n{'='*80}")
    print(f"🔌 센서 이벤트: 센서 {sensor_num} → {state}")
    print(f"{'='*80}")
    
    # 센서 큐에 추가
    try:
        sensor_data = {
            'sensor_num': sensor_num,
            'chip_idx': 0,
            'pin': sensor_num - 1,
            'state': state,
            'active': (state == 'LOW'),
            'timestamp': time.time()
        }
        app.sensor_queue.put_nowait(sensor_data)
        print(f"✅ 센서 큐에 저장됨")
    except queue.Full:
        print(f"⚠️ 센서 큐가 가득 참 (크기: {app.sensor_queue.qsize()})")

def check_queues():
    """큐 상태 확인"""
    print(f"\n📊 큐 상태:")
    print(f"  - 바코드 큐: {app.barcode_queue.qsize()}개")
    print(f"  - 센서 큐: {app.sensor_queue.qsize()}개")

def test_rental_flow():
    """대여 플로우 테스트"""
    print(f"\n{'#'*80}")
    print(f"# 테스트 1: 대여 플로우 (등록된 회원)")
    print(f"{'#'*80}")
    
    # 1. 바코드 스캔 (등록된 회원)
    simulate_barcode_scan("20240756")  # 홍길동
    time.sleep(0.5)
    check_queues()
    
    # 2. 센서 이벤트 (락커키 제거)
    time.sleep(1)
    simulate_sensor_event(6, "LOW")  # M06 락커키 제거
    time.sleep(0.5)
    check_queues()
    
    print(f"\n✅ 대여 플로우 시뮬레이션 완료")
    print(f"💡 실제 화면 전환:")
    print(f"   Home → Member Check → Rental Complete")

def test_unregistered_member():
    """등록되지 않은 회원 테스트"""
    print(f"\n{'#'*80}")
    print(f"# 테스트 2: 등록되지 않은 회원")
    print(f"{'#'*80}")
    
    # 바코드 스캔 (미등록 회원)
    simulate_barcode_scan("99999999")
    time.sleep(0.5)
    check_queues()
    
    print(f"\n✅ 미등록 회원 시뮬레이션 완료")
    print(f"💡 실제 화면 전환:")
    print(f"   Home → Error (Member Not Found)")

def test_return_flow():
    """반납 플로우 테스트"""
    print(f"\n{'#'*80}")
    print(f"# 테스트 3: 반납 플로우")
    print(f"{'#'*80}")
    
    # 1. 바코드 스캔 (대여 중인 회원)
    simulate_barcode_scan("20240756")
    time.sleep(0.5)
    check_queues()
    
    # 2. 센서 이벤트 (락커키 삽입)
    time.sleep(1)
    simulate_sensor_event(6, "HIGH")  # M06 락커키 삽입
    time.sleep(0.5)
    check_queues()
    
    print(f"\n✅ 반납 플로우 시뮬레이션 완료")
    print(f"💡 실제 화면 전환:")
    print(f"   Home → Member Check → Return Complete")

def test_multiple_sensor_events():
    """여러 센서 이벤트 동시 처리"""
    print(f"\n{'#'*80}")
    print(f"# 테스트 4: 여러 센서 이벤트 동시 발생")
    print(f"{'#'*80}")
    
    # 바코드 스캔
    simulate_barcode_scan("20240756")
    time.sleep(0.5)
    
    # 여러 센서 이벤트 동시 발생
    for i in range(1, 6):
        simulate_sensor_event(i, "LOW")
        time.sleep(0.1)
    
    check_queues()
    
    print(f"\n✅ 다중 센서 이벤트 시뮬레이션 완료")
    print(f"💡 큐에 {app.sensor_queue.qsize()}개의 센서 이벤트 대기 중")

def main():
    """메인 테스트 실행"""
    with app.app_context():
        print(f"\n{'*'*80}")
        print(f"* 폴링 방식 전체 플로우 테스트 시작")
        print(f"{'*'*80}")
        
        # 큐 초기화 확인
        print(f"\n📦 큐 초기화:")
        if not hasattr(app, 'barcode_queue'):
            print(f"  ⚠️ barcode_queue가 초기화되지 않음 - 수동 생성")
            app.barcode_queue = queue.Queue(maxsize=1)
            app.sensor_queue = queue.Queue(maxsize=10)
        print(f"  - 바코드 큐: {app.barcode_queue}")
        print(f"  - 센서 큐: {app.sensor_queue}")
        
        # 테스트 실행
        test_unregistered_member()
        time.sleep(2)
        
        test_rental_flow()
        time.sleep(2)
        
        test_multiple_sensor_events()
        time.sleep(2)
        
        # 최종 큐 상태
        print(f"\n{'*'*80}")
        print(f"* 테스트 완료")
        print(f"{'*'*80}")
        check_queues()
        
        print(f"\n💡 다음 단계:")
        print(f"  1. 라즈베리파이에 배포")
        print(f"  2. 실제 바코드 스캔 테스트")
        print(f"  3. 실제 센서 이벤트 테스트")
        print(f"  4. 전체 대여/반납 플로우 확인")

if __name__ == '__main__':
    main()

