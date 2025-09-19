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
    
    if member_id:
        member_service = MemberService()
        member = member_service.get_member(member_id)
        
        if member:
            return render_template('pages/member_check.html',
                                 title='회원 확인',
                                 member=member,
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
    zone = request.args.get('zone', 'A')  # A, B 구역
    
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
    member_id = request.args.get('member_id', '')
    
    return render_template('pages/rental_complete.html',
                         title='대여 완료',
                         locker_id=locker_id,
                         member_id=member_id,
                         page_class='success-page')


@bp.route('/return-complete')
def return_complete():
    """반납 완료 화면"""
    locker_id = request.args.get('locker_id', '')
    
    return render_template('pages/return_complete.html',
                         title='반납 완료',
                         locker_id=locker_id,
                         page_class='success-page')


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
    error_message = request.args.get('message', '알 수 없는 오류가 발생했습니다.')
    
    return render_template('pages/error.html',
                         title='오류',
                         error_type=error_type,
                         error_message=error_message,
                         page_class='error-page')
