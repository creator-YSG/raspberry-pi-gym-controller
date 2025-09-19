"""
대여 기록 모델
"""

from datetime import datetime
from typing import Optional


class Rental:
    """대여 기록"""
    
    def __init__(self, id: str, locker_id: str, member_id: str,
                 rented_at: datetime, returned_at: Optional[datetime] = None,
                 status: str = 'active'):
        self.id = id
        self.locker_id = locker_id
        self.member_id = member_id
        self.rented_at = rented_at
        self.returned_at = returned_at
        self.status = status  # active, returned, expired
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'locker_id': self.locker_id,
            'member_id': self.member_id,
            'rented_at': self.rented_at.isoformat() if self.rented_at else None,
            'returned_at': self.returned_at.isoformat() if self.returned_at else None,
            'status': self.status,
            'duration_minutes': self.duration_minutes,
            'is_active': self.is_active
        }
    
    @property
    def duration_minutes(self):
        """대여 지속 시간 (분)"""
        if self.returned_at:
            delta = self.returned_at - self.rented_at
        else:
            delta = datetime.now() - self.rented_at
        
        return int(delta.total_seconds() / 60)
    
    @property
    def is_active(self):
        """활성 대여 여부"""
        return self.status == 'active' and self.returned_at is None
    
    def __repr__(self):
        return f"<Rental {self.id} ({self.locker_id} -> {self.member_id})>"
