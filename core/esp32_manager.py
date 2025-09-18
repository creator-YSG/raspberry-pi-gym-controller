"""
ESP32 디바이스 매니저

기존 ESP32 프로젝트의 통신 규칙을 따라 3개의 ESP32와 시리얼 통신을 관리
- ESP32 #1: 바코드 스캐너 + 릴레이
- ESP32 #2: 모터 제어 #1 + 센서
- ESP32 #3: 모터 제어 #2 + 센서
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[SERIAL] pyserial not available, using stub mode")

# 기존 하드웨어 모듈 사용
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'hardware'))

from hardware.protocol_handler import ProtocolHandler, ParsedMessage, MessageType

logger = logging.getLogger(__name__)


class ESP32Device:
    """ESP32 디바이스 정보"""
    
    def __init__(self, device_id: str, serial_port: str, device_type: str, 
                 baudrate: int = 115200):
        self.device_id = device_id
        self.serial_port = serial_port
        self.device_type = device_type  # "barcode_scanner", "motor_controller"
        self.baudrate = baudrate
        
        self.serial_connection: Optional[serial.Serial] = None
        self.is_online = False
        self.last_seen: Optional[datetime] = None
        self.read_buffer = ""
        
        # 통계
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "last_error": None
        }


class ESP32Manager:
    """ESP32 디바이스들과의 통신을 총괄 관리"""
    
    def __init__(self):
        self.devices: Dict[str, ESP32Device] = {}
        self.protocol_handler = ProtocolHandler()
        
        # 이벤트 핸들러들
        self._event_handlers: Dict[str, List[Callable]] = {
            "barcode_scanned": [],
            "qr_scanned": [],
            "motor_completed": [],
            "sensor_triggered": [],
            "device_error": [],
            "device_status": []
        }
        
        # 통신 루프 제어
        self._running = False
        self._read_tasks: List[asyncio.Task] = []
        
        logger.info("ESP32Manager 초기화 완료")
    
    def add_device(self, device_id: str, serial_port: str, device_type: str):
        """ESP32 디바이스 추가
        
        Args:
            device_id: 디바이스 식별자 (예: "esp32_barcode")
            serial_port: 시리얼 포트 (예: "/dev/ttyUSB0")
            device_type: 디바이스 타입 ("barcode_scanner", "motor_controller")
        """
        device = ESP32Device(device_id, serial_port, device_type)
        self.devices[device_id] = device
        logger.info(f"ESP32 디바이스 추가: {device_id} @ {serial_port}")
    
    async def connect_all_devices(self) -> bool:
        """모든 ESP32 디바이스에 연결
        
        Returns:
            모든 디바이스 연결 성공 여부
        """
        success_count = 0
        
        for device_id, device in self.devices.items():
            if await self._connect_device(device):
                success_count += 1
            else:
                logger.error(f"ESP32 연결 실패: {device_id}")
        
        logger.info(f"ESP32 연결 완료: {success_count}/{len(self.devices)}")
        return success_count == len(self.devices)
    
    async def _connect_device(self, device: ESP32Device) -> bool:
        """개별 ESP32 디바이스 연결"""
        if not SERIAL_AVAILABLE:
            logger.warning(f"pyserial 없음, 스텁 모드: {device.device_id}")
            device.is_online = True
            return True
        
        try:
            if device.serial_connection and device.serial_connection.is_open:
                device.serial_connection.close()
            
            device.serial_connection = serial.Serial(
                port=device.serial_port,
                baudrate=device.baudrate,
                timeout=0.1,  # non-blocking read
                write_timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # 버퍼 초기화
            device.serial_connection.reset_input_buffer()
            device.serial_connection.reset_output_buffer()
            device.read_buffer = ""
            
            device.is_online = True
            device.last_seen = datetime.now(timezone.utc)
            
            logger.info(f"ESP32 연결 성공: {device.device_id} @ {device.serial_port}")
            return True
            
        except Exception as e:
            logger.error(f"ESP32 연결 실패: {device.device_id}, {e}")
            device.is_online = False
            device.stats["errors"] += 1
            device.stats["last_error"] = str(e)
            return False
    
    async def disconnect_all_devices(self):
        """모든 ESP32 디바이스 연결 해제"""
        for device in self.devices.values():
            if device.serial_connection and device.serial_connection.is_open:
                try:
                    device.serial_connection.close()
                    device.is_online = False
                    logger.info(f"ESP32 연결 해제: {device.device_id}")
                except Exception as e:
                    logger.error(f"ESP32 연결 해제 오류: {device.device_id}, {e}")
    
    async def send_command(self, device_id: str, command: str, **kwargs) -> bool:
        """ESP32에 명령 전송
        
        Args:
            device_id: 대상 디바이스 ID
            command: 명령어 (예: "OPEN_LOCKER", "START_SCAN")
            **kwargs: 명령 파라미터
            
        Returns:
            전송 성공 여부
        """
        device = self.devices.get(device_id)
        if not device or not device.is_online:
            logger.error(f"ESP32 디바이스 오프라인: {device_id}")
            return False
        
        # 기존 프로토콜에 맞는 명령 형식으로 변환
        if device.device_type == "barcode_scanner":
            message = self._build_barcode_command(command, **kwargs)
        elif device.device_type == "motor_controller":
            message = self._build_motor_command(command, **kwargs)
        else:
            logger.error(f"알 수 없는 디바이스 타입: {device.device_type}")
            return False
        
        return await self._send_raw_message(device, message)
    
    def _build_barcode_command(self, command: str, **kwargs) -> str:
        """바코드 스캐너 명령 생성"""
        if command == "START_SCAN":
            return "START_SCAN"
        elif command == "STOP_SCAN":
            return "STOP_SCAN"
        elif command == "GET_STATUS":
            return "STATUS?"
        else:
            return f"CMD:{command}"
    
    def _build_motor_command(self, command: str, **kwargs) -> str:
        """모터 컨트롤러 명령 생성"""
        if command == "OPEN_LOCKER":
            locker_id = kwargs.get("locker_id", "")
            duration = kwargs.get("duration_ms", 3000)
            return f"OPEN:{locker_id}:{duration}"
        elif command == "CLOSE_LOCKER":
            locker_id = kwargs.get("locker_id", "")
            return f"CLOSE:{locker_id}"
        elif command == "GET_STATUS":
            return "STATUS?"
        elif command == "CHECK_SENSOR":
            sensor_id = kwargs.get("sensor_id", "")
            return f"SENSOR:{sensor_id}"
        else:
            return f"CMD:{command}"
    
    async def _send_raw_message(self, device: ESP32Device, message: str) -> bool:
        """원시 메시지 전송"""
        if not device.serial_connection or not device.is_online:
            return False
        
        try:
            # 메시지 전송 (줄바꿈 추가)
            full_message = message + "\n"
            device.serial_connection.write(full_message.encode('utf-8'))
            device.serial_connection.flush()
            
            device.stats["messages_sent"] += 1
            device.last_seen = datetime.now(timezone.utc)
            
            logger.debug(f"ESP32 메시지 전송: {device.device_id} <- {message}")
            return True
            
        except Exception as e:
            logger.error(f"ESP32 메시지 전송 실패: {device.device_id}, {e}")
            device.stats["errors"] += 1
            device.stats["last_error"] = str(e)
            device.is_online = False
            return False
    
    async def start_communication(self):
        """ESP32들과의 통신 시작 (백그라운드 읽기 루프)"""
        if self._running:
            logger.warning("ESP32 통신이 이미 실행 중입니다")
            return
        
        self._running = True
        
        # 각 디바이스별로 읽기 태스크 시작
        for device in self.devices.values():
            if device.is_online:
                task = asyncio.create_task(self._device_read_loop(device))
                self._read_tasks.append(task)
        
        logger.info("ESP32 통신 시작")
    
    async def stop_communication(self):
        """ESP32 통신 중지"""
        self._running = False
        
        # 모든 읽기 태스크 취소
        for task in self._read_tasks:
            task.cancel()
        
        # 태스크 완료 대기
        if self._read_tasks:
            await asyncio.gather(*self._read_tasks, return_exceptions=True)
        
        self._read_tasks.clear()
        logger.info("ESP32 통신 중지")
    
    async def _device_read_loop(self, device: ESP32Device):
        """개별 디바이스 읽기 루프"""
        logger.info(f"ESP32 읽기 루프 시작: {device.device_id}")
        
        while self._running and device.is_online:
            try:
                await self._read_device_messages(device)
                await asyncio.sleep(0.01)  # 10ms 간격
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ESP32 읽기 루프 오류: {device.device_id}, {e}")
                device.stats["errors"] += 1
                device.stats["last_error"] = str(e)
                await asyncio.sleep(1)  # 오류 시 1초 대기
        
        logger.info(f"ESP32 읽기 루프 종료: {device.device_id}")
    
    async def _read_device_messages(self, device: ESP32Device):
        """디바이스에서 메시지 읽기"""
        if not device.serial_connection or not device.is_online:
            return
        
        try:
            # 시리얼 데이터 읽기
            if device.serial_connection.in_waiting > 0:
                data = device.serial_connection.read(device.serial_connection.in_waiting)
                device.read_buffer += data.decode('utf-8', errors='ignore')
                
                # 완성된 메시지 처리 (줄바꿈으로 구분)
                while '\n' in device.read_buffer:
                    line, device.read_buffer = device.read_buffer.split('\n', 1)
                    line = line.strip()
                    
                    if line:
                        await self._process_received_message(device, line)
                        
        except Exception as e:
            logger.error(f"ESP32 메시지 읽기 오류: {device.device_id}, {e}")
            device.stats["errors"] += 1
            device.stats["last_error"] = str(e)
    
    async def _process_received_message(self, device: ESP32Device, raw_message: str):
        """수신된 메시지 처리"""
        try:
            # 기존 프로토콜 핸들러로 메시지 파싱
            parsed = self.protocol_handler.parse_message(raw_message)
            
            if parsed:
                device.stats["messages_received"] += 1
                device.last_seen = datetime.now(timezone.utc)
                
                # 메시지 타입별 이벤트 발생
                await self._dispatch_event(device, parsed)
                
                logger.debug(f"ESP32 메시지 수신: {device.device_id} -> {parsed.type.value}")
            else:
                logger.warning(f"ESP32 메시지 파싱 실패: {device.device_id}, {raw_message}")
                
        except Exception as e:
            logger.error(f"ESP32 메시지 처리 오류: {device.device_id}, {e}")
            device.stats["errors"] += 1
    
    async def _dispatch_event(self, device: ESP32Device, message: ParsedMessage):
        """이벤트 디스패치"""
        event_type = None
        event_data = {
            "device_id": device.device_id,
            "device_type": device.device_type,
            "timestamp": message.timestamp,
            "raw_message": message.raw_message,
            **message.data
        }
        
        # 메시지 타입별 이벤트 매핑
        if message.type == MessageType.BARCODE_SCAN:
            event_type = "barcode_scanned"
        elif message.type == MessageType.QR_SCAN:
            event_type = "qr_scanned"
        elif message.type == MessageType.STATUS_REPORT:
            event_type = "device_status"
        elif message.type == MessageType.ERROR:
            event_type = "device_error"
        
        # 이벤트 핸들러 호출
        if event_type and event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_data)
                    else:
                        handler(event_data)
                except Exception as e:
                    logger.error(f"이벤트 핸들러 오류: {event_type}, {e}")
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """이벤트 핸들러 등록
        
        Args:
            event_type: 이벤트 타입 ("barcode_scanned", "qr_scanned", "motor_completed" 등)
            handler: 이벤트 처리 함수 (동기/비동기 모두 지원)
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        
        self._event_handlers[event_type].append(handler)
        logger.info(f"이벤트 핸들러 등록: {event_type}")
    
    def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """디바이스 상태 조회"""
        device = self.devices.get(device_id)
        if not device:
            return None
        
        return {
            "device_id": device.device_id,
            "device_type": device.device_type,
            "serial_port": device.serial_port,
            "is_online": device.is_online,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "stats": device.stats.copy()
        }
    
    def get_all_devices_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 디바이스 상태 조회"""
        return {
            device_id: self.get_device_status(device_id)
            for device_id in self.devices.keys()
        }


# 사전 정의된 디바이스 설정
DEFAULT_DEVICE_CONFIG = {
    "esp32_barcode": {
        "serial_port": "/dev/ttyUSB0",
        "device_type": "barcode_scanner"
    },
    "esp32_motor1": {
        "serial_port": "/dev/ttyUSB1", 
        "device_type": "motor_controller"
    },
    "esp32_motor2": {
        "serial_port": "/dev/ttyUSB2",
        "device_type": "motor_controller"
    }
}


def create_default_esp32_manager() -> ESP32Manager:
    """기본 설정으로 ESP32Manager 생성"""
    manager = ESP32Manager()
    
    for device_id, config in DEFAULT_DEVICE_CONFIG.items():
        manager.add_device(
            device_id=device_id,
            serial_port=config["serial_port"],
            device_type=config["device_type"]
        )
    
    return manager
