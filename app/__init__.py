"""
락카키 대여기 Flask 웹 애플리케이션

세로 모드 터치스크린 최적화된 키오스크 앱
"""

from flask import Flask
from flask_socketio import SocketIO
import logging
import os
from pathlib import Path

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
        active = event_data.get("active", False)
        raw_state = event_data.get("state", "HIGH")
        
        app.logger.info(f"📡 센서: Chip{chip_idx} Pin{pin} = {raw_state} ({'ACTIVE' if active else 'INACTIVE'})")
        
        # Chip+Pin 조합으로 센서 번호 매핑 (sensor_mapping.json 기반 역산)
        # 공식: sensor_num = (chip_idx * 16) + pin + 1을 역산
        chip_pin_to_sensor = {
            # Chip0 매핑 (센서 1~16번)
            (0,  0):  1,  # 센서  1번 → M03
            (0,  1):  2,  # 센서  2번 → M01
            (0,  2):  3,  # 센서  3번 → M02
            (0,  3):  4,  # 센서  4번 → M06
            (0,  4):  5,  # 센서  5번 → M07
            (0,  5):  6,  # 센서  6번 → M05
            (0,  6):  7,  # 센서  7번 → M04
            (0,  7):  8,  # 센서  8번 → M09
            (0,  8):  9,  # 센서  9번 → M10
            (0,  9): 10,  # 센서 10번 → M08
            (0, 10): 11,  # 센서 11번 → S02
            (0, 11): 12,  # 센서 12번 → S01
            (0, 12): 13,  # 센서 13번 → S07
            (0, 13): 14,  # 센서 14번 → S06
            (0, 14): 15,  # 센서 15번 → S05
            (0, 15): 16,  # 센서 16번 → S04
            
            # Chip1 매핑 (센서 17~30번)
            (1,  0): 17,  # 센서 17번 → M11
            (1,  1): 18,  # 센서 18번 → M13
            (1,  2): 19,  # 센서 19번 → M14
            (1,  3): 20,  # 센서 20번 → M12
            (1,  4): 21,  # 센서 21번 → M17
            (1,  5): 22,  # 센서 22번 → M15
            (1,  6): 23,  # 센서 23번 → M18
            (1,  7): 24,  # 센서 24번 → M16
            (1,  8): 25,  # 센서 25번 → M19
            (1,  9): 26,  # 센서 26번 → M20
            (1, 10): 27,  # 센서 27번 → S03
            (1, 11): 28,  # 센서 28번 → S10
            (1, 12): 29,  # 센서 29번 → S09
            (1, 13): 30,  # 센서 30번 → S08
            
            # Chip2 매핑 (센서 33~47번, 31~32번은 sensor_mapping.json에 없음)
            (2,  0): 33,  # 센서 33번 → M34
            (2,  1): 34,  # 센서 34번 → M35
            (2,  2): 35,  # 센서 35번 → M39
            (2,  3): 36,  # 센서 36번 → M38
            (2,  4): 37,  # 센서 37번 → M40
            (2,  5): 38,  # 센서 38번 → M21
            (2,  6): 39,  # 센서 39번 → M22
            (2,  7): 40,  # 센서 40번 → M23
            (2,  8): 41,  # 센서 41번 → M27
            (2,  9): 42,  # 센서 42번 → M26
            (2, 10): 43,  # 센서 43번 → M24
            (2, 11): 44,  # 센서 44번 → M25
            (2, 12): 45,  # 센서 45번 → M30
            (2, 13): 46,  # 센서 46번 → M29
            (2, 14): 47,  # 센서 47번 → M28
            
            # Chip3 매핑 (센서 49~63번, 48번은 sensor_mapping.json에 없음)
            (3,  0): 49,  # 센서 49번 → F01
            (3,  1): 50,  # 센서 50번 → F03
            (3,  2): 51,  # 센서 51번 → F02
            (3,  3): 52,  # 센서 52번 → F07
            (3,  4): 53,  # 센서 53번 → F06
            (3,  5): 54,  # 센서 54번 → F04
            (3,  6): 55,  # 센서 55번 → F05
            (3,  7): 56,  # 센서 56번 → F10
            (3,  8): 57,  # 센서 57번 → F09
            (3,  9): 58,  # 센서 58번 → F08
            (3, 10): 59,  # 센서 59번 → M31
            (3, 11): 60,  # 센서 60번 → M33
            (3, 12): 61,  # 센서 61번 → M36
            (3, 13): 62,  # 센서 62번 → M37
            (3, 14): 63,  # 센서 63번 → M32
        }
        
        # Chip+Pin 튜플로 센서 번호 조회
        sensor_num = chip_pin_to_sensor.get((chip_idx, pin), None)
        
        # 매핑되지 않은 핀 감지 시 경고
        if sensor_num is None:
            app.logger.warning(f"🔍 매핑되지 않은 핀 {pin} 감지됨!")
        
        app.logger.info(f"🔥 [DEBUG] 핀 {pin} -> 센서 {sensor_num} 매핑")
        
        if sensor_num:
            # 센서 이벤트 저장 (API에서 사용)
            from app.api.routes import add_sensor_event
            add_sensor_event(sensor_num, raw_state)
            app.logger.info(f"🔥 [DEBUG] 센서 이벤트 저장됨: 센서{sensor_num}, 상태{raw_state}")
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
