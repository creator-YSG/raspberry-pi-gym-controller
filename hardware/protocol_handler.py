"""
라즈베리파이용 프로토콜 핸들러

기존 ESP32 프로토콜을 라즈베리파이 환경에 맞게 포팅
바코드/QR 스캔 데이터 파싱 및 명령어 생성
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageType(Enum):
    """메시지 타입 열거형"""
    QR_SCAN = "qr_scan"
    BARCODE_SCAN = "barcode_scan"
    STATUS_REPORT = "status_report"
    HEARTBEAT = "heartbeat"
    COMMAND_RESPONSE = "command_response"
    ERROR = "error"
    UNKNOWN = "unknown"


class CommandType(Enum):
    """명령어 타입 열거형"""
    DOOR_OPEN = "DOOR_OPEN"
    DOOR_CLOSE = "DOOR_CLOSE"
    LOCKER_OPEN = "LOCKER_OPEN"
    LOCKER_CLOSE = "LOCKER_CLOSE"
    STATUS_REQUEST = "STATUS_REQUEST"
    CONFIG_SET = "CONFIG_SET"
    PING = "PING"


@dataclass
class ParsedMessage:
    """파싱된 메시지 데이터 구조"""
    type: MessageType
    data: Dict[str, Any]
    timestamp: float
    raw_message: str


@dataclass
class QRScanData:
    """QR 스캔 데이터 구조"""
    qr_content: str
    member_id: Optional[str] = None
    auth_timestamp: Optional[str] = None
    nonce: Optional[str] = None
    signature: Optional[str] = None


@dataclass
class BarcodeScanData:
    """바코드 스캔 데이터 구조"""
    barcode: str


@dataclass
class StatusData:
    """디바이스 상태 데이터 구조"""
    door_status: Optional[str] = None
    scanner_status: Optional[str] = None
    gpio_status: Optional[Dict[str, str]] = None
    uptime_seconds: Optional[int] = None
    cpu_temp: Optional[float] = None
    memory_usage: Optional[float] = None


class ProtocolHandler:
    """라즈베리파이용 프로토콜 핸들러"""

    def __init__(self) -> None:
        """프로토콜 핸들러 초기화"""
        self._message_id_counter = 0
        self._pending_commands: Dict[str, float] = {}
        self._stats = {
            "messages_parsed": 0,
            "commands_sent": 0,
            "parse_errors": 0,
            "invalid_messages": 0,
        }

    def parse_message(self, raw_message: str) -> Optional[ParsedMessage]:
        """라즈베리파이에서 수신한 메시지 파싱
        
        Args:
            raw_message: 원시 메시지 문자열
            
        Returns:
            ParsedMessage 객체 또는 None
        """
        if not raw_message or not isinstance(raw_message, str):
            self._stats["invalid_messages"] += 1
            return None

        raw_message = raw_message.strip()
        if not raw_message:
            return None

        try:
            timestamp = time.time()

            # QR 스캔: "QR:QRS:MEMBER123:timestamp:nonce:signature"
            if raw_message.startswith("QR:"):
                qr_data = self._parse_qr_scan(raw_message)
                if qr_data:
                    return ParsedMessage(
                        type=MessageType.QR_SCAN,
                        data=qr_data.__dict__,
                        timestamp=timestamp,
                        raw_message=raw_message,
                    )

            # 바코드 스캔: "BARCODE:123456789" 또는 JSON
            elif raw_message.startswith("BARCODE:") or (
                raw_message.startswith("{") and "BARCODE_SCAN" in raw_message
            ):
                barcode_data = self._parse_barcode_scan(raw_message)
                if barcode_data:
                    return ParsedMessage(
                        type=MessageType.BARCODE_SCAN,
                        data=barcode_data.__dict__,
                        timestamp=timestamp,
                        raw_message=raw_message,
                    )

            # 상태 보고: "STATUS:door=closed,scanner=ready"
            elif raw_message.startswith("STATUS:"):
                status_data = self._parse_status_report(raw_message)
                if status_data:
                    return ParsedMessage(
                        type=MessageType.STATUS_REPORT,
                        data=status_data.__dict__,
                        timestamp=timestamp,
                        raw_message=raw_message,
                    )

            # 하트비트: "HEARTBEAT"
            elif raw_message == "HEARTBEAT":
                return ParsedMessage(
                    type=MessageType.HEARTBEAT,
                    data={},
                    timestamp=timestamp,
                    raw_message=raw_message,
                )

            # 명령 응답: "RESP:CMD_ID:OK"
            elif raw_message.startswith("RESP:"):
                response_data = self._parse_command_response(raw_message)
                if response_data:
                    return ParsedMessage(
                        type=MessageType.COMMAND_RESPONSE,
                        data=response_data,
                        timestamp=timestamp,
                        raw_message=raw_message,
                    )

            # 에러 메시지: "ERROR:description"
            elif raw_message.startswith("ERROR:"):
                error_msg = raw_message[6:]
                return ParsedMessage(
                    type=MessageType.ERROR,
                    data={"error_message": error_msg},
                    timestamp=timestamp,
                    raw_message=raw_message,
                )

            # 순수 바코드 데이터 (접두사 없음)
            elif self._is_raw_barcode(raw_message):
                print(f"[ProtocolHandler] 순수 바코드 감지: {raw_message}")
                barcode_data = BarcodeScanData(barcode=raw_message)
                return ParsedMessage(
                    type=MessageType.BARCODE_SCAN,
                    data=barcode_data.__dict__,
                    timestamp=timestamp,
                    raw_message=raw_message,
                )

            # 알 수 없는 메시지
            else:
                print(f"[ProtocolHandler] 알 수 없는 메시지 형식: {raw_message}")
                self._stats["invalid_messages"] += 1
                return ParsedMessage(
                    type=MessageType.UNKNOWN,
                    data={"content": raw_message},
                    timestamp=timestamp,
                    raw_message=raw_message,
                )

            self._stats["messages_parsed"] += 1
            return None

        except Exception as e:
            print(f"[ProtocolHandler] 파싱 오류: {e}")
            self._stats["parse_errors"] += 1
            return None

    def _parse_qr_scan(self, raw_message: str) -> Optional[QRScanData]:
        """QR 스캔 메시지 파싱"""
        try:
            # 형식: "QR:QRS:MEMBER123:timestamp:nonce:signature"
            parts = raw_message.split(":", 5)
            if len(parts) < 2:
                return None

            qr_content = raw_message[3:]  # "QR:" 제거

            # 구조화된 QR 데이터 파싱
            if len(parts) >= 6 and parts[1] == "QRS":
                return QRScanData(
                    qr_content=qr_content,
                    member_id=parts[2],
                    auth_timestamp=parts[3],
                    nonce=parts[4],
                    signature=parts[5],
                )
            else:
                # 단순 QR 내용
                return QRScanData(qr_content=qr_content)

        except Exception as e:
            print(f"[ProtocolHandler] QR 파싱 오류: {e}")
            return None

    def _parse_barcode_scan(self, raw_message: str) -> Optional[BarcodeScanData]:
        """바코드 스캔 메시지 파싱"""
        try:
            # JSON 형태: {"type":"BARCODE_SCAN","data":"20240666",...}
            if raw_message.startswith("{") and "BARCODE_SCAN" in raw_message:
                import json
                try:
                    data = json.loads(raw_message)
                    if data.get("type") == "BARCODE_SCAN" and "data" in data:
                        barcode = str(data["data"]).strip()
                        if barcode:
                            print(f"[ProtocolHandler] JSON 바코드 파싱: {barcode}")
                            return BarcodeScanData(barcode=barcode)
                except json.JSONDecodeError as json_err:
                    print(f"[ProtocolHandler] JSON 파싱 오류: {json_err}")

            # 기본 형태: "BARCODE:123456789"
            elif raw_message.startswith("BARCODE:") and len(raw_message) > 8:
                barcode = raw_message[8:]  # "BARCODE:" 제거
                print(f"[ProtocolHandler] 기본 바코드 파싱: {barcode}")
                return BarcodeScanData(barcode=barcode)

            return None
        except Exception as e:
            print(f"[ProtocolHandler] 바코드 파싱 오류: {e}")
            return None

    def _parse_status_report(self, raw_message: str) -> Optional[StatusData]:
        """상태 보고 메시지 파싱"""
        try:
            # 형식: "STATUS:door=closed,scanner=ready,gpio=ok"
            status_str = raw_message[7:]  # "STATUS:" 제거
            status_data = StatusData()

            for pair in status_str.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    if key == "door":
                        status_data.door_status = value
                    elif key == "scanner":
                        status_data.scanner_status = value
                    elif key == "uptime":
                        try:
                            status_data.uptime_seconds = int(value)
                        except ValueError:
                            pass
                    elif key == "cpu_temp":
                        try:
                            status_data.cpu_temp = float(value)
                        except ValueError:
                            pass
                    elif key == "memory":
                        try:
                            status_data.memory_usage = float(value)
                        except ValueError:
                            pass
                    elif key.startswith("gpio_"):
                        if status_data.gpio_status is None:
                            status_data.gpio_status = {}
                        gpio_pin = key[5:]  # "gpio_" 제거
                        status_data.gpio_status[gpio_pin] = value

            return status_data

        except Exception as e:
            print(f"[ProtocolHandler] 상태 파싱 오류: {e}")
            return None

    def _parse_command_response(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """명령 응답 메시지 파싱"""
        try:
            # 형식: "RESP:CMD_ID:OK" 또는 "RESP:CMD_ID:ERROR:reason"
            parts = raw_message.split(":", 3)
            if len(parts) >= 3:
                cmd_id = parts[1]
                status = parts[2]
                error_reason = parts[3] if len(parts) > 3 else None

                return {
                    "command_id": cmd_id,
                    "status": status,
                    "error_reason": error_reason,
                    "success": status.upper() == "OK",
                }
            return None
        except Exception as e:
            print(f"[ProtocolHandler] 명령 응답 파싱 오류: {e}")
            return None

    def create_command(self, command_type: CommandType, **kwargs) -> str:
        """라즈베리파이용 명령어 생성
        
        Args:
            command_type: 명령어 타입
            **kwargs: 명령어별 매개변수
            
        Returns:
            포맷된 명령어 문자열
        """
        self._message_id_counter += 1
        cmd_id = f"CMD_{self._message_id_counter:04d}"

        try:
            if command_type == CommandType.DOOR_OPEN:
                duration_ms = kwargs.get("duration_ms", 3000)
                cmd = f"CMD:{cmd_id}:DOOR:OPEN:{duration_ms}"

            elif command_type == CommandType.DOOR_CLOSE:
                cmd = f"CMD:{cmd_id}:DOOR:CLOSE"

            elif command_type == CommandType.LOCKER_OPEN:
                locker_id = kwargs.get("locker_id", "L001")
                duration_ms = kwargs.get("duration_ms", 5000)
                cmd = f"CMD:{cmd_id}:LOCKER:OPEN:{locker_id}:{duration_ms}"

            elif command_type == CommandType.LOCKER_CLOSE:
                locker_id = kwargs.get("locker_id", "L001")
                cmd = f"CMD:{cmd_id}:LOCKER:CLOSE:{locker_id}"

            elif command_type == CommandType.STATUS_REQUEST:
                cmd = f"CMD:{cmd_id}:STATUS:REQUEST"

            elif command_type == CommandType.CONFIG_SET:
                key = kwargs.get("key", "")
                value = kwargs.get("value", "")
                cmd = f"CMD:{cmd_id}:CONFIG:SET:{key}:{value}"

            elif command_type == CommandType.PING:
                cmd = f"CMD:{cmd_id}:PING"

            else:
                raise ValueError(f"알 수 없는 명령어 타입: {command_type}")

            # 대기 중인 명령어 추가
            self._pending_commands[cmd_id] = time.time()
            self._stats["commands_sent"] += 1

            return cmd

        except Exception as e:
            print(f"[ProtocolHandler] 명령어 생성 오류: {e}")
            return ""

    def create_door_open_command(self, duration_ms: int = 3000) -> str:
        """문 열기 명령어 생성"""
        return self.create_command(CommandType.DOOR_OPEN, duration_ms=duration_ms)

    def create_locker_open_command(self, locker_id: str, duration_ms: int = 5000) -> str:
        """락카 열기 명령어 생성"""
        return self.create_command(
            CommandType.LOCKER_OPEN, locker_id=locker_id, duration_ms=duration_ms
        )

    def create_status_request(self) -> str:
        """상태 요청 명령어 생성"""
        return self.create_command(CommandType.STATUS_REQUEST)

    def create_config_command(self, key: str, value: str) -> str:
        """설정 명령어 생성"""
        return self.create_command(CommandType.CONFIG_SET, key=key, value=value)

    def create_ping_command(self) -> str:
        """핑 명령어 생성"""
        return self.create_command(CommandType.PING)

    def mark_command_completed(self, command_id: str) -> bool:
        """명령어 완료 표시
        
        Args:
            command_id: 완료된 명령어 ID
            
        Returns:
            True if 대기 중이던 명령어였음
        """
        return self._pending_commands.pop(command_id, None) is not None

    def get_pending_commands(self) -> List[str]:
        """대기 중인 명령어 ID 목록"""
        return list(self._pending_commands.keys())

    def cleanup_old_commands(self, timeout_seconds: float = 30.0) -> int:
        """오래된 대기 명령어 정리
        
        Args:
            timeout_seconds: 타임아웃 시간 (초)
            
        Returns:
            정리된 명령어 수
        """
        current_time = time.time()
        expired_commands = [
            cmd_id
            for cmd_id, timestamp in self._pending_commands.items()
            if current_time - timestamp > timeout_seconds
        ]

        for cmd_id in expired_commands:
            del self._pending_commands[cmd_id]

        if expired_commands:
            print(f"[ProtocolHandler] {len(expired_commands)}개 만료된 명령어 정리")

        return len(expired_commands)

    @property
    def stats(self) -> Dict[str, Any]:
        """프로토콜 핸들러 통계"""
        return {
            **self._stats,
            "pending_commands": len(self._pending_commands),
            "message_id_counter": self._message_id_counter,
        }

    def reset_stats(self) -> None:
        """통계 초기화"""
        self._stats = {
            "messages_parsed": 0,
            "commands_sent": 0,
            "parse_errors": 0,
            "invalid_messages": 0,
        }
        self._message_id_counter = 0
        self._pending_commands.clear()

    def validate_message_format(self, message: str) -> bool:
        """메시지 형식 검증 (전체 파싱 없이)
        
        Args:
            message: 검증할 메시지
            
        Returns:
            True if 유효한 형식
        """
        if not message or not isinstance(message, str):
            return False

        message = message.strip()
        if not message:
            return False

        # 알려진 메시지 접두사 확인
        valid_prefixes = [
            "QR:",
            "BARCODE:",
            "STATUS:",
            "HEARTBEAT",
            "RESP:",
            "ERROR:",
            "CMD:",
        ]

        return any(message.startswith(prefix) for prefix in valid_prefixes)

    def _is_raw_barcode(self, message: str) -> bool:
        """순수 바코드인지 확인 (바코드 리더기에서 직접 온 숫자)
        
        Args:
            message: 확인할 메시지
            
        Returns:
            True if 순수 바코드처럼 보임
        """
        # 6-15자리 숫자만 있고 0으로 시작하지 않는 경우
        return (
            message.isdigit()
            and 6 <= len(message) <= 15
            and not message.startswith("0")
        )
