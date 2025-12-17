"""
메인 페이지 라우트
"""

from flask import render_template, current_app, request
from app.main import bp
from app.services.locker_service import LockerService
from app.services.member_service import MemberService


@bp.route('/')
@bp.route('/index')
def index():
    """홈 화면 - 바코드 스캔 대기"""
    return render_template('pages/home.html', 
                         title='락카키 대여기',
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
                    locker_service.db.execute_query("""
                        INSERT INTO rentals (
                            transaction_id, member_id, locker_number, status,
                            rental_barcode_time, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (transaction_id, member_id, 'PENDING', 'pending', 
                          rental_time, rental_time, rental_time))
                    
                    locker_service.db.conn.commit()
                    
                    current_app.logger.info(f'📝 Pending 대여 레코드 생성: member={member_id}, transaction={transaction_id}')
                except Exception as e:
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
    return render_template('pages/face_auth.html',
                         title='얼굴 인증',
                         page_class='face-auth-page')


