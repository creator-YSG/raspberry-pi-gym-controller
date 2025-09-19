"""
회원 관리 서비스
"""

from typing import Optional
from app.models.member import Member
from datetime import datetime, timedelta


class MemberService:
    """회원 관리 비즈니스 로직"""
    
    def __init__(self):
        self.google_sheets = None
        # TODO: 구글시트 매니저 초기화
    
    def get_member(self, member_id: str) -> Optional[Member]:
        """회원 정보 조회"""
        try:
            # TODO: 구글시트에서 실제 데이터 조회
            # 임시 테스트 데이터
            test_members = {
                '12345': Member(
                    id='12345',
                    name='홍길동',
                    phone='010-1234-5678',
                    membership_type='premium',
                    membership_expires=datetime.now() + timedelta(days=30),
                    status='active'
                ),
                '54321': Member(
                    id='54321', 
                    name='김철수',
                    phone='010-9876-5432',
                    membership_type='basic',
                    membership_expires=datetime.now() + timedelta(days=5),
                    status='active'
                ),
                'expired123': Member(
                    id='expired123',
                    name='이만료',
                    phone='010-0000-0000',
                    membership_type='basic',
                    membership_expires=datetime.now() - timedelta(days=5),
                    status='active'
                )
            }
            
            return test_members.get(member_id)
            
        except Exception as e:
            print(f"회원 조회 오류: {e}")
            return None
    
    def validate_member(self, member_id: str) -> dict:
        """회원 유효성 검증"""
        member = self.get_member(member_id)
        
        if not member:
            return {
                'valid': False,
                'error': '등록되지 않은 회원입니다.',
                'member': None
            }
        
        if not member.is_valid:
            if member.status != 'active':
                error = '정지된 회원입니다. 프론트에 문의하세요.'
            elif member.membership_expires and member.membership_expires < datetime.now():
                error = '회원권이 만료되었습니다. 연장 후 이용하세요.'
            else:
                error = '회원 상태를 확인할 수 없습니다.'
            
            return {
                'valid': False,
                'error': error,
                'member': member
            }
        
        return {
            'valid': True,
            'member': member,
            'message': f'안녕하세요, {member.name}님!'
        }
