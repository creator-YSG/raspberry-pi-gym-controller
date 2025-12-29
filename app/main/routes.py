"""
메인 페이지 라우트
"""

from flask import render_template, current_app, request, jsonify
from app.main import bp
from app.services.locker_service import LockerService
from app.services.member_service import MemberService


def get_gym_name() -> str:
    """DB에서 헬스장 이름 가져오기"""
    try:
        from database.database_manager import DatabaseManager
        db = DatabaseManager('instance/gym_system.db')
        db.connect()
        cursor = db.execute_query(
            "SELECT setting_value FROM system_settings WHERE setting_key = 'gym_name'"
        )
        result = cursor.fetchone() if cursor else None
        db.close()
        return result[0] if result else '헬스장'
    except Exception as e:
        current_app.logger.warning(f"헬스장 이름 조회 실패: {e}")
        return '헬스장'


def get_admin_password() -> str:
    """DB에서 관리자 비밀번호 가져오기"""
    try:
        from database.database_manager import DatabaseManager
        db = DatabaseManager('instance/gym_system.db')
        db.connect()
        cursor = db.execute_query(
            "SELECT setting_value FROM system_settings WHERE setting_key = 'admin_password'"
        )
        result = cursor.fetchone() if cursor else None
        db.close()
        return result[0] if result else '1234'
    except Exception as e:
        current_app.logger.warning(f"관리자 비밀번호 조회 실패: {e}")
        return '1234'


@bp.route('/')
@bp.route('/index')
def index():
    """홈 화면 - 바코드 스캔 대기"""
    gym_name = get_gym_name()
    return render_template('pages/home.html', 
                         title='락카키 대여기',
                         gym_name=gym_name,
                         page_class='home-page')


@bp.route('/member-check')
def member_check():
    """회원 확인 화면"""
    member_id = request.args.get('member_id', '')
    action = request.args.get('action', 'rental')  # 'rental' or 'return'
    auth_method = request.args.get('auth_method', 'barcode')  # 인증 방법
    
    if member_id:
        member_service = MemberService()
        member = member_service.get_member(member_id)
        
        if member:
            # 트랜잭션 시작 (센서 이벤트 핸들러가 감지할 수 있도록)
            from app.services.locker_service import LockerService
            from database.transaction_manager import TransactionType
            import asyncio
            
            locker_service = LockerService()
            tx_type = TransactionType.RENTAL if action == 'rental' else TransactionType.RETURN
            
            try:
                # 트랜잭션 시작
                tx_result = asyncio.run(locker_service.tx_manager.start_transaction(member_id, tx_type))
                if tx_result['success']:
                    current_app.logger.info(f"✅ 트랜잭션 시작: {tx_result['transaction_id']} ({action})")
                else:
                    current_app.logger.warning(f"⚠️ 트랜잭션 시작 실패: {tx_result.get('error')}")
            except Exception as e:
                current_app.logger.error(f"❌ 트랜잭션 시작 오류: {e}")
            
            # 회원 데이터를 딕셔너리로 변환 (to_dict()에 모든 정보 포함됨)
            member_dict = member.to_dict()
            
            # 만료일 정보 추가 및 강제 계산
            from datetime import datetime
            if member.membership_expires:
                days_remaining = (member.membership_expires - datetime.now()).days
                member_dict['is_expired'] = days_remaining < 0
                member_dict['days_remaining'] = max(0, days_remaining)  # 강제 설정
                member_dict['expiry_date'] = member.membership_expires.strftime('%Y-%m-%d')  # 강제 설정
                current_app.logger.info(f"📅 만료일: {member_dict['expiry_date']}, 남은 기간: {member_dict['days_remaining']}일")
            else:
                member_dict['days_remaining'] = None
                member_dict['expiry_date'] = None
                current_app.logger.warning(f"⚠️ 회원 {member.id}의 만료일 정보 없음")
            
            # 접근 가능한 구역 확인 (교직원은 STAFF 우선)
            if member.member_category == 'staff' and 'STAFF' in member.allowed_zones:
                zone = 'STAFF'
            else:
                zone = member.allowed_zones[0] if member.allowed_zones else 'MALE'
            member_dict['zone'] = zone
            
            # 🆕 대여 프로세스인 경우: 바코드 인증 시점에 pending 레코드 생성
            if action == 'rental':
                try:
                    import uuid
                    transaction_id = str(uuid.uuid4())
                    rental_time = datetime.now().isoformat()

                    # pending 상태로 대여 레코드 INSERT (락커 번호는 아직 모름)
                    cursor = locker_service.db.execute_query("""
                        INSERT INTO rentals (
                            transaction_id, member_id, locker_number, status,
                            rental_barcode_time, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (transaction_id, member_id, 'PENDING', 'pending',
                          rental_time, rental_time, rental_time))

                    if cursor is None:
                        current_app.logger.error(f'❌ Pending 레코드 INSERT 실패: member={member_id}, cursor=None')
                        raise Exception("INSERT 쿼리 실패 (cursor=None)")

                    rental_id = cursor.lastrowid
                    locker_service.db.conn.commit()

                    # INSERT 성공 확인 (실제로 저장되었는지 검증)
                    verify_cursor = locker_service.db.execute_query(
                        "SELECT rental_id FROM rentals WHERE transaction_id = ?",
                        (transaction_id,)
                    )
                    verified = verify_cursor.fetchone() if verify_cursor else None
                    if verified:
                        current_app.logger.info(f'✅ Pending 대여 레코드 생성 완료: member={member_id}, rental_id={rental_id}, verified={verified[0]}')
                    else:
                        current_app.logger.error(f'⚠️ Pending 레코드 생성됨 but 검증 실패: member={member_id}, rental_id={rental_id}')

                    # 🆕 구글 시트 즉시 동기화 (대여 pending 생성 시)
                    current_app.logger.info(f'📊 시트 동기화 시작: member_dict 존재={member_dict is not None}, rental_id={rental_id}')
                    if member_dict:
                        current_app.logger.info(f'📊 member_dict 내용: {member_dict.keys()}')
                    else:
                        current_app.logger.warning(f'📊 member_dict가 None입니다!')

                    from app.services.sheets_sync import SheetsSync
                    sheets_sync = SheetsSync()
                    current_app.logger.info(f'📊 SheetsSync 객체 생성 완료')

                    # 회원 이름 가져오기
                    member_name = member_dict.get('member_name', '') if member_dict else ''
                    current_app.logger.info(f'📊 member_name 추출: "{member_name}"')

                    # 🚀 구글 시트 업로드 - 백그라운드 처리
                    import threading
                    
                    def async_sheet_upload():
                        try:
                            current_app.logger.info(f'📊 백그라운드 append_rental_record 시작')
                            result = sheets_sync.append_rental_record(
                                rental_id=rental_id,
                                member_id=member_id,
                                member_name=member_name,
                                locker_number='PENDING',
                                auth_method=auth_method,
                                auth_time=rental_time,
                                sensor_time='',  # 아직 센서 감지 안 됨
                                status='pending',
                                photo_url=''
                            )
                            if result:
                                current_app.logger.info(f'📊 백그라운드 구글시트 대여 기록 추가 성공 (pending): rental_id={rental_id}')
                            else:
                                current_app.logger.warning(f'📊 백그라운드 구글시트 대여 기록 추가 실패 (pending): rental_id={rental_id}')
                        except Exception as e:
                            current_app.logger.error(f'📊 백그라운드 시트 업로드 오류: {e}')
                    
                    # 백그라운드 스레드로 실행
                    threading.Thread(target=async_sheet_upload, daemon=True).start()
                    current_app.logger.info(f'📊 구글시트 업로드 백그라운드 실행 시작: rental_id={rental_id}')

                    # 🆕 인증 사진 촬영 (pending rental 생성 직후)
                    try:
                        from app.api.routes import _capture_auth_photo
                        _capture_auth_photo(member_id, auth_method)
                        current_app.logger.info(f'📸 인증 사진 촬영 요청: member={member_id}, method={auth_method}')
                    except Exception as photo_error:
                        current_app.logger.warning(f'📸 인증 사진 촬영 실패 (무시): {photo_error}')
                        
                except Exception as e:
                    current_app.logger.error(f'❌ 대여 프로세스 오류: {e}', exc_info=True)
                    current_app.logger.error(f'❌ Pending 레코드 생성 오류: {e}', exc_info=True)
            
            # 🆕 반납 프로세스인 경우: 바코드 인증 시점에 return_barcode_time 기록
            elif action == 'return':
                try:
                    return_barcode_time = datetime.now().isoformat()
                    
                    # 현재 대여 중인 락커 번호 조회
                    cursor = locker_service.db.execute_query("""
                        SELECT locker_number 
                        FROM rentals 
                        WHERE member_id = ? AND status = 'active'
                        ORDER BY rental_barcode_time DESC 
                        LIMIT 1
                    """, (member_id,))
                    
                    current_rental = None
                    if cursor:
                        current_rental = cursor.fetchone()
                    
                    if current_rental:
                        member_dict['current_locker'] = current_rental[0]
                        current_app.logger.info(f'🔍 현재 대여 중인 락커: {current_rental[0]}')
                    else:
                        member_dict['current_locker'] = None
                        current_app.logger.warning(f'⚠️ 회원 {member_id}의 대여 기록 없음')
                    
                    # 활성 대여 레코드에 return_barcode_time 업데이트
                    locker_service.db.execute_query("""
                        UPDATE rentals 
                        SET return_barcode_time = ?, updated_at = ?
                        WHERE member_id = ? AND status = 'active'
                    """, (return_barcode_time, return_barcode_time, member_id))
                    
                    locker_service.db.conn.commit()
                    
                    current_app.logger.info(f'📝 반납 바코드 시간 기록: member={member_id}, time={return_barcode_time}')
                    
                    # 구글 시트 동기화는 반납 완료 시에 한 번에 기록 (새 구조)
                    
                    # 🆕 인증 사진 촬영 (반납 시에도)
                    try:
                        from app.api.routes import _capture_auth_photo
                        _capture_auth_photo(member_id, auth_method)
                        current_app.logger.info(f'📸 반납 인증 사진 촬영 요청: member={member_id}, method={auth_method}')
                    except Exception as photo_error:
                        current_app.logger.warning(f'📸 반납 인증 사진 촬영 실패 (무시): {photo_error}')
                        
                except Exception as e:
                    current_app.logger.error(f'❌ 반납 바코드 시간 기록 오류: {e}', exc_info=True)
            
            return render_template('pages/member_check.html',
                                 title='회원 확인',
                                 member=member_dict,
                                 action=action,
                                 auth_method=auth_method,
                                 page_class='member-check-page')
    
    # 회원 정보 없음
    return render_template('pages/member_not_found.html',
                         title='회원 없음',
                         member_id=member_id,
                         page_class='error-page')


@bp.route('/locker-select')
def locker_select():
    """락카 선택 화면"""
    member_id = request.args.get('member_id', '')
    zone = request.args.get('zone', 'MALE')  # MALE, FEMALE, STAFF 구역
    
    locker_service = LockerService()
    available_lockers = locker_service.get_available_lockers(zone)
    
    return render_template('pages/locker_select.html',
                         title=f'{zone}구역 락카 선택',
                         member_id=member_id,
                         zone=zone,
                         lockers=available_lockers,
                         page_class='locker-select-page')


@bp.route('/rental-complete')
def rental_complete():
    """대여 완료 화면"""
    locker_id = request.args.get('locker_id', '')
    
    return render_template('pages/rental_complete.html',
                         title='대여 완료',
                         locker_id=locker_id,
                         page_class='complete-page')


@bp.route('/return-complete')
def return_complete():
    """반납 완료 화면"""
    locker_id = request.args.get('locker_id', '')
    
    return render_template('pages/return_complete.html',
                         title='반납 완료',
                         locker_id=locker_id,
                         page_class='complete-page')


@bp.route('/admin')
def admin():
    """관리자 화면"""
    from app.services.system_service import SystemService
    
    system_service = SystemService()
    system_status = system_service.get_system_status()
    
    return render_template('pages/admin.html',
                         title='관리자 화면',
                         system_status=system_status,
                         page_class='admin-page')


@bp.route('/error')
def error():
    """에러 화면"""
    error_type = request.args.get('type', 'unknown')
    error_message = request.args.get('message', '')
    
    return render_template('pages/error.html',
                         title='오류',
                         error_type=error_type,
                         error_message=error_message,
                         page_class='error-page')


@bp.route('/face-auth')
def face_auth():
    """얼굴 인증 화면 - 카메라 영상 표시 및 자동 인증"""
    gym_name = get_gym_name()
    return render_template('pages/face_auth.html',
                         title='얼굴 인증',
                         gym_name=gym_name,
                         page_class='face-auth-page')


# ========== 설정 메뉴 라우트 ==========

@bp.route('/settings')
def settings():
    """설정 메뉴 화면"""
    return render_template('pages/settings.html',
                         title='설정',
                         page_class='settings-page')


@bp.route('/settings/face-register')
def settings_face_register():
    """얼굴인식 등록 화면"""
    return render_template('pages/settings_face_register.html',
                         title='얼굴인식 등록',
                         page_class='settings-page')


@bp.route('/settings/sensor-mapping')
def settings_sensor_mapping():
    """센서 매핑 점검 화면"""
    return render_template('pages/settings_sensor_mapping.html',
                         title='센서 매핑 점검',
                         page_class='settings-page')


@bp.route('/settings/nfc-register')
def settings_nfc_register():
    """NFC 태그 등록 화면"""
    return render_template('pages/settings_nfc_register.html',
                         title='NFC 태그 등록',
                         page_class='settings-page')


@bp.route('/settings/sheets-sync')
def settings_sheets_sync():
    """구글시트 즉시 동기화 화면"""
    return render_template('pages/settings_sheets_sync.html',
                         title='구글시트 동기화',
                         page_class='settings-page')


# ========== 비밀번호 검증 API ==========

@bp.route('/api/verify-admin-password', methods=['POST'])
def verify_admin_password():
    """관리자 비밀번호 검증 API (5회 터치 후 호출)"""
    data = request.get_json()
    password = data.get('password', '') if data else ''
    
    correct_password = get_admin_password()
    
    if password == correct_password:
        current_app.logger.info("✅ 관리자 비밀번호 인증 성공")
        return jsonify({'success': True, 'redirect': '/settings'})
    else:
        current_app.logger.warning(f"❌ 관리자 비밀번호 인증 실패: 입력값={password}")
        return jsonify({'success': False, 'message': '비밀번호가 틀렸습니다.'})

