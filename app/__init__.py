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
    
    # DB 로그 핸들러 활성화 (모든 로그를 DB에 저장)
    try:
        from app.services.db_log_handler import setup_db_logging
        db_handler = setup_db_logging(db_path='instance/gym_system.db')
        # Flask 앱 로거에도 추가
        if db_handler:
            app.logger.addHandler(db_handler)
    except Exception as log_err:
        print(f"[WARNING] DB 로그 핸들러 설정 실패: {log_err}")
    
    # SocketIO 초기화
    #
    # NOTE:
    # - 기존 eventlet 모드는 MJPEG 스트림(OpenCV 인코딩)이 같은 이벤트루프를 오래 점유하면
    #   다른 HTTP API(/api/auth/face, /api/face/register 등)까지 응답이 멈추는 현상이 발생할 수 있음.
    # - 키오스크는 폴링 기반이므로 기본값을 threading으로 두고, 필요 시 환경변수로 변경.
    async_mode = os.environ.get("SOCKETIO_ASYNC_MODE", "threading")
    socketio.init_app(app, cors_allowed_origins="*", async_mode=async_mode)
    app.logger.info(f"🧵 SocketIO async_mode={async_mode}")
    
    # 블루프린트 등록
    register_blueprints(app)
    
    # 에러 핸들러 등록
    register_error_handlers(app)
    
    # 컨텍스트 프로세서 등록
    register_context_processors(app)
    
    # ESP32 자동 연결 (백그라운드)
    setup_esp32_connection(app)
    
    # 카메라 자동 시작 (모션 감지용)
    setup_camera_service(app)
    
    # Google Sheets 동기화 스케줄러 시작
    setup_sync_scheduler(app)
    
    # Flask 종료 시 DB 체크포인트 실행 (데이터 손실 방지)
    setup_shutdown_hook(app)
    
    app.logger.info("🚀 락카키 대여기 웹 애플리케이션 초기화 완료")
    
    return app


def setup_shutdown_hook(app):
    """Flask 종료 시 DB 체크포인트 실행"""
    import atexit
    import sqlite3
    
    def cleanup_on_exit():
        """앱 종료 시 정리 작업"""
        try:
            # WAL 체크포인트 실행
            db_path = 'instance/gym_system.db'
            conn = sqlite3.connect(db_path, timeout=5.0)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            print("[SHUTDOWN] DB WAL 체크포인트 완료")
        except Exception as e:
            print(f"[SHUTDOWN] DB 정리 오류: {e}")
    
    atexit.register(cleanup_on_exit)
    app.logger.info("종료 hook 등록 완료")


def setup_camera_service(app):
    """카메라 서비스 자동 시작 (모션 감지용)"""
    import threading
    
    def camera_init_worker():
        """카메라 초기화 워커 스레드"""
        try:
            # 잠시 대기 (앱 완전 초기화 후)
            import time
            time.sleep(2)
            
            from app.services.camera_service import get_camera_service
            camera_service = get_camera_service(use_picamera=True)
            
            if camera_service.start():
                app.camera_service = camera_service
                app.logger.info("📷 카메라 서비스 자동 시작 완료 (모션 감지 대기)")
            else:
                app.logger.warning("⚠️ 카메라 시작 실패 - 모션 감지 비활성화")
                app.camera_service = None
                
        except Exception as e:
            app.logger.error(f"❌ 카메라 초기화 실패: {e}")
            app.camera_service = None
    
    # 테스트 모드가 아닐 때만 카메라 시작
    if not app.config.get('TESTING', False):
        camera_thread = threading.Thread(target=camera_init_worker, daemon=True)
        camera_thread.start()
        app.logger.info("🚀 카메라 초기화 스레드 시작")


def setup_sync_scheduler(app):
    """Google Sheets 동기화 스케줄러 설정"""
    import threading
    from database.database_manager import DatabaseManager
    from app.services.sync_scheduler import init_scheduler
    
    def scheduler_init_worker():
        """스케줄러 초기화 워커 스레드"""
        try:
            # 잠시 대기 (앱 완전 초기화 후)
            import time
            time.sleep(3)
            
            with app.app_context():
                # DatabaseManager 초기화 및 연결
                db_manager = DatabaseManager()
                if not db_manager.connect():
                    app.logger.error("❌ DatabaseManager 연결 실패 - 스케줄러 시작 불가")
                    app.sync_scheduler = None
                    return
                
                # 스케줄러 초기화 및 시작
                scheduler = init_scheduler(db_manager, auto_start=True)
                
                if scheduler:
                    app.sync_scheduler = scheduler
                    app.logger.info("✅ Google Sheets 동기화 스케줄러 시작됨")
                else:
                    app.logger.warning("⚠️ Google Sheets 동기화 스케줄러 시작 실패 (오프라인 모드)")
                    app.sync_scheduler = None
                    
        except Exception as e:
            app.logger.error(f"❌ 동기화 스케줄러 초기화 실패: {e}")
            app.sync_scheduler = None
    
    # 테스트 모드가 아닐 때만 스케줄러 시작
    if not app.config.get('TESTING', False):
        scheduler_thread = threading.Thread(target=scheduler_init_worker, daemon=True)
        scheduler_thread.start()
        app.logger.info("🚀 동기화 스케줄러 초기화 스레드 시작")


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
    
    # 센서 폴링 큐 생성 (대여 중 센서 감지용)
    app.sensor_queue = queue.Queue(maxsize=10)
    
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
    
    # 하드코딩 센서 매핑 (DB 폴백용)
    # (addr, chip_idx, pin) → sensor_num
    HARDCODED_SENSOR_MAPPING = {
        # addr=0x26, Chip0 → 교직원 (S01-S10)
        ("0x26", 0, 1): 1, ("0x26", 0, 0): 2, ("0x26", 0, 6): 3, ("0x26", 0, 5): 4,
        ("0x26", 0, 4): 5, ("0x26", 0, 3): 6, ("0x26", 0, 2): 7, ("0x26", 0, 9): 8,
        ("0x26", 0, 8): 9, ("0x26", 0, 7): 10,
        # addr=0x23, Chip0 → 남성 (M01-M10)
        ("0x23", 0, 1): 11, ("0x23", 0, 2): 12, ("0x23", 0, 0): 13, ("0x23", 0, 6): 14,
        ("0x23", 0, 5): 15, ("0x23", 0, 3): 16, ("0x23", 0, 4): 17, ("0x23", 0, 9): 18,
        ("0x23", 0, 7): 19, ("0x23", 0, 8): 20,
        # addr=0x25, Chip1 → 남성 (M11-M20)
        ("0x25", 1, 0): 21, ("0x25", 1, 3): 22, ("0x25", 1, 1): 23, ("0x25", 1, 2): 24,
        ("0x25", 1, 5): 25, ("0x25", 1, 7): 26, ("0x25", 1, 4): 27, ("0x25", 1, 6): 28,
        ("0x25", 1, 8): 29, ("0x25", 1, 9): 30,
        # addr=0x26, Chip2 → 남성 (M21-M30, M34-M35, M38-M40)
        ("0x26", 2, 5): 31, ("0x26", 2, 6): 32, ("0x26", 2, 7): 33, ("0x26", 2, 10): 34,
        ("0x26", 2, 11): 35, ("0x26", 2, 9): 36, ("0x26", 2, 8): 37, ("0x26", 2, 14): 38,
        ("0x26", 2, 13): 39, ("0x26", 2, 12): 40, ("0x26", 2, 0): 44, ("0x26", 2, 1): 45,
        ("0x26", 2, 3): 48, ("0x26", 2, 2): 49, ("0x26", 2, 4): 50,
        # addr=0x24, Chip1 → 남성 (M31-M33, M36-M37)
        ("0x24", 1, 9): 41, ("0x24", 1, 7): 42, ("0x24", 1, 8): 43,
        ("0x24", 1, 6): 46, ("0x24", 1, 5): 47,
        # addr=0x27, Chip3 → 여성 (F01-F10)
        ("0x27", 3, 0): 51, ("0x27", 3, 1): 52, ("0x27", 3, 3): 53, ("0x27", 3, 2): 54,
        ("0x27", 3, 4): 55, ("0x27", 3, 5): 56, ("0x27", 3, 6): 57, ("0x27", 3, 8): 58,
        ("0x27", 3, 7): 59, ("0x27", 3, 9): 60,
    }
    
    async def handle_sensor_triggered(event_data):
        """센서 이벤트 처리"""
        app.logger.info(f"🔥 [DEBUG] 센서 이벤트 핸들러 호출됨! event_data: {event_data}")
        
        chip_idx = event_data.get("chip_idx", "?")
        pin = event_data.get("pin", "?")
        addr = event_data.get("addr", "?")
        active = event_data.get("active", False)
        raw_state = event_data.get("state", "HIGH")
        
        app.logger.info(f"📡 센서: Chip{chip_idx} Addr{addr} Pin{pin} = {raw_state} ({'ACTIVE' if active else 'INACTIVE'})")
        
        # DB에서 센서 번호 조회 (DB 우선, 실패 시 하드코딩 폴백)
        sensor_num = None
        try:
            from database.database_manager import DatabaseManager
            db_manager = DatabaseManager()
            if db_manager.connect():
                sensor_num = db_manager.get_sensor_num_from_hardware(addr, chip_idx, pin)
                if sensor_num:
                    app.logger.info(f"🔍 DB 매핑: addr={addr}, chip={chip_idx}, pin={pin} → sensor_num={sensor_num}")
        except Exception as db_error:
            app.logger.warning(f"⚠️ DB 센서 조회 오류: {db_error}")
        
        # DB에 없으면 하드코딩 폴백
        if sensor_num is None:
            sensor_num = HARDCODED_SENSOR_MAPPING.get((addr, chip_idx, pin))
            if sensor_num:
                app.logger.info(f"🔄 하드코딩 폴백: addr={addr}, chip={chip_idx}, pin={pin} → sensor_num={sensor_num}")
            else:
                app.logger.warning(f"🔍 매핑되지 않은 핀: addr={addr}, chip={chip_idx}, pin={pin}")
        
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
                'addr': addr,
                'chip_idx': chip_idx,
                'pin': pin,
                'state': raw_state,
                'active': active,
                'timestamp': event_data.get('timestamp')
            }
            try:
                queue_before = app.sensor_queue.qsize() if app.sensor_queue else -1
                app.sensor_queue.put_nowait(sensor_data)
                queue_after = app.sensor_queue.qsize() if app.sensor_queue else -1
                print(f"📦 [QUEUE] 센서 큐에 저장: 센서{sensor_num}, 상태{raw_state} | "
                      f"큐사이즈: {queue_before} → {queue_after} | queue_id={id(app.sensor_queue)}")
                app.logger.info(f"📦 [QUEUE] 센서 큐에 저장: 센서{sensor_num}, 상태{raw_state} | "
                               f"큐사이즈: {queue_before} → {queue_after}")
            except queue.Full:
                # 큐가 꽉 찼으면 가장 오래된 것 제거하고 새로운 것 추가
                try:
                    app.sensor_queue.get_nowait()
                    app.sensor_queue.put_nowait(sensor_data)
                    print(f"⚠️ 센서 큐가 가득 차서 오래된 데이터 제거 (센서{sensor_num})")
                except Exception as e:
                    print(f"❌ 센서 큐 오류 (Full 처리): {e}")
            except Exception as e:
                print(f"❌ 센서 큐 저장 오류: {e}, app.sensor_queue={getattr(app, 'sensor_queue', None)}")
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
