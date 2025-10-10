"""
라즈베리파이용 시리얼 바코드 스캐너

기존 ESP32 시리얼 통신을 라즈베리파이로 포팅
USB 바코드 스캐너와 시리얼 통신 지원
"""

import asyncio
import re
import time
from typing import Optional, Tuple, Dict, Any

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[SERIAL] pyserial not available, using stub mode")


class SerialBarcodeScanner:
    """시리얼 바코드 스캐너 클래스
    
    기능:
    - USB/시리얼 바코드 스캐너 지원
    - QR 코드 및 바코드 자동 감지
    - 비동기 스캔 데이터 읽기
    - 자동 포트 감지
    """

    def __init__(self, 
                 port: Optional[str] = None,
                 baudrate: int = 115200,
                 timeout: float = 0.1,
                 auto_detect: bool = True):
        """바코드 스캐너 초기화
        
        Args:
            port: 시리얼 포트 경로 (None이면 자동 감지)
            baudrate: 통신 속도 (9600, 115200 등)
            timeout: 읽기 타임아웃 (초)
            auto_detect: 자동 포트 감지 활성화
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.auto_detect = auto_detect
        
        self._serial: Optional["serial.Serial"] = None
        self._connected = False
        self._read_buffer = ""
        
        # 스텁 모드 제어
        self._last_stub_emit = 0.0
        self._stub_period = 10.0  # 10초마다 스텁 데이터 생성
        
        # 통계
        self._stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "scans_read": 0,
            "qr_scans": 0,
            "barcode_scans": 0,
            "parse_errors": 0,
            "serial_errors": 0
        }
        
        print(f"[SerialScanner] 초기화 - 포트:{port}, 속도:{baudrate}")

    async def connect(self) -> bool:
        """바코드 스캐너 연결
        
        Returns:
            True if 연결 성공
        """
        if not SERIAL_AVAILABLE:
            print("[SerialScanner] pyserial 없음, 스텁 모드로 실행")
            self._connected = True
            return True
            
        self._stats["connection_attempts"] += 1
        
        # 자동 포트 감지
        if not self.port and self.auto_detect:
            detected_port = await self._detect_scanner_port()
            if detected_port:
                self.port = detected_port
                print(f"[SerialScanner] 자동 감지된 포트: {self.port}")
            else:
                print("[SerialScanner] 적합한 포트를 찾지 못함")
                return False
        
        if not self.port:
            print("[SerialScanner] 포트가 지정되지 않음")
            return False
        
        try:
            print(f"[SerialScanner] 연결 시도: {self.port} @ {self.baudrate}")
            
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=1.0
            )
            
            # 버퍼 클리어
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            self._read_buffer = ""
            
            self._connected = True
            self._stats["successful_connections"] += 1
            
            print(f"[SerialScanner] 연결 성공: {self.port}")
            return True
            
        except serial.SerialException as e:
            print(f"[SerialScanner] 연결 실패: {e}")
            self._stats["serial_errors"] += 1
            return False
        except Exception as e:
            print(f"[SerialScanner] 예상치 못한 오류: {e}")
            self._stats["serial_errors"] += 1
            return False

    async def disconnect(self) -> None:
        """바코드 스캐너 연결 해제"""
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
                print(f"[SerialScanner] 연결 해제: {self.port}")
            except Exception as e:
                print(f"[SerialScanner] 연결 해제 오류: {e}")
        
        self._serial = None
        self._connected = False
        self._read_buffer = ""

    async def stop(self) -> None:
        """스캐너 정지 (disconnect와 동일)"""
        await self.disconnect()

    async def read_scan(self) -> Optional[Tuple[str, str]]:
        """스캔 데이터 읽기 (비블로킹)
        
        Returns:
            (scan_type, data) 튜플 또는 None
            scan_type: 'QR' 또는 'BARCODE'
        """
        try:
            # 실제 하드웨어 시도
            if self._serial and self._serial.is_open:
                raw_data = await self._read_serial_line()
                if raw_data:
                    return self._parse_scan_data(raw_data)
            
            # 스텁 모드 (개발/테스트용)
            elif not SERIAL_AVAILABLE or not self._connected:
                return await self._generate_stub_scan()
            
            return None
            
        except Exception as e:
            print(f"[SerialScanner] 스캔 읽기 오류: {e}")
            self._stats["serial_errors"] += 1
            return None

    async def _read_serial_line(self) -> Optional[str]:
        """시리얼에서 한 줄 읽기"""
        try:
            # 사용 가능한 데이터 읽기
            if self._serial.in_waiting > 0:
                new_data = self._serial.read(self._serial.in_waiting).decode('utf-8', errors='ignore')
                self._read_buffer += new_data
            
            # 완전한 라인 추출
            if '\n' in self._read_buffer:
                line, self._read_buffer = self._read_buffer.split('\n', 1)
                line = line.strip()
                
                if line:
                    print(f"[SerialScanner] 시리얼 데이터: {line}")
                    return line
                    
            return None
            
        except Exception as e:
            print(f"[SerialScanner] 시리얼 읽기 오류: {e}")
            return None

    async def _generate_stub_scan(self) -> Optional[Tuple[str, str]]:
        """스텁 스캔 데이터 생성 (테스트용)"""
        now = time.time()
        
        # 주기적으로만 스텁 데이터 생성
        if (now - self._last_stub_emit) < self._stub_period:
            return None
            
        self._last_stub_emit = now
        
        # 번갈아가며 QR과 바코드 데이터 생성
        import random
        if random.choice([True, False]):
            print("[SerialScanner] 스텁 바코드 생성")
            return ("BARCODE", "123456789")
        else:
            print("[SerialScanner] 스텁 QR 생성")
            return ("QR", "STUB_MEMBER_001")

    def _parse_scan_data(self, raw_data: str) -> Optional[Tuple[str, str]]:
        """스캔 데이터 파싱
        
        Args:
            raw_data: 원시 스캔 데이터
            
        Returns:
            (scan_type, data) 튜플 또는 None
        """
        if not raw_data:
            return None
            
        raw_data = raw_data.strip()
        self._stats["scans_read"] += 1
        
        try:
            # QR 코드 형식: "QR:데이터" 또는 "QRS:구조화데이터"
            if raw_data.startswith(("QR:", "QRS:")):
                qr_data = raw_data[3:] if raw_data.startswith("QR:") else raw_data[4:]
                self._stats["qr_scans"] += 1
                print(f"[SerialScanner] QR 파싱: {qr_data}")
                return ("QR", qr_data)
            
            # 바코드 형식: "BARCODE:데이터" 또는 JSON 형식
            elif raw_data.startswith("BARCODE:"):
                barcode_data = raw_data[8:]
                if self._is_valid_barcode(barcode_data):
                    self._stats["barcode_scans"] += 1
                    print(f"[SerialScanner] 바코드 파싱: {barcode_data}")
                    return ("BARCODE", barcode_data)
            
            # JSON 형식 바코드 (ESP32에서 오는 형식)
            elif raw_data.startswith("{") and "BARCODE_SCAN" in raw_data:
                barcode_data = self._parse_json_barcode(raw_data)
                if barcode_data:
                    self._stats["barcode_scans"] += 1
                    print(f"[SerialScanner] JSON 바코드 파싱: {barcode_data}")
                    return ("BARCODE", barcode_data)
            
            # 순수 숫자 바코드 (프리픽스 없음)
            elif self._is_valid_barcode(raw_data):
                self._stats["barcode_scans"] += 1
                print(f"[SerialScanner] 순수 바코드 파싱: {raw_data}")
                return ("BARCODE", raw_data)
            
            # 알 수 없는 형식
            else:
                print(f"[SerialScanner] 알 수 없는 스캔 형식: {raw_data}")
                self._stats["parse_errors"] += 1
                return None
                
        except Exception as e:
            print(f"[SerialScanner] 파싱 오류: {e}")
            self._stats["parse_errors"] += 1
            return None

    def _parse_json_barcode(self, json_str: str) -> Optional[str]:
        """JSON 형식 바코드 파싱"""
        try:
            import json
            data = json.loads(json_str)
            if data.get("type") == "BARCODE_SCAN" and "data" in data:
                barcode = str(data["data"]).strip()
                if self._is_valid_barcode(barcode):
                    return barcode
            return None
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _is_valid_barcode(self, barcode_str: str) -> bool:
        """바코드 형식 검증
        
        Args:
            barcode_str: 검증할 바코드 문자열
            
        Returns:
            True if 유효한 바코드 형식
        """
        if not barcode_str:
            return False
        
        # 6-15자리 숫자 (일반적인 바코드)
        if re.match(r"^\d{6,15}$", barcode_str):
            return True
        
        # 영숫자 조합 (6-15자리, 최소 1개 숫자 포함)
        if (re.match(r"^[A-Za-z0-9]{6,15}$", barcode_str) and 
            re.search(r"\d", barcode_str)):
            return True
        
        return False

    async def _detect_scanner_port(self) -> Optional[str]:
        """바코드 스캐너 포트 자동 감지
        
        Returns:
            감지된 포트 경로 또는 None
        """
        if not SERIAL_AVAILABLE:
            return None
        
        try:
            ports = serial.tools.list_ports.comports()
            
            # 바코드 스캐너 관련 키워드
            scanner_keywords = [
                "barcode", "scanner", "cp210", "ch340", "ft232", 
                "usb serial", "arduino", "esp32"
            ]
            
            # USB VID:PID (일반적인 USB-시리얼 칩)
            usb_ids = [
                "10c4:ea60",  # CP2102
                "1a86:7523",  # CH340  
                "0403:6001",  # FT232
                "2341:0043",  # Arduino
            ]
            
            # 키워드로 찾기
            for port in ports:
                description = (port.description or "").lower()
                hwid = (port.hwid or "").lower()
                
                # USB ID로 매칭
                for usb_id in usb_ids:
                    if usb_id in hwid:
                        print(f"[SerialScanner] USB ID로 포트 발견: {port.device} ({port.description})")
                        return port.device
                
                # 키워드로 매칭
                for keyword in scanner_keywords:
                    if keyword in description:
                        print(f"[SerialScanner] 키워드로 포트 발견: {port.device} ({port.description})")
                        return port.device
            
            # 첫 번째 사용 가능한 포트 사용
            if ports:
                port = ports[0]
                print(f"[SerialScanner] 첫 번째 포트 사용: {port.device} ({port.description})")
                return port.device
            
            return None
            
        except Exception as e:
            print(f"[SerialScanner] 포트 감지 오류: {e}")
            return None

    # 속성 및 정보

    @property
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not SERIAL_AVAILABLE:
            return self._connected  # 스텁 모드
        return self._serial is not None and self._serial.is_open

    @property
    def stats(self) -> Dict[str, Any]:
        """스캐너 통계"""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """통계 초기화"""
        self._stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "scans_read": 0,
            "qr_scans": 0,
            "barcode_scans": 0,
            "parse_errors": 0,
            "serial_errors": 0
        }

    def get_available_ports(self) -> list:
        """사용 가능한 시리얼 포트 목록"""
        if not SERIAL_AVAILABLE:
            return []
        
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception:
            return []

    def __repr__(self) -> str:
        """문자열 표현"""
        status = "connected" if self.is_connected else "disconnected"
        return f"SerialBarcodeScanner(port={self.port}, baudrate={self.baudrate}, {status})"

