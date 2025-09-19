"""
WebSocket 이벤트 핸들러
"""

from flask_socketio import emit, join_room, leave_room
from flask import request, current_app
from app import socketio


@socketio.on('connect')
def handle_connect():
    """클라이언트 연결"""
    client_id = request.sid
    current_app.logger.info(f'클라이언트 연결: {client_id}')
    
    # 키오스크 방에 참가
    join_room('kiosk')
    
    emit('connected', {
        'status': 'success',
        'client_id': client_id,
        'message': '락카키 대여기에 연결되었습니다.'
    })


@socketio.on('disconnect')
def handle_disconnect():
    """클라이언트 연결 해제"""
    client_id = request.sid
    current_app.logger.info(f'클라이언트 연결 해제: {client_id}')
    
    leave_room('kiosk')


@socketio.on('barcode_scanned')
def handle_barcode_scan(data):
    """바코드 스캔 이벤트"""
    try:
        barcode = data.get('barcode', '')
        scan_type = data.get('type', 'unknown')  # member, locker_key, unknown
        
        current_app.logger.info(f'바코드 스캔: {barcode} (타입: {scan_type})')
        
        # 바코드 처리
        from app.services.barcode_service import BarcodeService
        barcode_service = BarcodeService()
        result = barcode_service.process_barcode(barcode, scan_type)
        
        # 처리 결과를 클라이언트로 전송
        emit('barcode_processed', result)
        
        # 키오스크 화면 업데이트 (필요시)
        if result['success']:
            if result['action'] == 'show_member_info':
                emit('navigate_to', {
                    'page': 'member_check',
                    'params': {'member_id': result['member']['id']}
                }, room='kiosk')
            
            elif result['action'] == 'show_locker_select':
                emit('navigate_to', {
                    'page': 'locker_select', 
                    'params': {'member_id': result['member']['id']}
                }, room='kiosk')
            
            elif result['action'] == 'process_return':
                emit('navigate_to', {
                    'page': 'return_complete',
                    'params': {'locker_id': result['locker']['id']}
                }, room='kiosk')
        
    except Exception as e:
        current_app.logger.error(f'바코드 스캔 처리 오류: {e}')
        emit('barcode_processed', {
            'success': False,
            'error': '바코드 처리 중 오류가 발생했습니다.'
        })


@socketio.on('locker_selected')
def handle_locker_selection(data):
    """락카 선택 이벤트"""
    try:
        locker_id = data.get('locker_id', '')
        member_id = data.get('member_id', '')
        
        current_app.logger.info(f'락카 선택: {locker_id} (회원: {member_id})')
        
        # 락카 대여 처리
        from app.services.locker_service import LockerService
        locker_service = LockerService()
        result = locker_service.rent_locker(locker_id, member_id)
        
        if result['success']:
            # ESP32에 락카 열기 명령 전송
            emit('locker_command', {
                'action': 'open',
                'locker_id': locker_id,
                'duration': 3000  # 3초
            })
            
            # 대여 완료 화면으로 이동
            emit('navigate_to', {
                'page': 'rental_complete',
                'params': {
                    'locker_id': locker_id,
                    'member_id': member_id
                }
            })
        
        emit('locker_selected_result', result)
        
    except Exception as e:
        current_app.logger.error(f'락카 선택 처리 오류: {e}')
        emit('locker_selected_result', {
            'success': False,
            'error': '락카 선택 처리 중 오류가 발생했습니다.'
        })


@socketio.on('system_command')
def handle_system_command(data):
    """시스템 명령 처리"""
    try:
        command = data.get('command', '')
        params = data.get('params', {})
        
        current_app.logger.info(f'시스템 명령: {command}')
        
        from app.services.system_service import SystemService
        system_service = SystemService()
        
        if command == 'restart_system':
            result = system_service.restart_system()
        elif command == 'reconnect_esp32':
            result = system_service.reconnect_esp32()
        elif command == 'sync_google_sheets':
            result = system_service.sync_google_sheets()
        elif command == 'get_logs':
            result = system_service.get_recent_logs(params.get('lines', 50))
        else:
            result = {
                'success': False,
                'error': f'알 수 없는 명령: {command}'
            }
        
        emit('system_command_result', result)
        
    except Exception as e:
        current_app.logger.error(f'시스템 명령 처리 오류: {e}')
        emit('system_command_result', {
            'success': False,
            'error': '시스템 명령 처리 중 오류가 발생했습니다.'
        })


@socketio.on('heartbeat')
def handle_heartbeat():
    """하트비트 (연결 상태 확인)"""
    emit('heartbeat_response', {
        'timestamp': current_app.config.get('START_TIME', ''),
        'status': 'alive'
    })


# ESP32 이벤트 (외부에서 호출)
def broadcast_esp32_event(event_type, data):
    """ESP32 이벤트를 모든 클라이언트에 브로드캐스트"""
    socketio.emit('esp32_event', {
        'type': event_type,
        'data': data,
        'timestamp': data.get('timestamp', '')
    }, room='kiosk')


def broadcast_system_alert(alert_type, message):
    """시스템 알림 브로드캐스트"""
    socketio.emit('system_alert', {
        'type': alert_type,  # info, warning, error, success
        'message': message,
        'timestamp': current_app.config.get('START_TIME', '')
    }, room='kiosk')
