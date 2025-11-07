"""
락카키 대여기 Flask 웹 애플리케이션

세로 모드 터치스크린 최적화된 키오스크 앱
"""

from flask import Flask
from flask_socketio import SocketIO
import logging
import os
from pathlib import Path
import queue

# SocketIO 인스턴스 (전역)
socketio = SocketIO()


def create_app(config_name='default'):
    """Flask 애플리케이션 팩토리"""
    
    app = Flask(__name__)
    
    # 기본 설정
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
        DEBUG=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true',
        TESTING=False,
        
        # 터치스크린 최적화 설정
        SEND_FILE_MAX_AGE_DEFAULT=0,  # 캐시 비활성화 (개발용)
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB 업로드 제한
        
        # 키오스크 모드 설정
        KIOSK_MODE=True,
        PORTRAIT_MODE=True,
        SCREEN_WIDTH=600,
        SCREEN_HEIGHT=1024,
        
        # ESP32 통신 설정  
        ESP32_TIMEOUT=5.0,
        ESP32_RETRY_COUNT=3,
        
        # 구글시트 설정
        GOOGLE_SHEETS_UPDATE_INTERVAL=30,  # 30초마다 동기화
    )
    
    # 환경별 설정 로드
    if config_name == 'development':
        app.config.update(
            DEBUG=True,
            TEMPLATES_AUTO_RELOAD=True,
        )
    elif config_name == 'production':
        app.config.update(
            DEBUG=False,
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
        )
    
    # 로깅 설정
    setup_logging(app)
    
    # SocketIO 초기화
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # 블루프린트 등록
    register_blueprints(app)
    
    # 에러 핸들러 등록
    register_error_handlers(app)
    
    # 컨텍스트 프로세서 등록
    register_context_processors(app)
    
    # ESP32 자동 연결 (백그라운드)
    setup_esp32_connection(app)
    
    app.logger.info("🚀 락카키 대여기 웹 애플리케이션 초기화 완료")
    
    return app


def setup_esp32_connection(app):
    """ESP32 자동 연결 설정"""
    import asyncio
    import threading
    import queue
    from core.esp32_manager import create_auto_esp32_manager
    
    # ESP32 매니저를 앱 컨텍스트에 저장
    app.esp32_manager = None
    
    # 바코드/NFC 폴링 큐 생성
    app.barcode_queue = queue.Queue(maxsize=10)
    
    def esp32_connection_worker():
        """ESP32 연결 워커 스레드"""
        try:
            app.logger.info("🔍 ESP32 자동 연결 시작...")
            
            # 새 이벤트 루프 생성 (스레드용)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # ESP32 자동 연결
            manager = loop.run_until_complete(create_auto_esp32_manager())
            app.esp32_manager = manager
            
            app.logger.info("✅ ESP32 연결 완료")
            
            # 이벤트 핸들러 등록
            setup_esp32_event_handlers(app, manager)
            
            # 🔥 핵심: 이벤트 루프를 계속 실행하여 시리얼 데이터 읽기 유지
            app.logger.info("🔄 ESP32 백그라운드 통신 루프 시작")
            loop.run_forever()
            
        except Exception as e:
            app.logger.error(f"❌ ESP32 연결 실패: {e}")
            app.esp32_manager = None
    
    # 백그라운드 스레드에서 ESP32 연결
    if not app.config.get('TESTING', False):
        esp32_thread = threading.Thread(target=esp32_connection_worker, daemon=True)
        esp32_thread.start()
        app.logger.info("🚀 ESP32 연결 스레드 시작")


def setup_esp32_event_handlers(app, esp32_manager):
    """ESP32 이벤트 핸들러 설정"""
    
    async def handle_barcode_scanned(event_data):
        """바코드 스캔 이벤트 처리 - 폴링 방식"""
        barcode = event_data.get("barcode", "")
        device_id = event_data.get("device_id", "unknown")
        
        app.logger.info(f"🔍 바코드 스캔: {barcode} (from {device_id})")
        
        # 바코드 큐에 추가 (폴링 방식)
        try:
            import queue
            barcode_queue = getattr(app, 'barcode_queue', None)
            if barcode_queue:
                barcode_queue.put_nowait({
                    'type': 'barcode',
                    'barcode': barcode,
                    'device_id': device_id
                })
                app.logger.info(f"✅ 바코드를 큐에 추가: {barcode}")
        except queue.Full:
            app.logger.warning("⚠️ 바코드 큐가 가득 참")
        except Exception as e:
            app.logger.error(f"❌ 바코드 큐 추가 오류: {e}")
    
    async def handle_sensor_triggered(event_data):
        """센서 이벤트 처리"""
        app.logger.info(f"🔥 [DEBUG] 센서 이벤트 핸들러 호출됨! event_data: {event_data}")
        
        chip_idx = event_data.get("chip_idx", "?")
        pin = event_data.get("pin", "?")
        addr = event_data.get("addr", "?")
        active = event_data.get("active", False)
        raw_state = event_data.get("state", "HIGH")
        
        app.logger.info(f"📡 센서: Chip{chip_idx} Addr{addr} Pin{pin} = {raw_state} ({'ACTIVE' if active else 'INACTIVE'})")
        
        # 하드코딩된 센서 매핑 (2025-11-07 실제 테스트 기준)
        chip_addr_pin_to_sensor = {
            # addr=0x26, Chip0 → 교직원 (S01-S10)
            ("0x26", 0,  1):  1,   # S01
            ("0x26", 0,  0):  2,   # S02
            ("0x26", 0,  6):  3,   # S03
            ("0x26", 0,  5):  4,   # S04
            ("0x26", 0,  4):  5,   # S05
            ("0x26", 0,  3):  6,   # S06
            ("0x26", 0,  2):  7,   # S07
            ("0x26", 0,  9):  8,   # S08
            ("0x26", 0,  8):  9,   # S09
            ("0x26", 0,  7): 10,   # S10
            
            # addr=0x23, Chip0 → 남성 (M01-M10)
            ("0x23", 0,  1): 11,   # M01
            ("0x23", 0,  2): 12,   # M02
            ("0x23", 0,  0): 13,   # M03
            ("0x23", 0,  6): 14,   # M04
            ("0x23", 0,  5): 15,   # M05
            ("0x23", 0,  3): 16,   # M06
            ("0x23", 0,  4): 17,   # M07
            ("0x23", 0,  9): 18,   # M08
            ("0x23", 0,  7): 19,   # M09
            ("0x23", 0,  8): 20,   # M10
            
            # addr=0x25, Chip1 → 남성 (M11-M20)
            ("0x25", 1,  0): 21,   # M11
            ("0x25", 1,  3): 22,   # M12
            ("0x25", 1,  1): 23,   # M13
            ("0x25", 1,  2): 24,   # M14
            ("0x25", 1,  5): 25,   # M15
            ("0x25", 1,  7): 26,   # M16
            ("0x25", 1,  4): 27,   # M17
            ("0x25", 1,  6): 28,   # M18
            ("0x25", 1,  8): 29,   # M19
            ("0x25", 1,  9): 30,   # M20
            
            # addr=0x26, Chip2 → 남성 (M21-M30, M34-M35, M38-M40)
            ("0x26", 2,  5): 31,   # M21
            ("0x26", 2,  6): 32,   # M22
            ("0x26", 2,  7): 33,   # M23
            ("0x26", 2, 10): 34,   # M24
            ("0x26", 2, 11): 35,   # M25
            ("0x26", 2,  9): 36,   # M26
            ("0x26", 2,  8): 37,   # M27
            ("0x26", 2, 14): 38,   # M28
            ("0x26", 2, 13): 39,   # M29
            ("0x26", 2, 12): 40,   # M30
            ("0x26", 2,  0): 44,   # M34
            ("0x26", 2,  1): 45,   # M35
            ("0x26", 2,  3): 48,   # M38
            ("0x26", 2,  2): 49,   # M39
            ("0x26", 2,  4): 50,   # M40
            
            # addr=0x27, Chip3 → 남성 (M31-M33, M36-M37) + 여성 (F01-F10)
            ("0x27", 3, 10): 41,   # M31
            ("0x27", 3, 14): 42,   # M32
            ("0x27", 3, 11): 43,   # M33
            ("0x27", 3, 12): 46,   # M36
            ("0x27", 3, 13): 47,   # M37
            ("0x27", 3,  0): 51,   # F01
            ("0x27", 3,  1): 52,   # F03
            ("0x27", 3,  2): 53,   # F02
            ("0x27", 3,  3): 54,   # F07
            ("0x27", 3,  4): 55,   # F06
            ("0x27", 3,  5): 56,   # F04
            ("0x27", 3,  6): 57,   # F05
            ("0x27", 3,  7): 58,   # F10
            ("0x27", 3,  8): 59,   # F09
            ("0x27", 3,  9): 60,   # F08
        }
        
        # Addr+Chip+Pin 튜플로 센서 번호 조회
        sensor_num = chip_addr_pin_to_sensor.get((addr, chip_idx, pin), None)
        
        # 매핑되지 않은 핀 감지 시 경고
        if sensor_num is None:
            app.logger.warning(f"🔍 매핑되지 않은 핀 {pin} 감지됨!")
        
        app.logger.info(f"🔥 [DEBUG] 핀 {pin} -> 센서 {sensor_num} 매핑")
        
        if sensor_num:
            # 센서 이벤트 저장 (API에서 사용) - Flask 컨텍스트에서 실행
            from app.api.routes import add_sensor_event
            with app.app_context():
                add_sensor_event(sensor_num, raw_state)
            app.logger.info(f"🔥 [DEBUG] 센서 이벤트 저장됨: 센서{sensor_num}, 상태{raw_state}")
            
            # 센서 큐에 저장 (폴링용)
            sensor_data = {
                'sensor_num': sensor_num,
                'chip_idx': chip_idx,
                'pin': pin,
                'state': raw_state,
                'active': active,
                'timestamp': event_data.get('timestamp')
            }
            try:
                sensor_queue.put_nowait(sensor_data)
                app.logger.info(f"📦 센서 큐에 저장: 센서{sensor_num}, 상태{raw_state}")
            except queue.Full:
                # 큐가 꽉 찼으면 가장 오래된 것 제거하고 새로운 것 추가
                try:
                    sensor_queue.get_nowait()
                    sensor_queue.put_nowait(sensor_data)
                    app.logger.warning(f"⚠️ 센서 큐가 가득 차서 오래된 데이터 제거")
                except:
                    pass
        else:
            app.logger.warning(f"🔥 [DEBUG] 알 수 없는 핀 번호: {pin}")
        
        # WebSocket으로 센서 상태 전송 (호환성 유지)
        socketio.emit('esp32_event', {
            'event_type': 'sensor_triggered',
            'data': {
                'chip_idx': chip_idx,
                'pin': pin,
                'active': active,
                'raw': raw_state,
                'sensor_num': sensor_num,
                'timestamp': event_data.get('timestamp')
            }
        })
    
    async def handle_nfc_scanned(event_data):
        """NFC 스캔 이벤트 처리 - 폴링 방식"""
        nfc_uid = event_data.get("nfc_uid", "")
        device_id = event_data.get("device_id", "unknown")
        
        app.logger.info(f"🔖 NFC 스캔: {nfc_uid} (from {device_id})")
        
        # 바코드 큐에 NFC: 접두사를 붙여서 추가 (폴링 방식)
        try:
            import queue
            barcode_queue = getattr(app, 'barcode_queue', None)
            if barcode_queue:
                barcode_queue.put_nowait({
                    'type': 'nfc',
                    'data': f"NFC:{nfc_uid}",
                    'raw_uid': nfc_uid,
                    'device_id': device_id
                })
                app.logger.info(f"✅ NFC를 바코드 큐에 추가: NFC:{nfc_uid}")
        except queue.Full:
            app.logger.warning("⚠️ 바코드 큐가 가득 참")
        except Exception as e:
            app.logger.error(f"❌ NFC 큐 추가 오류: {e}")
    
    async def handle_motor_completed(event_data):
        """모터 완료 이벤트 처리"""
        action = event_data.get("action", "unknown")
        status = event_data.get("status", "unknown")
        
        app.logger.info(f"⚙️ 모터: {action} - {status}")
        
        # WebSocket으로 모터 상태 전송
        socketio.emit('esp32_event', {
            'event_type': 'motor_completed',
            'data': {
                'action': action,
                'status': status,
                'details': event_data.get('details', {}),
                'timestamp': event_data.get('timestamp')
            }
        })
    
    # 이벤트 핸들러 등록
    esp32_manager.register_event_handler("barcode_scanned", handle_barcode_scanned)
    esp32_manager.register_event_handler("nfc_scanned", handle_nfc_scanned)
    esp32_manager.register_event_handler("sensor_triggered", handle_sensor_triggered)
    esp32_manager.register_event_handler("motor_completed", handle_motor_completed)
    
    app.logger.info("📡 ESP32 이벤트 핸들러 등록 완료")


def setup_logging(app):
    """로깅 설정"""
    if not app.debug and not app.testing:
        # 프로덕션 로깅
        log_dir = Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / 'locker_system.log')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)


def register_blueprints(app):
    """블루프린트 등록"""
    
    # 메인 페이지 라우트
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    # API 라우트  
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # WebSocket 이벤트
    from app import events


def register_error_handlers(app):
    """에러 핸들러 등록"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        app.logger.error(f'서버 오류: {error}')
        return render_template('errors/500.html'), 500


def register_context_processors(app):
    """템플릿 컨텍스트 프로세서 등록"""
    
    @app.context_processor
    def inject_config():
        """모든 템플릿에 설정값 주입"""
        return {
            'KIOSK_MODE': app.config['KIOSK_MODE'],
            'PORTRAIT_MODE': app.config['PORTRAIT_MODE'], 
            'SCREEN_WIDTH': app.config['SCREEN_WIDTH'],
            'SCREEN_HEIGHT': app.config['SCREEN_HEIGHT'],
        }
