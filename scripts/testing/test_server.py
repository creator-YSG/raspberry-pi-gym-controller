#!/usr/bin/env python3
"""
간단한 테스트 서버 (API 테스트용)
"""

import sys
import os
from flask import Flask, jsonify, request
import asyncio

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.locker_service import LockerService
from app.services.member_service import MemberService
from database import DatabaseManager, TransactionManager

app = Flask(__name__)

@app.route('/api/system/status')
def system_status():
    """시스템 상태 조회"""
    return jsonify({
        'success': True,
        'status': {
            'database': 'connected',
            'esp32': 'simulation_mode',
            'timestamp': '2025-10-01T18:15:00'
        }
    })

@app.route('/api/members/<member_id>/validate')
def validate_member(member_id):
    """회원 유효성 검증"""
    try:
        member_service = MemberService('instance/gym_system.db')
        
        try:
            result = member_service.validate_member(member_id)
            return jsonify(result)
        finally:
            member_service.close()
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': f'회원 검증 중 오류: {str(e)}'
        }), 500

@app.route('/api/transactions/active')
def get_active_transactions():
    """활성 트랜잭션 목록 조회"""
    try:
        db = DatabaseManager('instance/gym_system.db')
        db.connect()
        tx_manager = TransactionManager(db)
        
        try:
            transactions = asyncio.run(tx_manager.get_active_transactions())
            
            return jsonify({
                'success': True,
                'transactions': transactions,
                'count': len(transactions)
            })
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'활성 트랜잭션 조회 중 오류: {str(e)}'
        }), 500

@app.route('/api/transactions/<transaction_id>/status')
def get_transaction_status(transaction_id):
    """트랜잭션 상태 조회"""
    try:
        db = DatabaseManager('instance/gym_system.db')
        db.connect()
        tx_manager = TransactionManager(db)
        
        try:
            status = asyncio.run(tx_manager.get_transaction_status(transaction_id))
            
            if status:
                return jsonify({
                    'success': True,
                    'transaction': status
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '트랜잭션을 찾을 수 없습니다.'
                }), 404
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'트랜잭션 상태 조회 중 오류: {str(e)}'
        }), 500

@app.route('/api/lockers/<locker_id>/rent', methods=['POST'])
def rent_locker(locker_id):
    """락카 대여"""
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        
        if not member_id:
            return jsonify({
                'success': False,
                'error': '회원 ID가 필요합니다.'
            }), 400
        
        locker_service = LockerService('instance/gym_system.db')
        
        try:
            result = asyncio.run(locker_service.rent_locker(locker_id, member_id))
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'transaction_id': result['transaction_id'],
                    'locker_id': result['locker_id'],
                    'member_id': result['member_id'],
                    'member_name': result['member_name'],
                    'step': result['step'],
                    'message': result['message'],
                    'timeout_seconds': result.get('timeout_seconds', 30)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result['error'],
                    'step': result.get('step', 'unknown')
                }), 400
        finally:
            locker_service.close()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'락카 대여 중 오류: {str(e)}'
        }), 500

@app.route('/api/hardware/simulate_sensor', methods=['POST'])
def simulate_sensor_event():
    """센서 이벤트 시뮬레이션"""
    try:
        from app.services.sensor_event_handler import SensorEventHandler
        
        data = request.get_json()
        sensor_num = data.get('sensor_num')
        state = data.get('state', 'LOW')
        
        if not sensor_num:
            return jsonify({
                'success': False,
                'error': '센서 번호가 필요합니다.'
            }), 400
        
        if state not in ['HIGH', 'LOW']:
            return jsonify({
                'success': False,
                'error': '센서 상태는 HIGH 또는 LOW여야 합니다.'
            }), 400
        
        sensor_handler = SensorEventHandler('instance/gym_system.db')
        
        try:
            result = asyncio.run(sensor_handler.handle_sensor_event(sensor_num, state))
            
            # 센서-락카 매핑 정보
            mapping = sensor_handler.get_sensor_locker_mapping()
            locker_id = mapping.get(sensor_num, 'Unknown')
            
            return jsonify({
                'success': True,
                'message': f'센서 이벤트 시뮬레이션 완료: 센서{sensor_num} → {state}',
                'sensor_num': sensor_num,
                'locker_id': locker_id,
                'state': state,
                'result': result
            })
        finally:
            sensor_handler.close()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'센서 이벤트 시뮬레이션 중 오류: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("🧪 테스트 서버 시작...")
    print("📡 API 엔드포인트:")
    print("  - GET  /api/system/status")
    print("  - GET  /api/members/<id>/validate")
    print("  - GET  /api/transactions/active")
    print("  - GET  /api/transactions/<id>/status")
    print("  - POST /api/lockers/<id>/rent")
    print("  - POST /api/hardware/simulate_sensor")
    print("🌐 서버 주소: http://localhost:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5001, debug=True)
