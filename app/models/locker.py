"""
락카 모델
"""

from datetime import datetime
from typing import Optional


class Locker:
    """락카 정보"""
    
    def __init__(self, id: str, zone: str, number: int, 
                 status: str = 'available', size: str = 'medium',
                 rented_at: Optional[datetime] = None, 
                 rented_by: Optional[str] = None):
        self.id = id  # A01, B15 등
        self.zone = zone  # A, B
        self.number = number  # 1-24
        self.status = status  # available, occupied, maintenance
        self.size = size  # small, medium, large
        self.rented_at = rented_at
        self.rented_by = rented_by
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'zone': self.zone,
            'number': self.number,
            'status': self.status,
            'size': self.size,
            'rented_at': self.rented_at.isoformat() if self.rented_at else None,
            'rented_by': self.rented_by,
            'display_name': f'{self.zone}-{self.number:02d}',
            'is_available': self.status == 'available'
        }
    
    @property
    def display_name(self):
        """화면 표시용 이름"""
        return f'{self.zone}-{self.number:02d}'
    
    @property
    def is_available(self):
        """사용 가능 여부"""
        return self.status == 'available'
    
    def __repr__(self):
        return f"<Locker {self.id} ({self.status})>"
