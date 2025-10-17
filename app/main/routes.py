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
            
            # 만료일 정보 추가 (이미 to_dict()에 포함되지만 is_expired는 추가 필요)
            from datetime import datetime
            if member.membership_expires:
                days_remaining = (member.membership_expires - datetime.now()).days
                member_dict['is_expired'] = days_remaining < 0
            
            # 접근 가능한 구역 확인 (allowed_zones는 이미 포함됨, zone은 기본값만)
            zone = member.allowed_zones[0] if member.allowed_zones else 'MALE'
            member_dict['zone'] = zone
            
            return render_template('pages/member_check.html',
                                 title='회원 확인',
                                 member=member_dict,
                                 action=action,
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


