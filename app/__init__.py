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
    from core.esp32_manager import create_auto_esp32_manager
    
    # ESP32 매니저를 앱 컨텍스트에 저장
    app.esp32_manager = None
    
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
        """바코드 스캔 이벤트 처리"""
        barcode = event_data.get("barcode", "")
        device_id = event_data.get("device_id", "unknown")
        
        app.logger.info(f"🔍 바코드 스캔: {barcode} (from {device_id})")
        
        # WebSocket으로 프론트엔드에 알림
        socketio.emit('barcode_scanned', {
            'barcode': barcode,
            'device_id': device_id,
            'timestamp': event_data.get('timestamp')
        })
    
    async def handle_sensor_triggered(event_data):
        """센서 이벤트 처리"""
        chip_idx = event_data.get("chip_idx", "?")
        pin = event_data.get("pin", "?")
        active = event_data.get("active", False)
        
        app.logger.info(f"📡 센서: Chip{chip_idx} Pin{pin} = {'ACTIVE' if active else 'INACTIVE'}")
        
        # WebSocket으로 센서 상태 전송
        socketio.emit('sensor_status', {
            'chip_idx': chip_idx,
            'pin': pin,
            'active': active,
            'timestamp': event_data.get('timestamp')
        })
    
    async def handle_motor_completed(event_data):
        """모터 완료 이벤트 처리"""
        action = event_data.get("action", "unknown")
        status = event_data.get("status", "unknown")
        
        app.logger.info(f"⚙️ 모터: {action} - {status}")
        
        # WebSocket으로 모터 상태 전송
        socketio.emit('motor_status', {
            'action': action,
            'status': status,
            'details': event_data.get('details', {}),
            'timestamp': event_data.get('timestamp')
        })
    
    # 이벤트 핸들러 등록
    esp32_manager.register_event_handler("barcode_scanned", handle_barcode_scanned)
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
