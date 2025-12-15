#!/usr/bin/env python3
"""
락카키 대여기 Flask 웹 애플리케이션 실행 파일

600x1024 세로 모드 터치스크린 최적화
"""

import os
import sys
import argparse
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app import create_app, socketio


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='락카키 대여기 웹 애플리케이션')
    parser.add_argument('--host', default='0.0.0.0', help='호스트 주소')
    parser.add_argument('--port', type=int, default=5000, help='포트 번호')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')
    parser.add_argument('--config', default='default', help='설정 환경 (development, production)')
    
    args = parser.parse_args()
    
    # 환경 변수 설정
    os.environ['FLASK_ENV'] = 'development' if args.debug else 'production'
    os.environ['FLASK_DEBUG'] = '1' if args.debug else '0'
    
    # Flask 앱 생성
    config_name = 'development' if args.debug else args.config
    app = create_app(config_name)
    
    # 시작 시간 기록
    from datetime import datetime
    app.config['START_TIME'] = datetime.now().isoformat()
    
    print("🏋️ 락카키 대여기 웹 애플리케이션")
    print("=" * 50)
    print(f"📱 모드: {'개발' if args.debug else '프로덕션'}")
    print(f"🌐 주소: http://{args.host}:{args.port}")
    print(f"📺 화면: 600x1024 세로 모드")
    print(f"🔧 설정: {config_name}")
    print("=" * 50)
    
    # 🆕 시스템 통합 정보 업로드 (운동복 대여기와 통신용)
    try:
        from app.services.integration_sync import IntegrationSync
        sync = IntegrationSync()
        if sync.upload_locker_api_info():
            print(f"🔗 통합 시트 업로드 완료: {sync.get_local_ip()}:5000")
        else:
            print("⚠️  통합 시트 업로드 실패 (계속 진행)")
    except Exception as e:
        print(f"⚠️  통합 시트 업로드 오류: {e} (계속 진행)")
    
    print("=" * 50)
    
    try:
        # SocketIO 서버 실행
        socketio.run(
            app,
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=args.debug,
            log_output=True
        )
    except KeyboardInterrupt:
        print("\n👋 애플리케이션 종료")
    except Exception as e:
        print(f"❌ 실행 오류: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
