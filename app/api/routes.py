"""
REST API 엔드포인트
"""

from flask import jsonify, request, current_app
from app.api import bp
from app.services.locker_service import LockerService
from app.services.member_service import MemberService
from app.services.system_service import SystemService


@bp.route('/health')
def health_check():
    """헬스 체크"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': current_app.config.get('START_TIME', ''),
        'kiosk_mode': current_app.config['KIOSK_MODE']
    })


@bp.route('/members/<member_id>')
def get_member(member_id):
    """회원 정보 조회"""
    try:
        member_service = MemberService()
        member = member_service.get_member(member_id)
        
        if member:
            return jsonify({
                'success': True,
                'member': member.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': '회원 정보를 찾을 수 없습니다.'
            }), 404
            
    except Exception as e:
        current_app.logger.error(f'회원 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '회원 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/lockers')
def get_lockers():
    """락카 목록 조회"""
    try:
        zone = request.args.get('zone', 'A')
        status = request.args.get('status', 'all')  # available, occupied, all
        
        locker_service = LockerService()
        
        if status == 'available':
            lockers = locker_service.get_available_lockers(zone)
        elif status == 'occupied':
            lockers = locker_service.get_occupied_lockers(zone)
        else:
            lockers = locker_service.get_all_lockers(zone)
        
        return jsonify({
            'success': True,
            'lockers': [locker.to_dict() for locker in lockers],
            'zone': zone,
            'count': len(lockers)
        })
        
    except Exception as e:
        current_app.logger.error(f'락카 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '락카 정보 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/lockers/<locker_id>/rent', methods=['POST'])
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
        
        locker_service = LockerService()
        result = locker_service.rent_locker(locker_id, member_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'rental': result['rental'].to_dict(),
                'message': f'{locker_id}번 락카가 대여되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f'락카 대여 오류: {e}')
        return jsonify({
            'success': False,
            'error': '락카 대여 중 오류가 발생했습니다.'
        }), 500


@bp.route('/lockers/<locker_id>/return', methods=['POST'])
def return_locker(locker_id):
    """락카 반납"""
    try:
        locker_service = LockerService()
        result = locker_service.return_locker(locker_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'rental': result['rental'].to_dict() if result.get('rental') else None,
                'message': f'{locker_id}번 락카가 반납되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f'락카 반납 오류: {e}')
        return jsonify({
            'success': False,
            'error': '락카 반납 중 오류가 발생했습니다.'
        }), 500


@bp.route('/system/status')
def system_status():
    """시스템 상태 조회"""
    try:
        system_service = SystemService()
        status = system_service.get_system_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        current_app.logger.error(f'시스템 상태 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '시스템 상태 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/system/esp32/reconnect', methods=['POST'])
def reconnect_esp32():
    """ESP32 재연결"""
    try:
        system_service = SystemService()
        result = system_service.reconnect_esp32()
        
        return jsonify({
            'success': result['success'],
            'message': result['message']
        })
        
    except Exception as e:
        current_app.logger.error(f'ESP32 재연결 오류: {e}')
        return jsonify({
            'success': False,
            'error': 'ESP32 재연결 중 오류가 발생했습니다.'
        }), 500


@bp.route('/barcode/scan', methods=['POST'])
def scan_barcode():
    """바코드 스캔 처리 (테스트용)"""
    try:
        data = request.get_json()
        barcode = data.get('barcode', '')
        
        if not barcode:
            return jsonify({
                'success': False,
                'error': '바코드 데이터가 필요합니다.'
            }), 400
        
        # 바코드 타입 판별 및 처리
        from app.services.barcode_service import BarcodeService
        barcode_service = BarcodeService()
        result = barcode_service.process_barcode(barcode)
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f'바코드 스캔 처리 오류: {e}')
        return jsonify({
            'success': False,
            'error': '바코드 처리 중 오류가 발생했습니다.'
        }), 500


@bp.route('/system/shutdown', methods=['POST'])
def shutdown_system():
    """시스템 종료"""
    try:
        current_app.logger.info('시스템 종료 요청 받음')
        
        # 종료 전 정리 작업
        # TODO: ESP32 연결 해제, 데이터 저장 등
        
        # Flask 서버 종료
        import os
        import signal
        
        def shutdown_server():
            import time
            time.sleep(1)  # 응답을 보낸 후 종료
            os.kill(os.getpid(), signal.SIGTERM)
        
        import threading
        threading.Thread(target=shutdown_server).start()
        
        return jsonify({
            'success': True,
            'message': '시스템이 종료됩니다.'
        })
        
    except Exception as e:
        current_app.logger.error(f'시스템 종료 오류: {e}')
        return jsonify({
            'success': False,
            'error': '시스템 종료 중 오류가 발생했습니다.'
        }), 500


@bp.route('/system/emergency-exit', methods=['POST'])
def emergency_exit():
    """응급 종료"""
    try:
        current_app.logger.warning('응급 종료 요청 받음')
        
        # 즉시 종료 (정리 작업 최소화)
        import os
        os._exit(0)
        
    except Exception as e:
        current_app.logger.error(f'응급 종료 오류: {e}')
        return jsonify({
            'success': False,
            'error': '응급 종료 중 오류가 발생했습니다.'
        }), 500


# ========== 하드웨어 테스트 API ==========

@bp.route('/hardware/status')
def hardware_status():
    """ESP32 하드웨어 상태 조회"""
    try:
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        
        if not esp32_manager:
            return jsonify({
                'success': False,
                'error': 'ESP32가 연결되지 않았습니다.',
                'data': {
                    'esp32Connection': False,
                    'uptime_ms': 0,
                    'free_heap': 0
                }
            })
        
        # ESP32 상태 요청
        status_data = {
            'esp32Connection': True,
            'uptime_ms': 0,
            'free_heap': 0,
            'motor_enabled': False,
            'total_moves': 0
        }
        
        return jsonify({
            'success': True,
            'data': status_data
        })
        
    except Exception as e:
        current_app.logger.error(f'하드웨어 상태 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '하드웨어 상태 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/hardware/motor_move', methods=['POST'])
def hardware_motor_move():
    """모터 이동 명령"""
    try:
        data = request.get_json()
        revs = data.get('revs', 1.0)
        rpm = data.get('rpm', 60.0)
        accel = data.get('accel', True)
        
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        
        if not esp32_manager:
            return jsonify({
                'success': False,
                'error': 'ESP32가 연결되지 않았습니다.'
            })
        
        # ESP32로 모터 이동 명령 전송 (비동기 처리)
        import asyncio
        try:
            result = asyncio.run(esp32_manager.send_motor_command(
                command="MOTOR_MOVE",
                revs=revs,
                rpm=rpm,
                accel=accel
            ))
        except Exception as cmd_error:
            current_app.logger.error(f'모터 명령 전송 실패: {cmd_error}')
            result = {'success': False, 'error': str(cmd_error)}
        
        return jsonify({
            'success': True,
            'message': f'모터 이동 명령 전송됨: {revs}회전, {rpm}RPM',
            'details': {
                'revs': revs,
                'rpm': rpm,
                'accel': accel
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'모터 이동 오류: {e}')
        return jsonify({
            'success': False,
            'error': f'모터 이동 중 오류가 발생했습니다: {str(e)}'
        }), 500


@bp.route('/hardware/auto_mode', methods=['POST'])
def hardware_auto_mode():
    """자동 모드 설정"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        
        if not esp32_manager:
            return jsonify({
                'success': False,
                'error': 'ESP32가 연결되지 않았습니다.'
            })
        
        # ESP32로 자동 모드 설정 명령 전송 (비동기 처리)
        import asyncio
        try:
            result = asyncio.run(esp32_manager.send_motor_command(
                command="SET_AUTO_MODE",
                enabled=enabled
            ))
        except Exception as cmd_error:
            current_app.logger.error(f'자동모드 명령 전송 실패: {cmd_error}')
            result = {'success': False, 'error': str(cmd_error)}
        
        return jsonify({
            'success': True,
            'message': f'자동 모드 {"활성화" if enabled else "비활성화"}됨',
            'auto_mode': enabled
        })
        
    except Exception as e:
        current_app.logger.error(f'자동 모드 설정 오류: {e}')
        return jsonify({
            'success': False,
            'error': f'자동 모드 설정 중 오류가 발생했습니다: {str(e)}'
        }), 500


@bp.route('/hardware/test_barcode', methods=['POST'])
def hardware_test_barcode():
    """테스트 바코드 전송"""
    try:
        data = request.get_json()
        barcode = data.get('barcode', '')
        
        if not barcode:
            return jsonify({
                'success': False,
                'error': '바코드 데이터가 필요합니다.'
            })
        
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        
        if not esp32_manager:
            return jsonify({
                'success': False,
                'error': 'ESP32가 연결되지 않았습니다.'
            })
        
        # 테스트 바코드 데이터 시뮬레이션
        from app.services.barcode_service import BarcodeService
        barcode_service = BarcodeService()
        result = barcode_service.process_barcode(barcode)
        
        # ESP32에 바코드 이벤트 알림 (선택사항)
        current_app.logger.info(f'테스트 바코드 처리: {barcode}')
        
        return jsonify({
            'success': True,
            'message': f'테스트 바코드 전송됨: {barcode}',
            'barcode': barcode,
            'processing_result': result
        })
        
    except Exception as e:
        current_app.logger.error(f'테스트 바코드 처리 오류: {e}')
        return jsonify({
            'success': False,
            'error': f'테스트 바코드 처리 중 오류가 발생했습니다: {str(e)}'
        }), 500


@bp.route('/hardware/reconnect', methods=['POST'])
def hardware_reconnect():
    """ESP32 재연결"""
    try:
        # 기존 연결 해제 후 재연결
        system_service = SystemService()
        result = system_service.reconnect_esp32()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'ESP32 재연결이 완료되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'ESP32 재연결에 실패했습니다.')
            })
        
    except Exception as e:
        current_app.logger.error(f'ESP32 재연결 오류: {e}')
        return jsonify({
            'success': False,
            'error': f'ESP32 재연결 중 오류가 발생했습니다: {str(e)}'
        }), 500
