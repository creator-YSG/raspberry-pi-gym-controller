"""
회원 모델
"""

from datetime import datetime
from typing import Optional


class Member:
    """회원 정보"""
    
    def __init__(self, id: str, name: str, phone: str = '',
                 membership_type: str = 'basic', 
                 membership_expires: Optional[datetime] = None,
                 status: str = 'active'):
        self.id = id  # 바코드 ID
        self.name = name
        self.phone = phone
        self.membership_type = membership_type  # basic, premium, vip
        self.membership_expires = membership_expires
        self.status = status  # active, suspended, expired
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'membership_type': self.membership_type,
            'membership_expires': self.membership_expires.isoformat() if self.membership_expires else None,
            'status': self.status,
            'is_valid': self.is_valid,
            'days_remaining': self.days_remaining
        }
    
    @property
    def is_valid(self):
        """유효한 회원 여부"""
        if self.status != 'active':
            return False
        
        if self.membership_expires:
            return self.membership_expires > datetime.now()
        
        return True
    
    @property
    def days_remaining(self):
        """남은 일수"""
        if not self.membership_expires:
            return None
        
        delta = self.membership_expires - datetime.now()
        return max(0, delta.days)
    
    def __repr__(self):
        return f"<Member {self.id} ({self.name})>"
