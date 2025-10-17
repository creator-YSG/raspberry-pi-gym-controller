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
        
        # 자동 감지 설정
        self.auto_detect_enabled = True
        self._last_scan_time = 0
        self._scan_interval = 10.0  # 10초마다 재스캔
        
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
    
    async def scan_and_connect_esp32_devices(self) -> int:
        """ESP32 디바이스 자동 스캔 및 연결
        
        Returns:
            연결된 디바이스 수
        """
        if not SERIAL_AVAILABLE:
            logger.warning("pyserial 없음, ESP32 자동 감지 불가")
            return 0
        
        logger.info("🔍 ESP32 디바이스 자동 스캔 시작...")
        connected_count = 0
        
        try:
            # 사용 가능한 시리얼 포트 스캔
            ports = serial.tools.list_ports.comports()
            
            # ESP32 관련 키워드 및 USB ID
            esp32_keywords = [
                "esp32", "arduino", "cp210", "ch340", "ft232",
                "usb serial", "silicon labs", "wch"
            ]
            
            esp32_usb_ids = [
                "10c4:ea60",  # CP2102 (ESP32 개발보드)
                "1a86:7523",  # CH340G (ESP32 클론)
                "0403:6001",  # FT232 (일부 ESP32)
                "2341:0043",  # Arduino 호환
                "1a86:55d4",  # CH9102 (새로운 ESP32)
            ]
            
            detected_ports = []
            
            for port in ports:
                description = (port.description or "").lower()
                hwid = (port.hwid or "").lower()
                manufacturer = (port.manufacturer or "").lower()
                
                # ESP32 장치인지 확인
                is_esp32 = False
                
                # USB ID로 확인
                for usb_id in esp32_usb_ids:
                    if usb_id in hwid:
                        is_esp32 = True
                        logger.info(f"📱 ESP32 USB ID 매칭: {port.device} ({usb_id})")
                        break
                
                # 키워드로 확인
                if not is_esp32:
                    for keyword in esp32_keywords:
                        if (keyword in description or 
                            keyword in manufacturer or 
                            keyword in hwid):
                            is_esp32 = True
                            logger.info(f"📱 ESP32 키워드 매칭: {port.device} ({keyword})")
                            break
                
                if is_esp32:
                    detected_ports.append({
                        "device": port.device,
                        "description": port.description,
                        "hwid": port.hwid,
                        "manufacturer": port.manufacturer
                    })
            
            logger.info(f"🔍 감지된 ESP32 후보: {len(detected_ports)}개")
            
            # 감지된 포트들에 연결 시도
            for i, port_info in enumerate(detected_ports):
                device_id = f"esp32_auto_{i}"
                port_device = port_info["device"]
                
                # 이미 등록된 포트인지 확인
                existing_device = None
                for dev_id, dev in self.devices.items():
                    if dev.serial_port == port_device:
                        existing_device = dev
                        device_id = dev_id
                        break
                
                if not existing_device:
                    # 새 디바이스 추가
                    self.add_device(
                        device_id=device_id,
                        serial_port=port_device,
                        device_type="gym_controller"
                    )
                    logger.info(f"➕ 새 ESP32 디바이스 추가: {device_id} @ {port_device}")
                
                # 연결 시도
                device = self.devices[device_id]
                if await self._connect_and_verify_esp32(device):
                    connected_count += 1
                    logger.info(f"✅ ESP32 연결 성공: {device_id} @ {port_device}")
                else:
                    logger.warning(f"❌ ESP32 연결 실패: {device_id} @ {port_device}")
                    # 연결 실패한 자동 감지 디바이스는 제거
                    if device_id.startswith("esp32_auto_"):
                        del self.devices[device_id]
            
            logger.info(f"🎯 ESP32 자동 연결 완료: {connected_count}/{len(detected_ports)}")
            self._last_scan_time = asyncio.get_event_loop().time()
            
            return connected_count
            
        except Exception as e:
            logger.error(f"ESP32 자동 스캔 오류: {e}")
            return 0
    
    async def _connect_and_verify_esp32(self, device: ESP32Device) -> bool:
        """ESP32 연결 및 검증
        
        Args:
            device: ESP32 디바이스 객체
            
        Returns:
            연결 및 검증 성공 여부
        """
        # 기본 연결 시도
        if not await self._connect_device(device):
            return False
        
        try:
            # ESP32인지 확인하기 위해 상태 요청
            status_cmd = self.protocol_handler.create_esp32_status_command()
            await self._send_raw_message(device, status_cmd)
            
            # 응답 대기 (3초)
            for _ in range(30):  # 100ms * 30 = 3초
                if device.serial_connection and device.serial_connection.in_waiting > 0:
                    try:
                        data = device.serial_connection.read(device.serial_connection.in_waiting)
                        response = data.decode('utf-8', errors='ignore').strip()
                        
                        # ESP32 응답인지 확인
                        if ('esp32' in response.lower() or 
                            'device_id' in response or
                            'message_type' in response):
                            logger.info(f"✅ ESP32 검증 성공: {device.device_id}")
                            return True
                            
                    except Exception as e:
                        logger.debug(f"ESP32 응답 읽기 오류: {e}")
                
                await asyncio.sleep(0.1)
            
            logger.warning(f"⚠️ ESP32 응답 없음: {device.device_id}")
            return True  # 연결은 되었으니 일단 유지
            
        except Exception as e:
            logger.error(f"ESP32 검증 오류: {device.device_id}, {e}")
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
        elif device.device_type == "gym_controller":
            # 통합 ESP32 디바이스 - 모터 명령 사용
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
        """모터 컨트롤러 명령 생성 - ESP32 JSON 호환"""
        # 새로운 ESP32는 JSON 명령을 받음
        if command == "OPEN_LOCKER":
            locker_id = kwargs.get("locker_id", "")
            duration = kwargs.get("duration_ms", 3000)
            return self.protocol_handler.create_esp32_locker_open_command(locker_id, duration)
        elif command == "GET_STATUS":
            return self.protocol_handler.create_esp32_status_command()
        elif command == "SET_AUTO_MODE":
            enabled = kwargs.get("enabled", True)
            return self.protocol_handler.create_esp32_auto_mode_command(enabled)
        elif command == "MOTOR_MOVE":
            revs = kwargs.get("revs", 1.0)
            rpm = kwargs.get("rpm", 60.0)
            accel = kwargs.get("accel", True)
            return self.protocol_handler.create_esp32_motor_command(revs, rpm, accel)
        else:
            # 기본 JSON 명령
            return self.protocol_handler.create_esp32_json_command(command, **kwargs)
    
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
            # 시리얼 데이터 읽기 (더 안정적인 방식)
            if device.serial_connection.in_waiting > 0:
                # 한 번에 읽을 바이트 수 제한 (버퍼 오버플로우 방지)
                max_read = min(device.serial_connection.in_waiting, 1024)
                data = device.serial_connection.read(max_read)
                device.read_buffer += data.decode('utf-8', errors='ignore')
                
                # 버퍼가 너무 커지면 일부 삭제 (메모리 보호)
                if len(device.read_buffer) > 4096:
                    device.read_buffer = device.read_buffer[-2048:]
                    logger.warning(f"ESP32 버퍼 크기 제한: {device.device_id}")
                
                # 완성된 메시지 처리 (줄바꿈으로 구분)
                while '\n' in device.read_buffer:
                    line, device.read_buffer = device.read_buffer.split('\n', 1)
                    line = line.strip()
                    
                    if line:
                        await self._process_received_message(device, line)
                
                # 줄바꿈 없이 JSON이 여러 개 붙어있는 경우 처리
                # JSON 형식: {...}로 시작하고 끝남
                while device.read_buffer.startswith('{'):
                    try:
                        # 완전한 JSON을 찾기
                        brace_count = 0
                        json_end = -1
                        for i, char in enumerate(device.read_buffer):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                        
                        if json_end > 0:
                            json_str = device.read_buffer[:json_end]
                            device.read_buffer = device.read_buffer[json_end:].lstrip()
                            await self._process_received_message(device, json_str)
                        else:
                            # 완전한 JSON이 아직 없음, 다음에 더 읽기
                            break
                    except Exception as e:
                        logger.error(f"ESP32 JSON 추출 오류: {device.device_id}, {e}")
                        # 버퍼 초기화
                        device.read_buffer = ""
                        break
                        
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
            # 센서 이벤트인지 확인
            if message.data.get("sensor_type") == "ir_sensor":
                event_type = "sensor_triggered"
            else:
                event_type = "device_status"
        elif message.type == MessageType.COMMAND_RESPONSE:
            # 모터 이벤트인지 확인
            if message.data.get("response_type") == "motor_event":
                event_type = "motor_completed"
            else:
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


async def create_auto_esp32_manager() -> ESP32Manager:
    """ESP32 자동 감지 및 연결이 포함된 Manager 생성
    
    Returns:
        연결된 ESP32들이 포함된 Manager
    """
    manager = ESP32Manager()
    
    logger.info("🚀 ESP32 자동 감지 및 연결 시작...")
    
    # 자동 스캔 및 연결
    connected_count = await manager.scan_and_connect_esp32_devices()
    
    if connected_count > 0:
        logger.info(f"✅ {connected_count}개 ESP32 디바이스 연결 완료")
        
        # 통신 시작
        await manager.start_communication()
        logger.info("📡 ESP32 통신 시작")
        
        return manager
    else:
        logger.warning("⚠️ 연결된 ESP32 디바이스 없음")
        
        # 기본 설정으로 폴백
        logger.info("🔄 기본 설정으로 폴백...")
        manager = create_default_esp32_manager()
        
        # 기본 설정으로 연결 시도
        if await manager.connect_all_devices():
            await manager.start_communication()
            logger.info("✅ 기본 설정으로 연결 성공")
        else:
            logger.warning("❌ 기본 설정으로도 연결 실패")
        
        return manager


async def test_esp32_auto_detection():
    """ESP32 자동 감지 테스트 함수"""
    print("🔍 ESP32 자동 감지 테스트 시작...")
    
    manager = await create_auto_esp32_manager()
    
    # 연결된 디바이스 목록 출력
    devices = manager.get_all_devices_status()
    print(f"\n📋 연결된 디바이스: {len(devices)}개")
    
    for device_id, status in devices.items():
        online = "🟢 온라인" if status.get("is_online") else "🔴 오프라인"
        port = status.get("serial_port", "unknown")
        device_type = status.get("device_type", "unknown")
        
        print(f"  • {device_id}: {online} @ {port} ({device_type})")
    
    # 간단한 상태 요청 테스트
    print("\n📊 상태 요청 테스트...")
    for device_id in devices.keys():
        if devices[device_id].get("is_online"):
            success = await manager.send_command(device_id, "GET_STATUS")
            result = "✅ 성공" if success else "❌ 실패"
            print(f"  • {device_id}: {result}")
    
    print("\n🛑 연결 해제...")
    await manager.disconnect_all_devices()
    print("✅ 테스트 완료")
