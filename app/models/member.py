"""
회원 모델 (SQLite 연동 확장)
"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any


class Member:
    """회원 정보 (SQLite 연동)"""
    
    def __init__(self, id: str, name: str, phone: str = '',
                 membership_type: str = 'basic',
                 program_name: str = '',  # 가입 프로그램명
                 membership_expires: Optional[datetime] = None,
                 status: str = 'active',
                 # 🆕 새로 추가되는 필드들
                 currently_renting: Optional[str] = None,
                 daily_rental_count: int = 0,
                 last_rental_time: Optional[datetime] = None,
                 sync_date: Optional[datetime] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None,
                 # 🆕 락커 권한 관련 필드들
                 gender: str = 'male',  # male, female
                 member_category: str = 'general',  # general, staff
                 customer_type: str = '학부'):
        self.id = id  # 바코드 ID (member_id)
        self.name = name  # member_name
        self.phone = phone
        self.membership_type = membership_type  # basic, premium, vip
        self.program_name = program_name  # 가입 프로그램명 (예: 1.헬스1개월)
        self.membership_expires = membership_expires  # expiry_date
        self.status = status  # active, suspended, expired
        
        # 새로 추가된 필드들
        self.currently_renting = currently_renting  # 현재 대여중인 락카 번호
        self.daily_rental_count = daily_rental_count  # 오늘 대여 횟수
        self.last_rental_time = last_rental_time  # 마지막 대여 시각
        self.sync_date = sync_date  # 구글시트 동기화 시각
        self.created_at = created_at
        self.updated_at = updated_at
        
        # 락커 권한 관련 필드들
        self.gender = gender  # 성별 (male, female)
        self.member_category = member_category  # 회원 구분 (general, staff)
        self.customer_type = customer_type  # 고객구분 (학부, 대학교수, 대학직원, 기타 등)
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'member_id': self.id,  # 호환성을 위한 별칭
            'name': self.name,
            'member_name': self.name,  # 호환성을 위한 별칭
            'phone': self.phone,
            'membership_type': self.membership_type,
            'program_name': self.program_name,
            'membership_expires': self.membership_expires.isoformat() if self.membership_expires else None,
            'expiry_date': self.membership_expires.strftime('%Y-%m-%d') if self.membership_expires else None,  # 호환성
            'status': self.status,
            'currently_renting': self.currently_renting,
            'daily_rental_count': self.daily_rental_count,
            'last_rental_time': self.last_rental_time.isoformat() if self.last_rental_time else None,
            'sync_date': self.sync_date.isoformat() if self.sync_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'gender': self.gender,
            'member_category': self.member_category,
            'customer_type': self.customer_type,
            'is_valid': self.is_valid,
            'days_remaining': self.days_remaining,
            'is_renting': self.is_renting,
            'allowed_zones': self.allowed_zones
        }
    
    @property
    def member_id(self):
        """회원 ID (호환성을 위한 별칭)"""
        return self.id
    
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
    
    @property
    def is_renting(self):
        """현재 대여중인지 여부"""
        return self.currently_renting is not None
    
    @property
    def can_rent_more(self):
        """추가 대여 가능 여부"""
        max_daily_rentals = 3  # 기본값, 나중에 시스템 설정에서 가져올 수 있음
        return self.daily_rental_count < max_daily_rentals
    
    @property
    def allowed_zones(self):
        """접근 가능한 락커 구역 목록"""
        zones = []
        
        # 교직원은 성별 구역 + 교직원 구역 모두 접근 가능
        if self.member_category == 'staff':
            if self.gender == 'male':
                zones.extend(['MALE', 'STAFF'])
            else:  # female
                zones.extend(['FEMALE', 'STAFF'])
        else:
            # 일반 회원은 성별 구역만 접근 가능
            if self.gender == 'male':
                zones.append('MALE')
            else:  # female
                zones.append('FEMALE')
        
        return zones
    
    def can_access_zone(self, zone: str) -> bool:
        """특정 구역 접근 가능 여부"""
        return zone in self.allowed_zones
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> 'Member':
        """데이터베이스 행에서 Member 객체 생성
        
        Args:
            row: SQLite Row 객체
            
        Returns:
            Member 인스턴스
        """
        def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
            """날짜 문자열을 datetime 객체로 변환"""
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return None
        
        return cls(
            id=row['member_id'],
            name=row['member_name'],
            phone=row['phone'] if 'phone' in row.keys() and row['phone'] else '',
            membership_type=row['membership_type'] if 'membership_type' in row.keys() and row['membership_type'] else 'basic',
            program_name=row['program_name'] if 'program_name' in row.keys() and row['program_name'] else '',
            membership_expires=parse_datetime(row['expiry_date'] if 'expiry_date' in row.keys() else None),
            status=row['status'] if 'status' in row.keys() and row['status'] else 'active',
            currently_renting=row['currently_renting'] if 'currently_renting' in row.keys() else None,
            daily_rental_count=row['daily_rental_count'] if 'daily_rental_count' in row.keys() and row['daily_rental_count'] else 0,
            last_rental_time=parse_datetime(row['last_rental_time'] if 'last_rental_time' in row.keys() else None),
            sync_date=parse_datetime(row['sync_date'] if 'sync_date' in row.keys() else None),
            created_at=parse_datetime(row['created_at'] if 'created_at' in row.keys() else None),
            updated_at=parse_datetime(row['updated_at'] if 'updated_at' in row.keys() else None),
            gender=row['gender'] if 'gender' in row.keys() and row['gender'] else 'male',
            member_category=row['member_category'] if 'member_category' in row.keys() and row['member_category'] else 'general',
            customer_type=row['customer_type'] if 'customer_type' in row.keys() and row['customer_type'] else '학부'
        )
    
    def to_db_dict(self) -> Dict[str, Any]:
        """데이터베이스 저장용 딕셔너리 변환
        
        Returns:
            데이터베이스 컬럼명과 값의 딕셔너리
        """
        def format_datetime(dt: Optional[datetime]) -> Optional[str]:
            """datetime을 ISO 형식 문자열로 변환"""
            return dt.isoformat() if dt else None
        
        return {
            'member_id': self.id,
            'member_name': self.name,
            'phone': self.phone,
            'membership_type': self.membership_type,
            'program_name': self.program_name,
            'expiry_date': format_datetime(self.membership_expires),
            'status': self.status,
            'currently_renting': self.currently_renting,
            'daily_rental_count': self.daily_rental_count,
            'last_rental_time': format_datetime(self.last_rental_time),
            'sync_date': format_datetime(self.sync_date),
            'created_at': format_datetime(self.created_at),
            'updated_at': format_datetime(self.updated_at),
            'gender': self.gender,
            'member_category': self.member_category,
            'customer_type': self.customer_type
        }
    
    def start_rental(self, locker_number: str):
        """대여 시작 처리
        
        Args:
            locker_number: 대여할 락카 번호
        """
        self.currently_renting = locker_number
        self.last_rental_time = datetime.now()
        self.daily_rental_count += 1
    
    def end_rental(self):
        """대여 종료 처리"""
        self.currently_renting = None
    
    def reset_daily_count(self):
        """일일 대여 횟수 초기화 (자정에 실행)"""
        self.daily_rental_count = 0
    
    def __repr__(self):
        return f"<Member {self.id} ({self.name}) - {self.status}>"
