"""
Google Sheets 동기화 서비스

Google Sheets ↔ SQLite 간 데이터 동기화
- 다운로드: 회원 정보, 시스템 설정
- 업로드: 대여 기록, 락카 현황, 센서 이벤트
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    print("[SheetsSync] gspread 없음, 스텁 모드로 실행")

logger = logging.getLogger(__name__)


class SheetsSync:
    """Google Sheets 동기화 클래스"""
    
    def __init__(self, config_path: str = None):
        """
        초기화
        
        Args:
            config_path: 설정 파일 경로 (기본: config/google_sheets_config.json)
        """
        # 프로젝트 루트 찾기
        self.project_root = Path(__file__).parent.parent.parent
        
        # 설정 로드
        if config_path is None:
            config_path = self.project_root / "config" / "google_sheets_config.json"
        
        self.config = self._load_config(config_path)
        self.spreadsheet_id = self.config.get("spreadsheet_id")
        self.sheet_names = self.config.get("sheet_names", {})
        
        # 인증 파일 경로
        creds_file = self.config.get("credentials_file", "google_credentials.json")
        self.credentials_path = self.project_root / "config" / creds_file
        
        # API 클라이언트
        self.client = None
        self.spreadsheet = None
        
        # Rate limit 관리
        self.last_api_call = 0
        self.min_interval = 1.0  # 최소 1초 간격
        
        # 연결 상태
        self.connected = False
        
        logger.info(f"[SheetsSync] 초기화: {self.config.get('spreadsheet_name', 'Unknown')}")
    
    def _load_config(self, config_path) -> dict:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[SheetsSync] 설정 파일 로드 실패: {e}")
            return {}
    
    def connect(self) -> bool:
        """Google Sheets API 연결"""
        if not GSPREAD_AVAILABLE:
            logger.warning("[SheetsSync] gspread 없음, 스텁 모드")
            return False
        
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = Credentials.from_service_account_file(
                str(self.credentials_path), scopes=scope
            )
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.connected = True
            
            logger.info(f"[SheetsSync] ✓ 연결 성공: {self.spreadsheet.title}")
            return True
            
        except Exception as e:
            logger.error(f"[SheetsSync] ✗ 연결 실패: {e}")
            self.connected = False
            return False
    
    def _rate_limit(self):
        """API 호출 제한 관리 (분당 60회 제한 대응)"""
        now = time.time()
        elapsed = now - self.last_api_call
        
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        
        self.last_api_call = time.time()
    
    def _get_worksheet(self, sheet_key: str):
        """워크시트 가져오기"""
        if not self.connected or not self.spreadsheet:
            return None
        
        sheet_name = self.sheet_names.get(sheet_key)
        if not sheet_name:
            logger.error(f"[SheetsSync] 시트 키 없음: {sheet_key}")
            return None
        
        try:
            self._rate_limit()
            return self.spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger.error(f"[SheetsSync] 워크시트 접근 실패: {sheet_name}, {e}")
            return None
    
    # =============================
    # 다운로드 (Sheets → SQLite)
    # =============================
    
    def download_members(self, db_manager) -> int:
        """회원 정보 다운로드"""
        try:
            worksheet = self._get_worksheet("members")
            if not worksheet:
                return 0
            
            self._rate_limit()
            records = worksheet.get_all_records()
            
            if not records:
                logger.info("[SheetsSync] 다운로드할 회원 데이터 없음")
                return 0
            
            count = 0
            for record in records:
                member_id = record.get('member_id')
                if not member_id:
                    continue
                
                # 바코드 처리
                barcode = record.get('barcode', '')
                if barcode:
                    barcode = str(barcode).strip()
                
                try:
                    db_manager.execute_query("""
                        INSERT OR REPLACE INTO members 
                        (member_id, barcode, qr_code, member_name, phone, email,
                         membership_type, program_name, status, expiry_date,
                         gender, member_category, customer_type, sync_date, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        member_id,
                        barcode,
                        record.get('qr_code') or None,
                        record.get('member_name', ''),
                        record.get('phone', ''),
                        record.get('email', ''),
                        record.get('membership_type', 'basic'),
                        record.get('program_name', ''),
                        record.get('status', 'active'),
                        record.get('expiry_date') or None,
                        record.get('gender', 'male'),
                        record.get('member_category', 'general'),
                        record.get('customer_type', '학부'),
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    count += 1
                except Exception as e:
                    logger.error(f"[SheetsSync] 회원 저장 실패: {member_id}, {e}")
            
            logger.info(f"[SheetsSync] 회원 다운로드 완료: {count}명")
            return count
            
        except Exception as e:
            logger.error(f"[SheetsSync] 회원 다운로드 오류: {e}")
            return 0
    
    def download_settings(self, db_manager) -> int:
        """시스템 설정 다운로드"""
        try:
            worksheet = self._get_worksheet("settings")
            if not worksheet:
                return 0
            
            self._rate_limit()
            records = worksheet.get_all_records()
            
            count = 0
            for record in records:
                setting_key = record.get('setting_key')
                if not setting_key:
                    continue
                
                try:
                    db_manager.execute_query("""
                        INSERT OR REPLACE INTO system_settings 
                        (setting_key, setting_value, setting_type, description, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        setting_key,
                        str(record.get('setting_value', '')),
                        record.get('setting_type', 'string'),
                        record.get('description', ''),
                        datetime.now().isoformat()
                    ))
                    count += 1
                except Exception as e:
                    logger.error(f"[SheetsSync] 설정 저장 실패: {setting_key}, {e}")
            
            logger.info(f"[SheetsSync] 설정 다운로드 완료: {count}개")
            return count
            
        except Exception as e:
            logger.error(f"[SheetsSync] 설정 다운로드 오류: {e}")
            return 0
    
    # =============================
    # 업로드 (SQLite → Sheets)
    # =============================
    
    def _row_to_dict(self, row) -> dict:
        """sqlite3.Row를 dict로 변환"""
        if row is None:
            return {}
        return dict(row)
    
    def upload_rentals(self, db_manager) -> int:
        """대여 기록 업로드 (미동기화 레코드만)"""
        try:
            worksheet = self._get_worksheet("rentals")
            if not worksheet:
                return 0
            
            # 미동기화 대여 기록 조회
            cursor = db_manager.execute_query("""
                SELECT r.*, m.member_name
                FROM rentals r
                LEFT JOIN members m ON r.member_id = m.member_id
                WHERE r.sync_status = 0
                ORDER BY r.created_at
                LIMIT 50
            """)
            
            if not cursor:
                return 0
            
            rows_data = cursor.fetchall()
            if not rows_data:
                return 0
            
            rows = []
            rental_ids = []
            
            for row in rows_data:
                record = self._row_to_dict(row)
                
                # zone 추출 (locker_number의 첫 글자로 판단)
                locker_number = record.get('locker_number', '') or ''
                zone = ''
                if locker_number.startswith('M'):
                    zone = 'MALE'
                elif locker_number.startswith('F'):
                    zone = 'FEMALE'
                elif locker_number.startswith('S'):
                    zone = 'STAFF'
                
                rows.append([
                    record.get('rental_id'),
                    record.get('transaction_id'),
                    record.get('member_id'),
                    record.get('member_name', ''),
                    locker_number,
                    zone,
                    record.get('rental_barcode_time', ''),
                    record.get('rental_sensor_time', ''),
                    record.get('return_sensor_time', ''),
                    record.get('status'),
                    record.get('device_id', ''),
                    record.get('created_at')
                ])
                rental_ids.append(record.get('rental_id'))
            
            # 시트에 추가
            self._rate_limit()
            worksheet.append_rows(rows)
            
            # 동기화 완료 표시
            if rental_ids:
                placeholders = ', '.join(['?' for _ in rental_ids])
                db_manager.execute_query(f"""
                    UPDATE rentals SET sync_status = 1 WHERE rental_id IN ({placeholders})
                """, rental_ids)
            
            logger.info(f"[SheetsSync] 대여 기록 업로드 완료: {len(rows)}건")
            return len(rows)
            
        except Exception as e:
            logger.error(f"[SheetsSync] 대여 기록 업로드 오류: {e}")
            return 0
    
    def upload_locker_status(self, db_manager) -> int:
        """락카 현황 업로드 (전체 업데이트)"""
        try:
            worksheet = self._get_worksheet("lockers")
            if not worksheet:
                return 0
            
            # 락카 상태 조회
            cursor = db_manager.execute_query("""
                SELECT ls.*, m.member_name as current_member_name
                FROM locker_status ls
                LEFT JOIN members m ON ls.current_member = m.member_id
                ORDER BY ls.zone, ls.locker_number
            """)
            
            if not cursor:
                return 0
            
            rows_data = cursor.fetchall()
            if not rows_data:
                return 0
            
            # 헤더 포함 전체 데이터 구성
            headers = [
                "locker_number", "zone", "sensor_status", "door_status",
                "current_member", "current_member_name", "nfc_uid",
                "maintenance_status", "last_change_time", "updated_at"
            ]
            
            rows = [headers]
            for row in rows_data:
                record = self._row_to_dict(row)
                rows.append([
                    record.get('locker_number', ''),
                    record.get('zone', ''),
                    record.get('sensor_status', 0),
                    record.get('door_status', 0),
                    record.get('current_member', '') or '',
                    record.get('current_member_name', '') or '',
                    record.get('nfc_uid', '') or '',
                    record.get('maintenance_status', 'normal'),
                    record.get('last_change_time', '') or '',
                    datetime.now().isoformat()
                ])
            
            # 시트 전체 업데이트
            self._rate_limit()
            worksheet.clear()
            self._rate_limit()
            worksheet.update(values=rows, range_name='A1')
            
            # 헤더 스타일
            self._rate_limit()
            worksheet.format('A1:J1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            logger.info(f"[SheetsSync] 락카 현황 업로드 완료: {len(rows_data)}개")
            return len(rows_data)
            
        except Exception as e:
            logger.error(f"[SheetsSync] 락카 현황 업로드 오류: {e}")
            return 0
    
    def upload_sensor_events(self, db_manager, limit: int = 100) -> int:
        """센서 이벤트 업로드"""
        try:
            worksheet = self._get_worksheet("sensor_events")
            if not worksheet:
                return 0
            
            # 최근 센서 이벤트 조회 (동기화되지 않은 것만)
            cursor = db_manager.execute_query("""
                SELECT * FROM sensor_events
                ORDER BY event_timestamp DESC
                LIMIT ?
            """, (limit,))
            
            if not cursor:
                return 0
            
            rows_data = cursor.fetchall()
            if not rows_data:
                return 0
            
            rows = []
            for row in rows_data:
                record = self._row_to_dict(row)
                rows.append([
                    record.get('event_id', ''),
                    record.get('locker_number', ''),
                    record.get('sensor_state', ''),
                    record.get('member_id', '') or '',
                    record.get('rental_id', '') or '',
                    record.get('session_context', '') or '',
                    record.get('description', '') or '',
                    record.get('event_timestamp', '')
                ])
            
            # 헤더 포함 전체 데이터 구성
            headers = [
                "event_id", "locker_number", "sensor_state", "member_id",
                "rental_id", "session_context", "description", "event_timestamp"
            ]
            
            all_rows = [headers] + rows
            
            # 시트 전체 업데이트 (최근 데이터만)
            self._rate_limit()
            worksheet.clear()
            self._rate_limit()
            worksheet.update(values=all_rows, range_name='A1')
            
            # 헤더 스타일
            self._rate_limit()
            worksheet.format('A1:H1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
            
            logger.info(f"[SheetsSync] 센서 이벤트 업로드 완료: {len(rows)}건")
            return len(rows)
            
        except Exception as e:
            logger.error(f"[SheetsSync] 센서 이벤트 업로드 오류: {e}")
            return 0
    
    # =============================
    # 배치 동기화
    # =============================
    
    def sync_all_downloads(self, db_manager) -> Dict[str, int]:
        """모든 다운로드 동기화 실행"""
        if not self.connected:
            if not self.connect():
                return {}
        
        result = {
            'members': self.download_members(db_manager),
            'settings': self.download_settings(db_manager),
        }
        logger.info(f"[SheetsSync] 다운로드 완료: {result}")
        return result
    
    def sync_all_uploads(self, db_manager) -> Dict[str, int]:
        """모든 업로드 동기화 실행"""
        if not self.connected:
            if not self.connect():
                return {}
        
        result = {
            'rentals': self.upload_rentals(db_manager),
            'lockers': self.upload_locker_status(db_manager),
            'sensor_events': self.upload_sensor_events(db_manager),
        }
        
        if any(result.values()):
            logger.info(f"[SheetsSync] 업로드 완료: {result}")
        return result
    
    def get_status(self) -> Dict:
        """동기화 상태 정보"""
        return {
            'connected': self.connected,
            'spreadsheet_id': self.spreadsheet_id,
            'spreadsheet_name': self.config.get('spreadsheet_name', ''),
            'sheet_names': self.sheet_names,
        }

