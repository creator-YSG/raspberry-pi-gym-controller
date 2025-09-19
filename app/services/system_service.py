"""
시스템 관리 서비스
"""

import psutil
import subprocess
from datetime import datetime
from typing import Dict, List


class SystemService:
    """시스템 상태 및 관리 비즈니스 로직"""
    
    def __init__(self):
        self.esp32_manager = None
        self.google_sheets = None
        # TODO: 의존성 주입
    
    def get_system_status(self) -> Dict:
        """전체 시스템 상태 조회"""
        try:
            return {
                'system': self._get_system_info(),
                'esp32': self._get_esp32_status(),
                'google_sheets': self._get_google_sheets_status(),
                'lockers': self._get_locker_status(),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"시스템 상태 조회 오류: {e}")
            return {
                'error': '시스템 상태 조회 중 오류가 발생했습니다.',
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_system_info(self) -> Dict:
        """시스템 정보"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'status': 'normal',
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': round(memory.used / (1024**3), 1),
                'memory_total_gb': round(memory.total / (1024**3), 1),
                'disk_percent': disk.percent,
                'disk_used_gb': round(disk.used / (1024**3), 1),
                'disk_total_gb': round(disk.total / (1024**3), 1),
                'uptime': self._get_uptime()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _get_esp32_status(self) -> Dict:
        """ESP32 연결 상태"""
        try:
            # TODO: 실제 ESP32 매니저에서 상태 조회
            return {
                'barcode_scanner': {
                    'connected': True,
                    'port': '/dev/ttyUSB0',
                    'last_seen': '2분 전'
                },
                'motor_controller_1': {
                    'connected': True,
                    'port': '/dev/ttyUSB1',
                    'last_seen': '1분 전'
                },
                'motor_controller_2': {
                    'connected': False,
                    'port': '/dev/ttyUSB2',
                    'last_seen': '10분 전',
                    'error': '연결 끊김'
                }
            }
            
        except Exception as e:
            return {
                'error': f'ESP32 상태 조회 오류: {e}'
            }
    
    def _get_google_sheets_status(self) -> Dict:
        """구글시트 연동 상태"""
        try:
            # TODO: 실제 구글시트 매니저에서 상태 조회
            return {
                'connected': True,
                'last_sync': '5분 전',
                'member_count': 150,
                'rental_count': 23,
                'sync_interval': '30초'
            }
            
        except Exception as e:
            return {
                'connected': False,
                'error': f'구글시트 상태 조회 오류: {e}'
            }
    
    def _get_locker_status(self) -> Dict:
        """락카 현황"""
        try:
            from app.services.locker_service import LockerService
            locker_service = LockerService()
            
            # A, B 구역 락카 현황
            a_lockers = locker_service.get_all_lockers('A')
            b_lockers = locker_service.get_all_lockers('B')
            
            total_count = len(a_lockers) + len(b_lockers)
            available_count = len([l for l in a_lockers + b_lockers if l.is_available])
            occupied_count = total_count - available_count
            
            return {
                'total': total_count,
                'available': available_count,
                'occupied': occupied_count,
                'occupancy_rate': round((occupied_count / total_count) * 100, 1) if total_count > 0 else 0,
                'zones': {
                    'A': {
                        'total': len(a_lockers),
                        'available': len([l for l in a_lockers if l.is_available])
                    },
                    'B': {
                        'total': len(b_lockers),
                        'available': len([l for l in b_lockers if l.is_available])
                    }
                }
            }
            
        except Exception as e:
            return {
                'error': f'락카 현황 조회 오류: {e}'
            }
    
    def _get_uptime(self) -> str:
        """시스템 가동 시간"""
        try:
            uptime_seconds = psutil.boot_time()
            uptime_delta = datetime.now() - datetime.fromtimestamp(uptime_seconds)
            
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if days > 0:
                return f"{days}일 {hours}시간 {minutes}분"
            elif hours > 0:
                return f"{hours}시간 {minutes}분"
            else:
                return f"{minutes}분"
                
        except Exception:
            return "알 수 없음"
    
    def reconnect_esp32(self) -> Dict:
        """ESP32 재연결"""
        try:
            # TODO: 실제 ESP32 재연결 로직
            return {
                'success': True,
                'message': 'ESP32 재연결을 시도했습니다.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'ESP32 재연결 실패: {e}'
            }
    
    def sync_google_sheets(self) -> Dict:
        """구글시트 동기화"""
        try:
            # TODO: 실제 구글시트 동기화 로직
            return {
                'success': True,
                'message': '구글시트 동기화가 완료되었습니다.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'구글시트 동기화 실패: {e}'
            }
    
    def restart_system(self) -> Dict:
        """시스템 재시작"""
        try:
            # 실제 운영에서는 주의해서 사용
            subprocess.Popen(['sudo', 'reboot'])
            return {
                'success': True,
                'message': '시스템 재시작을 시작합니다.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'시스템 재시작 실패: {e}'
            }
    
    def get_recent_logs(self, lines: int = 50) -> Dict:
        """최근 로그 조회"""
        try:
            # 시스템 로그 조회
            result = subprocess.run(
                ['sudo', 'journalctl', '-n', str(lines), '--no-pager'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                logs = result.stdout.split('\n')
                return {
                    'success': True,
                    'logs': logs[-lines:] if len(logs) > lines else logs
                }
            else:
                return {
                    'success': False,
                    'message': '로그 조회 실패'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'로그 조회 오류: {e}'
            }
