#!/usr/bin/env python3
"""
API 엔드포인트 테스트 스크립트
"""

import sys
import os
import requests
import json
import time
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_api_endpoints():
    """API 엔드포인트 테스트"""
    
    print("🌐 API 엔드포인트 테스트 시작...")
    
    # Flask 앱이 실행 중인지 확인
    base_url = "http://localhost:5001"
    
    try:
        # 1. 시스템 상태 확인
        print(f"\n📊 1. 시스템 상태 확인")
        
        response = requests.get(f"{base_url}/api/system/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ 시스템 상태: {data.get('success', False)}")
        else:
            print(f"  ❌ 시스템 상태 조회 실패: {response.status_code}")
        
        # 2. 회원 검증 테스트
        print(f"\n👤 2. 회원 검증 테스트")
        
        test_members = ['TEST001', '54321', 'expired123', 'NOTFOUND']
        
        for member_id in test_members:
            try:
                response = requests.get(f"{base_url}/api/members/{member_id}/validate", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    status = "✅" if data.get('valid') else "❌"
                    message = data.get('message', data.get('error', ''))
                    print(f"  {status} {member_id}: {message}")
                else:
                    print(f"  ❌ {member_id}: HTTP {response.status_code}")
            except Exception as e:
                print(f"  ❌ {member_id}: 연결 오류 - {e}")
        
        # 3. 활성 트랜잭션 조회
        print(f"\n🔄 3. 활성 트랜잭션 조회")
        
        try:
            response = requests.get(f"{base_url}/api/transactions/active", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    transactions = data.get('transactions', [])
                    print(f"  ✅ 활성 트랜잭션: {len(transactions)}개")
                    
                    for tx in transactions:
                        print(f"    - ID: {tx['transaction_id'][:8]}...")
                        print(f"      단계: {tx['step']}, 타입: {tx['transaction_type']}")
                        print(f"      회원: {tx['member_id']}, 락카: {tx.get('locker_number', 'None')}")
                else:
                    print(f"  ❌ 트랜잭션 조회 실패: {data.get('error')}")
            else:
                print(f"  ❌ 트랜잭션 조회 HTTP 오류: {response.status_code}")
        except Exception as e:
            print(f"  ❌ 트랜잭션 조회 연결 오류: {e}")
        
        # 4. 락카 대여 테스트
        print(f"\n🔑 4. 락카 대여 테스트")
        
        rental_data = {
            'member_id': 'TEST002'
        }
        
        try:
            response = requests.post(
                f"{base_url}/api/lockers/A05/rent", 
                json=rental_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"  ✅ 대여 성공!")
                    print(f"    트랜잭션 ID: {data['transaction_id']}")
                    print(f"    회원: {data['member_name']}")
                    print(f"    락카: {data['locker_id']}")
                    print(f"    단계: {data['step']}")
                    print(f"    메시지: {data['message']}")
                    
                    # 트랜잭션 ID 저장 (센서 시뮬레이션용)
                    tx_id = data['transaction_id']
                    
                    # 5. 트랜잭션 상태 조회
                    print(f"\n📋 5. 트랜잭션 상태 조회")
                    
                    response = requests.get(f"{base_url}/api/transactions/{tx_id}/status", timeout=5)
                    if response.status_code == 200:
                        tx_data = response.json()
                        if tx_data.get('success'):
                            tx_info = tx_data['transaction']
                            print(f"  ✅ 트랜잭션 상태: {tx_info['step']}")
                            print(f"    타입: {tx_info['transaction_type']}")
                            print(f"    회원: {tx_info['member_id']}")
                            print(f"    락카: {tx_info.get('locker_number', 'None')}")
                        else:
                            print(f"  ❌ 트랜잭션 상태 조회 실패: {tx_data.get('error')}")
                    
                    # 6. 센서 이벤트 시뮬레이션
                    print(f"\n🔍 6. 센서 이벤트 시뮬레이션")
                    
                    sensor_data = {
                        'sensor_num': 5,  # A05 → 센서 5번
                        'state': 'LOW'    # 키 제거
                    }
                    
                    response = requests.post(
                        f"{base_url}/api/hardware/simulate_sensor",
                        json=sensor_data,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        sensor_result = response.json()
                        if sensor_result.get('success'):
                            print(f"  ✅ 센서 이벤트 시뮬레이션 성공!")
                            print(f"    센서: {sensor_result['sensor_num']}번")
                            print(f"    락카: {sensor_result['locker_id']}")
                            print(f"    상태: {sensor_result['state']}")
                        else:
                            print(f"  ❌ 센서 시뮬레이션 실패: {sensor_result.get('error')}")
                    
                    # 잠시 대기 후 트랜잭션 상태 재확인
                    print(f"\n⏳ 7. 센서 처리 후 상태 확인 (2초 대기)")
                    time.sleep(2)
                    
                    response = requests.get(f"{base_url}/api/transactions/{tx_id}/status", timeout=5)
                    if response.status_code == 200:
                        tx_data = response.json()
                        if tx_data.get('success'):
                            tx_info = tx_data['transaction']
                            print(f"  📋 트랜잭션 상태: {tx_info['step']}")
                            print(f"    상태: {tx_info['status']}")
                        else:
                            print(f"  ❌ 트랜잭션이 완료되어 조회되지 않음 (정상)")
                    else:
                        print(f"  ❌ 트랜잭션 상태 조회 실패: {response.status_code}")
                    
                else:
                    print(f"  ❌ 대여 실패: {data.get('error')}")
            else:
                print(f"  ❌ 대여 HTTP 오류: {response.status_code}")
                if response.text:
                    print(f"    응답: {response.text}")
        except Exception as e:
            print(f"  ❌ 대여 연결 오류: {e}")
        
        # 8. 최종 활성 트랜잭션 확인
        print(f"\n🔄 8. 최종 활성 트랜잭션 확인")
        
        try:
            response = requests.get(f"{base_url}/api/transactions/active", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    transactions = data.get('transactions', [])
                    print(f"  ✅ 활성 트랜잭션: {len(transactions)}개")
                    
                    if transactions:
                        for tx in transactions:
                            print(f"    - ID: {tx['transaction_id'][:8]}...")
                            print(f"      단계: {tx['step']}, 상태: {tx['status']}")
                    else:
                        print(f"  🎉 모든 트랜잭션이 완료되었습니다!")
        except Exception as e:
            print(f"  ❌ 최종 트랜잭션 조회 오류: {e}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Flask 앱이 실행되지 않았습니다.")
        print("   다음 명령으로 Flask 앱을 시작하세요:")
        print("   python3 run.py")
        return False
    
    print(f"\n✅ API 엔드포인트 테스트 완료!")
    return True


if __name__ == '__main__':
    test_api_endpoints()
