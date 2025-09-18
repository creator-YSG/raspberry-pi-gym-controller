"""
구글시트 API 연동 모듈

헬스장 회원 명단, 락카키 대여 기록 등을 구글시트에서 관리
WiFi를 통해 구글시트와 실시간 동기화
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    print("[GSPREAD] gspread not available, using stub mode")

logger = logging.getLogger(__name__)


@dataclass
class MemberInfo:
    """회원 정보"""
    member_id: str
    name: str
    phone: str
    membership_type: str
    expiry_date: str
    is_active: bool
    barcode: str


@dataclass
class LockerInfo:
    """락카 정보"""
    locker_id: str
    section: str  # A, B, C 등
    is_available: bool
    current_user: Optional[str] = None
    rental_start: Optional[datetime] = None
    rental_end: Optional[datetime] = None


@dataclass
class RentalRecord:
    """대여 기록"""
    record_id: str
    member_id: str
    member_name: str
    locker_id: str
    key_barcode: str
    rental_time: datetime
    return_time: Optional[datetime] = None
    is_returned: bool = False


class GoogleSheetsManager:
    """구글시트 연동 매니저"""
    
    def __init__(self, credentials_file: str, spreadsheet_id: str):
        """
        Args:
            credentials_file: 구글 서비스 계정 JSON 파일 경로
            spreadsheet_file: 구글시트 ID
        """
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        
        self.client: Optional['gspread.Client'] = None
        self.spreadsheet: Optional['gspread.Spreadsheet'] = None
        
        # 워크시트 이름들
        self.sheets = {
            "members": "회원명단",
            "lockers": "락카정보", 
            "rentals": "대여기록",
            "keys": "락카키목록"
        }
        
        # 캐시된 데이터
        self._members_cache: Dict[str, MemberInfo] = {}
        self._lockers_cache: Dict[str, LockerInfo] = {}
        self._last_sync: Optional[datetime] = None
        self._cache_timeout = 300  # 5분
        
        logger.info("GoogleSheetsManager 초기화")
    
    async def connect(self) -> bool:
        """구글시트에 연결
        
        Returns:
            연결 성공 여부
        """
        if not GSPREAD_AVAILABLE:
            logger.warning("gspread 없음, 스텁 모드로 실행")
            return True
        
        try:
            # 서비스 계정 인증
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                self.credentials_file, scopes=scope
            )
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            logger.info(f"구글시트 연결 성공: {self.spreadsheet.title}")
            
            # 초기 데이터 로드
            await self._load_initial_data()
            
            return True
            
        except FileNotFoundError:
            logger.error(f"인증 파일 없음: {self.credentials_file}")
            return False
        except Exception as e:
            logger.error(f"구글시트 연결 실패: {e}")
            return False
    
    async def _load_initial_data(self):
        """초기 데이터 로드"""
        await asyncio.gather(
            self._load_members(),
            self._load_lockers(),
            return_exceptions=True
        )
        self._last_sync = datetime.now(timezone.utc)
        logger.info("구글시트 초기 데이터 로드 완료")
    
    async def _load_members(self):
        """회원 명단 로드"""
        if not self.spreadsheet:
            return
        
        try:
            worksheet = self.spreadsheet.worksheet(self.sheets["members"])
            records = worksheet.get_all_records()
            
            self._members_cache.clear()
            
            for record in records:
                if record.get("바코드") and record.get("회원ID"):
                    member = MemberInfo(
                        member_id=str(record.get("회원ID", "")),
                        name=str(record.get("이름", "")),
                        phone=str(record.get("전화번호", "")),
                        membership_type=str(record.get("회원권종류", "")),
                        expiry_date=str(record.get("만료일", "")),
                        is_active=str(record.get("활성화", "")).upper() in ["Y", "TRUE", "1"],
                        barcode=str(record.get("바코드", ""))
                    )
                    
                    # 바코드와 회원ID 모두로 접근 가능하게 저장
                    self._members_cache[member.barcode] = member
                    self._members_cache[member.member_id] = member
            
            logger.info(f"회원 데이터 로드: {len(records)}명")
            
        except Exception as e:
            logger.error(f"회원 데이터 로드 실패: {e}")
    
    async def _load_lockers(self):
        """락카 정보 로드"""
        if not self.spreadsheet:
            return
        
        try:
            worksheet = self.spreadsheet.worksheet(self.sheets["lockers"])
            records = worksheet.get_all_records()
            
            self._lockers_cache.clear()
            
            for record in records:
                if record.get("락카번호"):
                    locker = LockerInfo(
                        locker_id=str(record.get("락카번호", "")),
                        section=str(record.get("구역", "")),
                        is_available=str(record.get("사용가능", "")).upper() in ["Y", "TRUE", "1"],
                        current_user=record.get("현재사용자") or None,
                        rental_start=self._parse_datetime(record.get("대여시작")),
                        rental_end=self._parse_datetime(record.get("대여종료"))
                    )
                    
                    self._lockers_cache[locker.locker_id] = locker
            
            logger.info(f"락카 데이터 로드: {len(records)}개")
            
        except Exception as e:
            logger.error(f"락카 데이터 로드 실패: {e}")
    
    def _parse_datetime(self, date_str: Any) -> Optional[datetime]:
        """날짜 문자열 파싱"""
        if not date_str or date_str == "":
            return None
        
        try:
            # 여러 날짜 형식 지원
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(str(date_str), fmt)
                except ValueError:
                    continue
            
            logger.warning(f"날짜 파싱 실패: {date_str}")
            return None
            
        except Exception as e:
            logger.error(f"날짜 파싱 오류: {date_str}, {e}")
            return None
    
    async def validate_member(self, barcode: str) -> Optional[MemberInfo]:
        """회원 바코드 유효성 검증
        
        Args:
            barcode: 회원 바코드
            
        Returns:
            회원 정보 또는 None
        """
        # 캐시 확인
        if await self._should_refresh_cache():
            await self._load_members()
        
        member = self._members_cache.get(barcode)
        
        if member and member.is_active:
            # 만료일 확인
            if member.expiry_date:
                try:
                    expiry = datetime.strptime(member.expiry_date, "%Y-%m-%d")
                    if expiry < datetime.now():
                        logger.warning(f"만료된 회원: {member.member_id}")
                        return None
                except ValueError:
                    logger.warning(f"만료일 형식 오류: {member.expiry_date}")
            
            logger.info(f"유효한 회원: {member.name} ({member.member_id})")
            return member
        
        logger.warning(f"유효하지 않은 회원 바코드: {barcode}")
        return None
    
    async def get_available_lockers(self) -> List[LockerInfo]:
        """사용 가능한 락카 목록 조회
        
        Returns:
            사용 가능한 락카 목록
        """
        if await self._should_refresh_cache():
            await self._load_lockers()
        
        available_lockers = [
            locker for locker in self._lockers_cache.values()
            if locker.is_available and not locker.current_user
        ]
        
        # 구역별로 정렬
        available_lockers.sort(key=lambda x: (x.section, x.locker_id))
        
        logger.info(f"사용 가능한 락카: {len(available_lockers)}개")
        return available_lockers
    
    async def record_rental(self, member_id: str, locker_id: str, key_barcode: str) -> bool:
        """락카키 대여 기록
        
        Args:
            member_id: 회원 ID
            locker_id: 락카 번호
            key_barcode: 락카키 바코드
            
        Returns:
            기록 성공 여부
        """
        if not self.spreadsheet:
            logger.error("구글시트 연결되지 않음")
            return False
        
        try:
            # 대여 기록 추가
            rental_worksheet = self.spreadsheet.worksheet(self.sheets["rentals"])
            
            member = self._members_cache.get(member_id)
            member_name = member.name if member else "알 수 없음"
            
            now = datetime.now(timezone.utc)
            record_id = f"R{now.strftime('%Y%m%d%H%M%S')}"
            
            rental_data = [
                record_id,
                member_id,
                member_name,
                locker_id,
                key_barcode,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                "",  # 반납시간 (빈 값)
                "N"  # 반납여부
            ]
            
            rental_worksheet.append_row(rental_data)
            
            # 락카 상태 업데이트
            await self._update_locker_status(locker_id, member_id, now)
            
            logger.info(f"대여 기록 완료: {member_name} -> {locker_id}")
            return True
            
        except Exception as e:
            logger.error(f"대여 기록 실패: {e}")
            return False
    
    async def _update_locker_status(self, locker_id: str, member_id: str, rental_time: datetime):
        """락카 상태 업데이트"""
        try:
            locker_worksheet = self.spreadsheet.worksheet(self.sheets["lockers"])
            records = locker_worksheet.get_all_records()
            
            for i, record in enumerate(records, start=2):  # 2행부터 시작
                if str(record.get("락카번호")) == locker_id:
                    # 현재 사용자와 대여 시간 업데이트
                    locker_worksheet.update(f"D{i}", member_id)  # 현재사용자
                    locker_worksheet.update(f"E{i}", rental_time.strftime("%Y-%m-%d %H:%M:%S"))  # 대여시작
                    locker_worksheet.update(f"C{i}", "N")  # 사용가능 = N
                    break
            
            # 캐시 업데이트
            if locker_id in self._lockers_cache:
                self._lockers_cache[locker_id].current_user = member_id
                self._lockers_cache[locker_id].rental_start = rental_time
                self._lockers_cache[locker_id].is_available = False
                
        except Exception as e:
            logger.error(f"락카 상태 업데이트 실패: {e}")
    
    async def process_return(self, key_barcode: str) -> Optional[RentalRecord]:
        """락카키 반납 처리
        
        Args:
            key_barcode: 락카키 바코드
            
        Returns:
            반납 처리된 대여 기록 또는 None
        """
        if not self.spreadsheet:
            logger.error("구글시트 연결되지 않음")
            return None
        
        try:
            # 대여 기록에서 해당 키 찾기
            rental_worksheet = self.spreadsheet.worksheet(self.sheets["rentals"])
            records = rental_worksheet.get_all_records()
            
            for i, record in enumerate(records, start=2):  # 2행부터 시작
                if (str(record.get("락카키바코드")) == key_barcode and 
                    str(record.get("반납여부")).upper() != "Y"):
                    
                    # 반납 처리
                    return_time = datetime.now(timezone.utc)
                    rental_worksheet.update(f"G{i}", return_time.strftime("%Y-%m-%d %H:%M:%S"))  # 반납시간
                    rental_worksheet.update(f"H{i}", "Y")  # 반납여부
                    
                    # 락카 상태 복구
                    locker_id = str(record.get("락카번호"))
                    await self._release_locker(locker_id)
                    
                    # 반납 기록 생성
                    rental_record = RentalRecord(
                        record_id=str(record.get("기록ID")),
                        member_id=str(record.get("회원ID")),
                        member_name=str(record.get("회원이름")),
                        locker_id=locker_id,
                        key_barcode=key_barcode,
                        rental_time=self._parse_datetime(record.get("대여시간")),
                        return_time=return_time,
                        is_returned=True
                    )
                    
                    logger.info(f"반납 처리 완료: {rental_record.member_name} -> {locker_id}")
                    return rental_record
            
            logger.warning(f"해당 락카키 대여 기록 없음: {key_barcode}")
            return None
            
        except Exception as e:
            logger.error(f"반납 처리 실패: {e}")
            return None
    
    async def _release_locker(self, locker_id: str):
        """락카 해제 (사용 가능 상태로 변경)"""
        try:
            locker_worksheet = self.spreadsheet.worksheet(self.sheets["lockers"])
            records = locker_worksheet.get_all_records()
            
            for i, record in enumerate(records, start=2):  # 2행부터 시작
                if str(record.get("락카번호")) == locker_id:
                    # 락카 해제
                    locker_worksheet.update(f"C{i}", "Y")  # 사용가능 = Y
                    locker_worksheet.update(f"D{i}", "")   # 현재사용자 삭제
                    locker_worksheet.update(f"F{i}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))  # 대여종료
                    break
            
            # 캐시 업데이트
            if locker_id in self._lockers_cache:
                self._lockers_cache[locker_id].current_user = None
                self._lockers_cache[locker_id].rental_end = datetime.now()
                self._lockers_cache[locker_id].is_available = True
                
        except Exception as e:
            logger.error(f"락카 해제 실패: {e}")
    
    async def _should_refresh_cache(self) -> bool:
        """캐시 갱신 필요 여부 확인"""
        if not self._last_sync:
            return True
        
        elapsed = (datetime.now(timezone.utc) - self._last_sync).total_seconds()
        return elapsed > self._cache_timeout
    
    async def refresh_cache(self):
        """수동 캐시 갱신"""
        await self._load_initial_data()
        logger.info("구글시트 캐시 갱신 완료")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """캐시 상태 정보"""
        return {
            "members_count": len(self._members_cache),
            "lockers_count": len(self._lockers_cache),
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "cache_timeout": self._cache_timeout
        }
