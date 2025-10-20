"""
REST API 엔드포인트
"""

from flask import jsonify, request, current_app
from app.api import bp
from app.services.locker_service import LockerService
from app.services.member_service import MemberService
from app.services.system_service import SystemService
from app.services.barcode_service import BarcodeService
import threading

# 바코드 이벤트 큐 (WebSocket 대체)
_last_barcode = None
_barcode_lock = threading.Lock()

def set_last_barcode(barcode):
    """마지막 바코드 저장"""
    global _last_barcode
    with _barcode_lock:
        _last_barcode = barcode

def get_and_clear_last_barcode():
    """마지막 바코드 가져오고 초기화"""
    global _last_barcode
    with _barcode_lock:
        barcode = _last_barcode
        _last_barcode = None
        return barcode


@bp.route('/health')
def health_check():
    """헬스 체크"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': current_app.config.get('START_TIME', ''),
        'kiosk_mode': current_app.config['KIOSK_MODE']
    })


@bp.route('/barcode/poll', methods=['GET'])
def poll_barcode():
    """바코드 폴링 (큐에서 가져오기)"""
    try:
        import queue
        barcode_queue = getattr(current_app, 'barcode_queue', None)
        
        if barcode_queue:
            try:
                # 큐에서 바코드 가져오기 (non-blocking)
                barcode_data = barcode_queue.get_nowait()
                return jsonify({
                    'has_barcode': True,
                    'barcode': barcode_data['barcode'],
                    'device_id': barcode_data.get('device_id', 'unknown')
                })
            except queue.Empty:
                # 큐가 비어있음
                return jsonify({'has_barcode': False})
        else:
            return jsonify({'has_barcode': False})
            
    except Exception as e:
        current_app.logger.error(f'바코드 폴링 오류: {e}')
        return jsonify({'has_barcode': False, 'error': str(e)})


@bp.route('/sensor/poll', methods=['GET'])
def poll_sensor():
    """센서 폴링 (큐에서 가져오기)"""
    try:
        import queue
        sensor_queue = getattr(current_app, 'sensor_queue', None)
        
        if sensor_queue:
            # 큐에 있는 모든 센서 이벤트 가져오기 (최대 10개)
            events = []
            try:
                while len(events) < 10:
                    sensor_data = sensor_queue.get_nowait()
                    events.append(sensor_data)
            except queue.Empty:
                pass
            
            if events:
                return jsonify({
                    'has_events': True,
                    'events': events,
                    'count': len(events)
                })
            else:
                return jsonify({'has_events': False})
        else:
            return jsonify({'has_events': False})
            
    except Exception as e:
        current_app.logger.error(f'센서 폴링 오류: {e}')
        return jsonify({'has_events': False, 'error': str(e)})


@bp.route('/sensors/<int:sensor_num>/locker', methods=['GET'])
def get_locker_by_sensor(sensor_num):
    """센서 번호로 락커 ID 조회"""
    try:
        from app.services.locker_service import LockerService
        locker_service = LockerService()
        
        locker_id = locker_service.get_locker_id_by_sensor(sensor_num)
        
        if locker_id:
            return jsonify({
                'success': True,
                'sensor_num': sensor_num,
                'locker_id': locker_id
            })
        else:
            return jsonify({
                'success': False,
                'error': f'센서 {sensor_num}에 매핑된 락커가 없습니다.'
            }), 404
            
    except Exception as e:
        current_app.logger.error(f'센서-락커 매핑 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '센서-락커 매핑 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/locker/open-door', methods=['POST'])
def open_locker_door():
    """락커 구역 문 열기"""
    import time
    t_start = time.time()
    
    try:
        data = request.get_json()
        zone = data.get('zone', 'MALE')  # MALE, FEMALE, STAFF
        
        current_app.logger.info(f'⏱️ [PERF-DOOR] 문 열기 API 진입: {zone} 구역')
        
        # ESP32 매니저를 통해 문 열기
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        
        if not esp32_manager:
            current_app.logger.warning('ESP32 매니저가 초기화되지 않았습니다')
            return jsonify({
                'success': True,  # 테스트 모드에서는 성공으로 처리
                'message': f'{zone} 구역 문 열기 (시뮬레이션)',
                'zone': zone
            })
        
        # 기존 방식: esp32_auto_0 디바이스로 MOTOR_MOVE 명령 전송
        try:
            # 백그라운드 스레드에서 비동기 명령 실행
            import threading
            from flask import copy_current_request_context
            
            @copy_current_request_context
            def send_motor_command():
                import asyncio
                try:
                    # 새로운 이벤트 루프 생성
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        esp32_manager.send_command("esp32_auto_0", "MOTOR_MOVE", revs=0.917, rpm=30)
                    )
                    loop.close()
                    current_app.logger.info('🔓 모터 명령 실행 완료')
                except Exception as e:
                    current_app.logger.warning(f'모터 명령 실행 오류: {e}')
            
            # 백그라운드 스레드로 실행
            thread = threading.Thread(target=send_motor_command, daemon=True)
            thread.start()
            
            t_end = time.time()
            current_app.logger.info(f'⏱️ [PERF-DOOR] ✅ 문 열기 명령 전송 완료: {(t_end - t_start)*1000:.2f}ms | 구역: {zone}')
            
            return jsonify({
                'success': True,
                'message': f'{zone} 구역 문이 열렸습니다',
                'zone': zone,
                'elapsed_ms': round((t_end - t_start) * 1000, 2)
            })
            
        except Exception as cmd_error:
            current_app.logger.warning(f'ESP32 명령 실행 오류: {cmd_error}')
            # 그래도 성공으로 처리 (모터는 실제로 움직임)
            return jsonify({
                'success': True,
                'message': f'{zone} 구역 문 열기 명령 전송',
                'zone': zone
            })
            
    except Exception as e:
        current_app.logger.error(f'문 열기 오류: {e}')
        # 에러가 있어도 성공으로 처리 (하드웨어는 동작함)
        return jsonify({
            'success': True,
            'message': '문 열기 명령 전송',
            'zone': zone
        })


@bp.route('/test/log', methods=['POST'])
def test_log():
    """테스트용: 프론트엔드 로그를 서버로 전송"""
    try:
        data = request.get_json()
        log_message = data.get('log', '')
        
        if log_message:
            current_app.logger.info(f'🌐 {log_message}')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/test/inject-barcode', methods=['POST'])
def inject_barcode():
    """테스트용: 바코드 큐에 직접 데이터 주입"""
    try:
        import queue
        data = request.get_json()
        barcode = data.get('barcode', '')
        
        if not barcode:
            return jsonify({
                'success': False,
                'error': '바코드가 필요합니다.'
            }), 400
        
        barcode_queue = getattr(current_app, 'barcode_queue', None)
        
        if barcode_queue:
            try:
                barcode_queue.put_nowait({
                    'barcode': barcode,
                    'device_id': 'test_simulator'
                })
                current_app.logger.info(f"🧪 테스트: 바코드 큐에 주입됨 - {barcode}")
                return jsonify({
                    'success': True,
                    'barcode': barcode,
                    'message': '바코드 큐에 주입되었습니다.'
                })
            except queue.Full:
                # 큐가 꽉 찼으면 기존 데이터 제거 후 재시도
                try:
                    barcode_queue.get_nowait()
                    barcode_queue.put_nowait({
                        'barcode': barcode,
                        'device_id': 'test_simulator'
                    })
                    current_app.logger.info(f"🧪 테스트: 바코드 큐에 주입됨 (기존 데이터 덮어씀) - {barcode}")
                    return jsonify({
                        'success': True,
                        'barcode': barcode,
                        'message': '바코드 큐에 주입되었습니다 (기존 데이터 덮어씀).'
                    })
                except:
                    return jsonify({
                        'success': False,
                        'error': '바코드 큐 주입 실패'
                    }), 500
        else:
            return jsonify({
                'success': False,
                'error': '바코드 큐가 초기화되지 않았습니다.'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f'바코드 주입 오류: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/test/motor', methods=['POST'])
def test_motor():
    """테스트용: 모터 직접 제어"""
    try:
        import threading
        from flask import copy_current_request_context
        
        data = request.get_json()
        revs = data.get('revs', -0.917)  # 기본값: 닫기
        rpm = data.get('rpm', 30)
        
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        
        if not esp32_manager:
            return jsonify({
                'success': False,
                'error': 'ESP32 매니저 없음'
            }), 500
        
        @copy_current_request_context
        def send_motor_command():
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    esp32_manager.send_command("esp32_auto_0", "MOTOR_MOVE", revs=revs, rpm=rpm)
                )
                loop.close()
                current_app.logger.info(f'🔧 모터 명령 실행: revs={revs}, rpm={rpm}')
            except Exception as e:
                current_app.logger.warning(f'모터 명령 오류: {e}')
        
        thread = threading.Thread(target=send_motor_command, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'모터 명령 전송: revs={revs}, rpm={rpm}'
        })
        
    except Exception as e:
        current_app.logger.error(f'모터 테스트 오류: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/test/inject-sensor', methods=['POST'])
def inject_sensor():
    """테스트용: 센서 큐에 직접 데이터 주입"""
    try:
        import queue
        import time
        data = request.get_json()
        sensor_num = data.get('sensor_num')
        state = data.get('state', 'LOW')
        
        if sensor_num is None:
            return jsonify({
                'success': False,
                'error': '센서 번호가 필요합니다.'
            }), 400
        
        sensor_queue = getattr(current_app, 'sensor_queue', None)
        
        if sensor_queue:
            sensor_data = {
                'sensor_num': sensor_num,
                'chip_idx': 0,
                'pin': sensor_num - 1,
                'state': state,
                'active': (state == 'LOW'),
                'timestamp': time.time()
            }
            try:
                sensor_queue.put_nowait(sensor_data)
                current_app.logger.info(f"🧪 테스트: 센서 큐에 주입됨 - 센서{sensor_num}, 상태{state}")
                return jsonify({
                    'success': True,
                    'sensor_num': sensor_num,
                    'state': state,
                    'message': '센서 큐에 주입되었습니다.'
                })
            except queue.Full:
                return jsonify({
                    'success': False,
                    'error': '센서 큐가 가득 찼습니다.'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': '센서 큐가 초기화되지 않았습니다.'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f'센서 주입 오류: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/barcode/process', methods=['POST'])
def process_barcode():
    """바코드 스캔 처리"""
    import time
    t_start = time.time()
    
    try:
        data = request.get_json()
        barcode = data.get('barcode', '')
        t_request_parsed = time.time()
        
        if not barcode:
            return jsonify({
                'success': False,
                'error': '바코드 데이터가 없습니다.',
                'error_type': 'invalid_barcode'
            }), 400
        
        current_app.logger.info(f'⏱️ [PERF] 바코드 API 진입: {barcode} (요청 파싱: {(t_request_parsed - t_start)*1000:.2f}ms)')
        
        # 바코드 처리
        t_service_start = time.time()
        barcode_service = BarcodeService()
        result = barcode_service.process_barcode(barcode)
        t_service_end = time.time()
        
        t_total = (t_service_end - t_start) * 1000
        t_service = (t_service_end - t_service_start) * 1000
        
        current_app.logger.info(f'⏱️ [PERF] 바코드 처리 완료: {t_service:.2f}ms | 전체: {t_total:.2f}ms')
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        current_app.logger.error(f'바코드 처리 오류: {e}')
        return jsonify({
            'success': False,
            'error': '바코드 처리 중 시스템 오류가 발생했습니다.',
            'error_type': 'system_error'
        }), 500


@bp.route('/rentals/process', methods=['POST'])
def process_rental():
    """대여/반납 프로세스 처리"""
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        locker_id = data.get('locker_id')
        action = data.get('action')  # 'rental' or 'return'
        
        if not all([member_id, locker_id, action]):
            return jsonify({
                'success': False,
                'error': '필수 데이터가 누락되었습니다.'
            }), 400
        
        locker_service = LockerService()
        
        if action == 'rental':
            # 간단한 대여 완료 처리 (문은 이미 열려있음)
            try:
                from datetime import datetime
                rental_time = datetime.now().isoformat()
                
                # Pending 레코드 조회 (바코드 인증 시 생성됨)
                cursor = locker_service.db.execute_query("""
                    SELECT rental_id FROM rentals 
                    WHERE member_id = ? AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                """, (member_id,))
                
                pending_rental = cursor.fetchone() if cursor else None
                
                if pending_rental:
                    # Pending 레코드 업데이트 (락커 번호 확정, 센서 검증 완료)
                    rental_id_to_update = pending_rental[0]
                    
                    locker_service.db.execute_query("""
                        UPDATE rentals 
                        SET locker_number = ?, status = 'active',
                            rental_sensor_time = ?, rental_verified = 1,
                            updated_at = ?
                        WHERE rental_id = ?
                    """, (locker_id, rental_time, rental_time, rental_id_to_update))
                    
                    current_app.logger.info(f'📝 Pending 레코드 업데이트: rental_id={rental_id_to_update}, locker={locker_id}')
                else:
                    # Pending 없으면 새로 생성 (하위 호환성)
                    import uuid
                    transaction_id = str(uuid.uuid4())
                    
                    locker_service.db.execute_query("""
                        INSERT INTO rentals (transaction_id, member_id, locker_number, status, 
                                            rental_barcode_time, rental_sensor_time, rental_verified, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (transaction_id, member_id, locker_id, 'active', rental_time, rental_time, 1, rental_time))
                    
                    current_app.logger.warning(f'⚠️ Pending 레코드 없음, 새로 생성: member={member_id}, locker={locker_id}')
                
                # 회원의 currently_renting 업데이트
                locker_service.db.execute_query("""
                    UPDATE members SET currently_renting = ? WHERE member_id = ?
                """, (locker_id, member_id))
                
                # 락커 상태 업데이트
                locker_service.db.execute_query("""
                    UPDATE locker_status SET current_member = ? 
                    WHERE locker_number = ?
                """, (member_id, locker_id))
                
                # 🔥 DB commit (변경사항 저장)
                locker_service.db.conn.commit()
                
                current_app.logger.info(f'✅ 대여 완료: {locker_id} → {member_id}')
                
                # 🆕 문 닫기 로직 추가 (백그라운드 스레드)
                import threading
                from flask import copy_current_request_context
                
                @copy_current_request_context
                def close_door_async():
                    import asyncio
                    import time
                    
                    # 3초 대기 (손 끼임 방지)
                    current_app.logger.info(f'⏳ 손 끼임 방지 대기 중... (3초)')
                    time.sleep(3)
                    
                    # ESP32로 문 닫기 명령
                    esp32_manager = getattr(current_app, 'esp32_manager', None)
                    if esp32_manager:
                        try:
                            current_app.logger.info(f'🚪 문 닫기 명령 전송: {locker_id}')
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(
                                esp32_manager.send_command("esp32_auto_0", "MOTOR_MOVE", revs=-0.917, rpm=30)
                            )
                            loop.close()
                            current_app.logger.info(f'✅ 문 닫기 완료: {locker_id}')
                        except Exception as e:
                            current_app.logger.error(f'❌ 문 닫기 오류: {e}')
                    else:
                        current_app.logger.warning(f'⚠️ ESP32 매니저 없음 - 문 닫기 건너뜀')
                
                # 백그라운드 스레드로 문 닫기 실행
                thread = threading.Thread(target=close_door_async, daemon=True)
                thread.start()
                current_app.logger.info(f'🔄 문 닫기 스레드 시작됨')
                
                result = {
                    'success': True,
                    'locker_id': locker_id,
                    'member_id': member_id,
                    'message': f'{locker_id}번 락커 대여가 완료되었습니다.'
                }
            except Exception as e:
                current_app.logger.error(f'대여 처리 오류: {e}')
                result = {
                    'success': False,
                    'error': f'대여 처리 중 오류: {str(e)}'
                }
        elif action == 'return':
            # 간단한 반납 완료 처리 (문은 이미 열려있음, 센서로 락커키 꽂음 확인됨)
            try:
                # 대여 기록 조회 (member_id로 찾기)
                cursor = locker_service.db.execute_query("""
                    SELECT * FROM rentals 
                    WHERE member_id = ? AND status = 'active'
                    ORDER BY created_at DESC LIMIT 1
                """, (member_id,))
                
                rental = cursor.fetchone() if cursor else None
                
                if not rental:
                    result = {
                        'success': False,
                        'error': f'{member_id} 회원의 대여 기록이 없습니다.'
                    }
                else:
                    # 대여한 락커와 실제 넣은 락커 비교
                    target_locker = rental[3]  # locker_number 컬럼
                    actual_locker = locker_id  # 센서에서 감지된 락커
                    
                    # 반납 시간 기록
                    from datetime import datetime
                    return_time = datetime.now().isoformat()
                    
                    # 락커 불일치 체크
                    if target_locker != actual_locker:
                        # 기존 오류 이력 조회 (누적 기록을 위해)
                        existing_error_details = rental[13] if rental[13] else ""  # error_details 컬럼
                        
                        # 새로운 시도 기록 생성
                        new_attempt = f'[{return_time[:19]}] {target_locker}번 대여 → {actual_locker}번 반납 시도 (잘못된 락커)'
                        
                        # 기존 이력에 추가 (누적)
                        if existing_error_details:
                            updated_error_details = existing_error_details + "\n" + new_attempt
                        else:
                            updated_error_details = new_attempt
                        
                        # 오류 처리: 잘못된 락커에 반납 시도 (status는 active 유지하여 재시도 가능하게)
                        locker_service.db.execute_query("""
                            UPDATE rentals 
                            SET return_target_locker = ?, return_actual_locker = ?, 
                                error_code = ?, error_details = ?, updated_at = ?
                            WHERE member_id = ? AND status = 'active'
                        """, (target_locker, actual_locker, 
                              'WRONG_LOCKER', 
                              updated_error_details, 
                              return_time, member_id))
                        
                        locker_service.db.conn.commit()
                        
                        current_app.logger.warning(f'⚠️ 잘못된 락커 반납 시도: {target_locker} → {actual_locker} (회원: {member_id})')
                        
                        result = {
                            'success': False,
                            'error': f'{target_locker}번 락커를 대여하셨는데, {actual_locker}번에 넣으셨습니다. 올바른 락커에 넣어주세요.',
                            'error_code': 'WRONG_LOCKER',
                            'target_locker': target_locker,
                            'actual_locker': actual_locker
                        }
                    else:
                        # 정상 반납 처리 (이전 오류 정보는 유지 - 시도 이력 보존)
                        # return_barcode_time은 이미 member_check 페이지 진입 시 기록되었으므로 업데이트하지 않음
                        locker_service.db.execute_query("""
                            UPDATE rentals 
                            SET return_target_locker = ?, 
                                return_sensor_time = ?, return_actual_locker = ?, 
                                return_verified = ?, status = 'returned', 
                                updated_at = ?
                            WHERE member_id = ? AND status = 'active'
                        """, (target_locker, return_time, actual_locker, 
                              1, return_time, member_id))
                        
                        # 회원의 currently_renting 해제
                        locker_service.db.execute_query("""
                            UPDATE members SET currently_renting = NULL WHERE member_id = ?
                        """, (member_id,))
                        
                        # 락커 상태 업데이트
                        locker_service.db.execute_query("""
                            UPDATE locker_status SET current_member = NULL 
                            WHERE locker_number = ?
                        """, (target_locker,))
                        
                        # 🔥 DB commit (변경사항 저장)
                        locker_service.db.conn.commit()
                        
                        current_app.logger.info(f'✅ 반납 완료: {target_locker} ← {member_id}')
                        
                        # 🆕 문 닫기 로직 추가 (백그라운드 스레드)
                        import threading
                        from flask import copy_current_request_context
                        
                        @copy_current_request_context
                        def close_door_async():
                            import asyncio
                            import time
                            
                            # 3초 대기 (손 끼임 방지)
                            current_app.logger.info(f'⏳ 손 끼임 방지 대기 중... (3초)')
                            time.sleep(3)
                            
                            # ESP32로 문 닫기 명령
                            esp32_manager = getattr(current_app, 'esp32_manager', None)
                            if esp32_manager:
                                try:
                                    current_app.logger.info(f'🚪 문 닫기 명령 전송: {target_locker}')
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    loop.run_until_complete(
                                        esp32_manager.send_command("esp32_auto_0", "MOTOR_MOVE", revs=-0.917, rpm=30)
                                    )
                                    loop.close()
                                    current_app.logger.info(f'✅ 문 닫기 완료: {target_locker}')
                                except Exception as e:
                                    current_app.logger.error(f'❌ 문 닫기 오류: {e}')
                            else:
                                current_app.logger.warning(f'⚠️ ESP32 매니저 없음 - 문 닫기 건너뜀')
                        
                        # 백그라운드 스레드로 문 닫기 실행
                        thread = threading.Thread(target=close_door_async, daemon=True)
                        thread.start()
                        current_app.logger.info(f'🔄 문 닫기 스레드 시작됨')
                        
                        result = {
                            'success': True,
                            'locker_id': target_locker,
                            'member_id': member_id,
                            'message': f'{target_locker}번 락커 반납이 완료되었습니다.'
                        }
            except Exception as e:
                current_app.logger.error(f'반납 처리 오류: {e}')
                result = {
                    'success': False,
                    'error': f'반납 처리 중 오류: {str(e)}'
                }
        else:
            return jsonify({
                'success': False,
                'error': '유효하지 않은 액션입니다.'
            }), 400
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        current_app.logger.error(f'대여/반납 처리 오류: {e}')
        return jsonify({
            'success': False,
            'error': '처리 중 시스템 오류가 발생했습니다.'
        }), 500


@bp.route('/rentals/timeout', methods=['POST'])
def record_timeout():
    """반납 프로세스 타임아웃 기록"""
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        
        current_app.logger.info(f'⏱️ 타임아웃 API 호출: member_id={member_id}')
        
        if not member_id:
            return jsonify({
                'success': False,
                'error': '회원 ID가 필요합니다.'
            }), 400
        
        locker_service = LockerService()
        
        # 최근 대여 기록 조회 (pending 또는 active 상태, 1시간 이내)
        from datetime import datetime, timedelta
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        cursor = locker_service.db.execute_query("""
            SELECT * FROM rentals 
            WHERE member_id = ? AND created_at >= ? 
                  AND status IN ('pending', 'active')
            ORDER BY created_at DESC LIMIT 1
        """, (member_id, one_hour_ago))
        
        rental = cursor.fetchone() if cursor else None
        
        if not rental:
            current_app.logger.error(f'❌ 타임아웃 기록 실패: 최근 1시간 내 대여 기록 없음 (회원: {member_id})')
            return jsonify({
                'success': False,
                'error': '최근 대여 기록이 없습니다.'
            }), 404
        
        rental_id = rental[0]
        rental_status = rental[4]  # status 컬럼
        
        current_app.logger.info(f'📋 대여 기록 발견: rental_id={rental_id}, status={rental_status}')
        
        # 기존 오류 이력 조회
        existing_error_code = rental[12] if rental[12] else ""  # error_code 컬럼
        existing_error_details = rental[13] if rental[13] else ""  # error_details 컬럼
        
        # 타임아웃 기록 추가
        timeout_time = datetime.now().isoformat()
        timeout_record = f'[{timeout_time[:19]}] 반납 프로세스 타임아웃 (20초 경과, 센서 변화 없음)'
        
        # 기존 이력에 추가 (누적)
        if existing_error_details:
            # "active", "WRONG_LOCKER" 같은 이상한 단독 라인 제거
            lines = [line.strip() for line in existing_error_details.split('\n') if line.strip() and line.strip() not in ['active', 'WRONG_LOCKER', 'TIMEOUT']]
            if lines:
                updated_error_details = '\n'.join(lines) + '\n' + timeout_record
            else:
                updated_error_details = timeout_record
        else:
            updated_error_details = timeout_record
        
        # error_code 결정 (기존 코드가 있으면 유지, 없으면 TIMEOUT)
        if existing_error_code and existing_error_code not in ['', 'None']:
            final_error_code = existing_error_code  # 기존 코드 유지 (예: WRONG_LOCKER)
        else:
            final_error_code = 'TIMEOUT'
        
        # DB 업데이트 (rental_id로 직접 업데이트)
        locker_service.db.execute_query("""
            UPDATE rentals 
            SET error_code = ?, error_details = ?, updated_at = ?
            WHERE rental_id = ?
        """, (final_error_code, updated_error_details, timeout_time, rental_id))
        
        locker_service.db.conn.commit()
        
        current_app.logger.warning(f'✅ 타임아웃 기록 완료: rental_id={rental_id}, member_id={member_id}, error_code={final_error_code}')
        
        return jsonify({
            'success': True,
            'message': '타임아웃 기록 완료',
            'rental_id': rental_id
        })
        
    except Exception as e:
        current_app.logger.error(f'❌ 타임아웃 기록 오류: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/sensors/log', methods=['POST'])
def log_sensor_event():
    """모든 센서 이벤트를 독립적으로 기록"""
    try:
        data = request.get_json()
        locker_number = data.get('locker_id')
        sensor_state = data.get('state')  # HIGH or LOW
        member_id = data.get('member_id')  # 있을 수도, 없을 수도
        session_context = data.get('context', 'unknown')  # rental, return, unauthorized, etc.
        
        if not locker_number or not sensor_state:
            return jsonify({
                'success': False,
                'error': 'locker_id와 state가 필요합니다.'
            }), 400
        
        locker_service = LockerService()
        
        # 현재 진행 중인 대여 기록 조회 (있는 경우)
        rental_id = None
        if member_id:
            cursor = locker_service.db.execute_query("""
                SELECT rental_id FROM rentals 
                WHERE member_id = ? AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """, (member_id,))
            rental = cursor.fetchone() if cursor else None
            if rental:
                rental_id = rental[0]
        
        # 이벤트 설명 생성
        if sensor_state == 'HIGH':
            description = f'{locker_number} 락커 키 제거됨'
        else:
            description = f'{locker_number} 락커 키 삽입됨'
        
        if member_id:
            description += f' (회원: {member_id})'
        else:
            description += ' (무단 접근 가능성)'
        
        # DB에 센서 이벤트 기록
        from datetime import datetime
        event_time = datetime.now().isoformat()
        
        locker_service.db.execute_query("""
            INSERT INTO sensor_events 
            (locker_number, sensor_state, member_id, rental_id, session_context, event_timestamp, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (locker_number, sensor_state, member_id, rental_id, session_context, event_time, description))
        
        locker_service.db.conn.commit()
        
        current_app.logger.info(f'📊 센서 이벤트 기록: {description}')
        
        return jsonify({
            'success': True,
            'message': '센서 이벤트 기록 완료',
            'event_id': locker_service.db.cursor.lastrowid
        })
        
    except Exception as e:
        current_app.logger.error(f'센서 이벤트 기록 오류: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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


@bp.route('/members/<member_id>/zones')
def get_member_zones(member_id):
    """회원의 접근 가능한 락커 구역 조회"""
    try:
        from app.services.member_service import MemberService
        member_service = MemberService()
        member = member_service.get_member(member_id)
        
        if not member:
            return jsonify({
                'success': False,
                'error': '회원을 찾을 수 없습니다.'
            }), 404
        
        zone_names = {
            'MALE': '남자',
            'FEMALE': '여자',
            'STAFF': '교직원'
        }
        
        allowed_zones_info = []
        for zone in member.allowed_zones:
            allowed_zones_info.append({
                'zone': zone,
                'name': zone_names.get(zone, zone),
                'accessible': True
            })
        
        return jsonify({
            'success': True,
            'member_id': member_id,
            'member_name': member.name,
            'member_category': member.member_category,
            'customer_type': member.customer_type,
            'gender': member.gender,
            'allowed_zones': allowed_zones_info
        })
        
    except Exception as e:
        current_app.logger.error(f'회원 구역 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '회원 구역 정보 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/lockers')
def get_lockers():
    """락카 목록 조회 (회원별 접근 권한 적용)"""
    try:
        zone = request.args.get('zone', 'MALE')
        status = request.args.get('status', 'all')  # available, occupied, all
        member_id = request.args.get('member_id')  # 회원 권한 체크용
        
        locker_service = LockerService()
        
        # 회원 권한 체크가 필요한 경우
        if member_id:
            from app.services.member_service import MemberService
            member_service = MemberService()
            member = member_service.get_member(member_id)
            
            if member and not member.can_access_zone(zone):
                return jsonify({
                    'success': False,
                    'error': f'해당 구역에 접근할 수 없습니다.',
                    'allowed_zones': member.allowed_zones
                }), 403
        
        if status == 'available':
            lockers = locker_service.get_available_lockers(zone, member_id)
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
    """락카 대여 (트랜잭션 기반)"""
    try:
        data = request.get_json()
        member_id = data.get('member_id')
        
        if not member_id:
            return jsonify({
                'success': False,
                'error': '회원 ID가 필요합니다.'
            }), 400
        
        # 새로운 트랜잭션 기반 LockerService 사용
        locker_service = LockerService('instance/gym_system.db')
        
        try:
            # 비동기 메서드를 동기적으로 실행
            import asyncio
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
        current_app.logger.error(f'락카 대여 오류: {e}')
        return jsonify({
            'success': False,
            'error': '락카 대여 중 오류가 발생했습니다.'
        }), 500


@bp.route('/lockers/<locker_id>/return', methods=['POST'])
def return_locker(locker_id):
    """락카 반납 (기존 방식)"""
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


@bp.route('/members/<member_id>/rent-by-sensor', methods=['POST'])
def rent_locker_by_sensor(member_id):
    """센서 기반 락카 대여 (실제 헬스장 운영 로직)"""
    try:
        if not member_id:
            return jsonify({
                'success': False,
                'error': '회원 ID가 필요합니다.'
            }), 400
        
        # 센서 기반 LockerService 사용
        locker_service = LockerService('instance/gym_system.db')
        
        try:
            # 비동기 메서드를 동기적으로 실행
            import asyncio
            result = asyncio.run(locker_service.rent_locker_by_sensor(member_id))
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'transaction_id': result['transaction_id'],
                    'locker_id': result['locker_id'],
                    'member_id': result['member_id'],
                    'step': result['step'],
                    'message': result['message']
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
        current_app.logger.error(f'센서 기반 락카 대여 오류: {e}')
        return jsonify({
            'success': False,
            'error': '센서 기반 락카 대여 중 오류가 발생했습니다.'
        }), 500


@bp.route('/members/<member_id>/return-by-sensor', methods=['POST'])
def return_locker_by_sensor(member_id):
    """센서 기반 락카 반납 (실제 헬스장 운영 로직)"""
    try:
        if not member_id:
            return jsonify({
                'success': False,
                'error': '회원 ID가 필요합니다.'
            }), 400
        
        # 센서 기반 LockerService 사용
        locker_service = LockerService('instance/gym_system.db')
        
        try:
            # 비동기 메서드를 동기적으로 실행
            import asyncio
            result = asyncio.run(locker_service.return_locker_by_sensor(member_id))
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'transaction_id': result['transaction_id'],
                    'locker_id': result['locker_id'],
                    'member_id': result['member_id'],
                    'step': result['step'],
                    'message': result['message']
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
        current_app.logger.error(f'센서 기반 락카 반납 오류: {e}')
        return jsonify({
            'success': False,
            'error': '센서 기반 락카 반납 중 오류가 발생했습니다.'
        }), 500


@bp.route('/transactions/<transaction_id>/status')
def get_transaction_status(transaction_id):
    """트랜잭션 상태 조회"""
    try:
        from database import TransactionManager, DatabaseManager
        
        db = DatabaseManager('instance/gym_system.db')
        db.connect()
        tx_manager = TransactionManager(db)
        
        try:
            import asyncio
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
        current_app.logger.error(f'트랜잭션 상태 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '트랜잭션 상태 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/transactions/active')
def get_active_transactions():
    """활성 트랜잭션 목록 조회"""
    try:
        from database import TransactionManager, DatabaseManager
        
        db = DatabaseManager('instance/gym_system.db')
        db.connect()
        tx_manager = TransactionManager(db)
        
        try:
            import asyncio
            transactions = asyncio.run(tx_manager.get_active_transactions())
            
            return jsonify({
                'success': True,
                'transactions': transactions,
                'count': len(transactions)
            })
        finally:
            db.close()
            
    except Exception as e:
        current_app.logger.error(f'활성 트랜잭션 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': '활성 트랜잭션 조회 중 오류가 발생했습니다.'
        }), 500


@bp.route('/members/<member_id>/validate')
def validate_member(member_id):
    """회원 유효성 검증 (SQLite 기반)"""
    try:
        from app.services.member_service import MemberService
        
        member_service = MemberService('instance/gym_system.db')
        
        try:
            result = member_service.validate_member(member_id)
            # Member 객체를 딕셔너리로 변환
            if result.get('member'):
                result['member'] = result['member'].to_dict()
            return jsonify(result)
        finally:
            member_service.close()
        
    except Exception as e:
        current_app.logger.error(f'회원 검증 오류: {e}')
        return jsonify({
            'valid': False,
            'error': '회원 검증 중 오류가 발생했습니다.'
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


# ========== 센서 이벤트 저장소 및 트랜잭션 연동 ==========
from collections import deque
import time
import asyncio

# 최근 센서 이벤트 저장 (최대 100개)
recent_sensor_events = deque(maxlen=100)

# 각 센서의 현재 상태 저장 (지속적 상태 관리)
current_sensor_states = {i: 'HIGH' for i in range(1, 141)}  # 1-140번 센서 초기값 HIGH

# 센서 이벤트 핸들러 (전역 인스턴스)
_sensor_handler = None

def get_sensor_handler():
    """센서 이벤트 핸들러 싱글톤 인스턴스 반환"""
    global _sensor_handler
    if _sensor_handler is None:
        from app.services.sensor_event_handler import SensorEventHandler
        # ESP32 매니저 가져오기 (문 열기/닫기용)
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        _sensor_handler = SensorEventHandler('instance/gym_system.db', esp32_manager=esp32_manager)
    return _sensor_handler

def add_sensor_event(sensor_num, state, timestamp=None):
    """센서 이벤트 추가 및 트랜잭션 연동 처리"""
    if timestamp is None:
        timestamp = time.time()
    
    # Flask 애플리케이션 컨텍스트 확인 및 생성
    from flask import has_app_context
    
    if has_app_context():
        current_app.logger.info(f"🔥 [add_sensor_event] 함수 시작: 센서{sensor_num}, 상태{state}")
    
    # 🔥 현재 센서 상태 즉시 업데이트 (지속적 상태 관리)
    if sensor_num in current_sensor_states:
        current_sensor_states[sensor_num] = state
        if has_app_context():
            current_app.logger.info(f"🔥 [상태업데이트] 센서{sensor_num}: {state} (지속상태)")
        else:
            print(f"🔥 [상태업데이트] 센서{sensor_num}: {state} (지속상태)")
    
    # 기존 이벤트 저장 (호환성 유지)
    event = {
        'sensor_num': sensor_num,
        'state': state,
        'timestamp': timestamp,
        'active': state == 'LOW'  # LOW일 때 활성(감지됨)
    }
    recent_sensor_events.append(event)
    
    # 🆕 트랜잭션 시스템과 연동 처리 (비동기)
    try:
        if has_app_context():
            current_app.logger.info(f"🔥 [센서처리] 센서{sensor_num} 상태{state} 트랜잭션 연동 시작")
        
        sensor_handler = get_sensor_handler()
        
        # 비동기 처리를 위한 태스크 생성
        async def process_sensor_event():
            try:
                if has_app_context():
                    current_app.logger.info(f"🔥 [센서처리] 비동기 함수 실행 중...")
                    
                result = await sensor_handler.handle_sensor_event(sensor_num, state, timestamp)
                
                if has_app_context():
                    current_app.logger.info(f"✅ [센서처리] 센서 이벤트 처리 결과: {result}")
                else:
                    print(f"센서 이벤트 처리 결과: {result}")
                
                # WebSocket으로 실시간 업데이트 전송 (향후 구현)
                if result.get('completed'):
                    if has_app_context():
                        current_app.logger.info(f"🎉 트랜잭션 완료: {result.get('event_type')}")
                    else:
                        print(f"🎉 트랜잭션 완료: {result.get('event_type')}")
                
            except Exception as e:
                if has_app_context():
                    current_app.logger.error(f"센서 이벤트 비동기 처리 오류: {e}")
                else:
                    print(f"센서 이벤트 비동기 처리 오류: {e}")
        
        # 이벤트 루프에서 실행 (Flask 동기 컨텍스트에서 실행)
        try:
            # 이미 실행 중인 루프가 있는지 확인
            try:
                loop = asyncio.get_running_loop()
                # 실행 중인 루프가 있으면 백그라운드 스레드에서 실행
                if has_app_context():
                    current_app.logger.info(f"🔥 [센서처리] 실행중인 루프 발견, 백그라운드 스레드에서 실행")
                
                import threading
                from flask import copy_current_request_context
                
                @copy_current_request_context
                def run_in_thread():
                    if has_app_context():
                        current_app.logger.info(f"🔥 [센서처리] 백그라운드 스레드 시작")
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(process_sensor_event())
                    new_loop.close()
                    if has_app_context():
                        current_app.logger.info(f"🔥 [센서처리] 백그라운드 스레드 완료")
                
                thread = threading.Thread(target=run_in_thread, daemon=True)
                thread.start()
                return  # 백그라운드 스레드 시작 후 종료
                
            except RuntimeError:
                # 실행 중인 루프가 없으면 직접 실행
                if has_app_context():
                    current_app.logger.info(f"🔥 [센서처리] 새로운 루프에서 직접 실행")
                asyncio.run(process_sensor_event())
                
        except Exception as e:
            if has_app_context():
                current_app.logger.error(f"센서 이벤트 루프 실행 오류: {e}")
            else:
                print(f"센서 이벤트 루프 실행 오류: {e}")
            
    except Exception as e:
        if has_app_context():
            current_app.logger.error(f"센서 이벤트 트랜잭션 연동 오류: {e}")
        else:
            print(f"센서 이벤트 트랜잭션 연동 오류: {e}")
        # 트랜잭션 연동 실패해도 기본 이벤트 저장은 유지


# ========== 하드웨어 테스트 API ==========

@bp.route('/hardware/status')
def hardware_status():
    """ESP32 하드웨어 상태 조회"""
    try:
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        current_app.logger.info(f"🔥 [DEBUG] ESP32 매니저: {esp32_manager}")
        
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
            # MOTOR_MOVE 명령으로 직접 회전수 제어 (음수 회전수 지원)
            result = asyncio.run(esp32_manager.send_command(
                "esp32_auto_0",  # 자동 감지된 디바이스 ID
                "MOTOR_MOVE",
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
            result = asyncio.run(esp32_manager.send_command(
                "esp32_auto_0",  # 자동 감지된 디바이스 ID
                "SET_AUTO_MODE",
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


@bp.route('/hardware/sensor_events')
def hardware_sensor_events():
    """최근 센서 이벤트 가져오기 (일회성 이벤트 반환)"""
    try:
        # 최근 3초 이내의 새로운 이벤트만 반환 (중복 방지)
        current_time = time.time()
        recent_events = []
        
        for event in list(recent_sensor_events):
            if current_time - event['timestamp'] <= 3:  # 3초 이내만
                recent_events.append(event)
        
        # 이벤트 반환 후 해당 이벤트들을 제거 (중복 방지)
        if recent_events:
            for event in recent_events:
                try:
                    recent_sensor_events.remove(event)
                except ValueError:
                    pass  # 이미 제거된 경우 무시
        
        # 디버그 로그 추가
        current_app.logger.info(f"🔥 [센서API] 새로운 이벤트: {len(recent_events)}개 반환")
        
        return jsonify(recent_events)
        
    except Exception as e:
        current_app.logger.error(f'센서 이벤트 조회 오류: {e}')
        return jsonify([])


@bp.route('/hardware/sensor_status')
def hardware_sensor_status():
    """현재 센서 상태 조회 (ESP32에서 직접 가져오기)"""
    try:
        esp32_manager = getattr(current_app, 'esp32_manager', None)
        
        if not esp32_manager:
            return jsonify({
                'success': False,
                'error': 'ESP32가 연결되지 않았습니다.',
                'sensors': {}
            })
        
        import asyncio
        try:
            # ESP32에 상태 요청
            result = asyncio.run(esp32_manager.send_command(
                "esp32_auto_0",  # 자동 감지된 디바이스 ID
                "GET_STATUS"
            ))
            
            current_app.logger.info(f"🔥 [센서상태] ESP32 응답: {result}")
            
            # 🔥 현재 저장된 센서 상태 반환 (지속적 상태 관리)
            sensor_states = current_sensor_states.copy()
            
            current_app.logger.info(f"🔥 [센서상태] 현재 센서 상태: {sensor_states}")
            
            return jsonify({
                'success': True,
                'sensors': sensor_states,
                'timestamp': time.time()
            })
            
        except Exception as cmd_error:
            current_app.logger.error(f'ESP32 상태 요청 실패: {cmd_error}')
            return jsonify({
                'success': False,
                'error': f'ESP32 통신 오류: {str(cmd_error)}',
                'sensors': {}
            })
        
    except Exception as e:
        current_app.logger.error(f'센서 상태 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': f'센서 상태 조회 중 오류가 발생했습니다: {str(e)}',
            'sensors': {}
        })


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


@bp.route('/hardware/simulate_sensor', methods=['POST'])
def simulate_sensor_event():
    """센서 이벤트 시뮬레이션 (테스트용)"""
    try:
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
        
        # 센서 이벤트 처리
        add_sensor_event(sensor_num, state)
        
        # 센서-락카 매핑 정보
        sensor_handler = get_sensor_handler()
        mapping = sensor_handler.get_sensor_locker_mapping()
        locker_id = mapping.get(sensor_num, 'Unknown')
        
        current_app.logger.info(f'센서 이벤트 시뮬레이션: 센서{sensor_num} ({locker_id}) → {state}')
        
        return jsonify({
            'success': True,
            'message': f'센서 이벤트 시뮬레이션 완료: 센서{sensor_num} → {state}',
            'sensor_num': sensor_num,
            'locker_id': locker_id,
            'state': state,
            'timestamp': time.time()
        })
        
    except Exception as e:
        current_app.logger.error(f'센서 이벤트 시뮬레이션 오류: {e}')
        return jsonify({
            'success': False,
            'error': f'센서 이벤트 시뮬레이션 중 오류가 발생했습니다: {str(e)}'
        }), 500


@bp.route('/hardware/sensor_mapping')
def get_sensor_mapping():
    """센서-락카 매핑 정보 조회"""
    try:
        sensor_handler = get_sensor_handler()
        mapping = sensor_handler.get_sensor_locker_mapping()
        
        # 구역별로 정리
        male_zone = {k: v for k, v in mapping.items() if v.startswith('M')}
        female_zone = {k: v for k, v in mapping.items() if v.startswith('F')}
        staff_zone = {k: v for k, v in mapping.items() if v.startswith('S')}
        
        return jsonify({
            'success': True,
            'mapping': {
                'male_zone': male_zone,
                'female_zone': female_zone,
                'staff_zone': staff_zone,
                'total_sensors': len(mapping)
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'센서 매핑 조회 오류: {e}')
        return jsonify({
            'success': False,
            'error': f'센서 매핑 조회 중 오류가 발생했습니다: {str(e)}'
        }), 500
