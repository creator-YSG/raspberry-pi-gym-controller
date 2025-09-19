#!/bin/bash
# 라즈베리파이 바탕화면에 락카키 대여기 바로가기 생성

DESKTOP_DIR="/home/pi/Desktop"
APP_DIR="/home/pi/gym-controller"
ICON_PATH="$APP_DIR/assets/locker-icon.png"

echo "🖥️ 바탕화면 바로가기 생성 중..."

# 바탕화면 디렉토리 확인
if [ ! -d "$DESKTOP_DIR" ]; then
    echo "❌ 바탕화면 디렉토리 없음: $DESKTOP_DIR"
    exit 1
fi

# 메인 앱 바로가기 생성
cat > "$DESKTOP_DIR/락카키대여기.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=락카키 대여기
Name[en]=Locker Key System
Comment=헬스장 락카키 대여/반납 시스템
Comment[en]=Gym Locker Key Rental System
Exec=lxterminal -e "cd $APP_DIR && python3 main.py"
Icon=$ICON_PATH
Terminal=false
Categories=Application;Utility;
StartupNotify=true
EOF

# 테스트 모드 바로가기 생성
cat > "$DESKTOP_DIR/락카키대여기-테스트.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=락카키 대여기 (테스트)
Name[en]=Locker Key System (Test)
Comment=테스트 모드로 실행
Comment[en]=Run in test mode
Exec=lxterminal -e "cd $APP_DIR && python3 main.py --test-mode --debug"
Icon=$ICON_PATH
Terminal=true
Categories=Application;Development;
StartupNotify=true
EOF

# 시스템 상태 확인 바로가기
cat > "$DESKTOP_DIR/시스템상태확인.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=시스템 상태 확인
Name[en]=System Status
Comment=ESP32 연결 및 시스템 상태 확인
Comment[en]=Check ESP32 connections and system status
Exec=lxterminal -e "cd $APP_DIR && python3 -c 'from core.esp32_manager import create_default_esp32_manager; import asyncio; asyncio.run(create_default_esp32_manager().connect_all_devices())'"
Icon=/usr/share/pixmaps/utilities-system-monitor.png
Terminal=true
Categories=Application;System;
StartupNotify=true
EOF

# WiFi 설정 바로가기
cat > "$DESKTOP_DIR/WiFi설정.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=WiFi 설정
Name[en]=WiFi Settings
Comment=무선 네트워크 연결 설정
Comment[en]=Wireless network connection settings
Exec=sudo raspi-config
Icon=/usr/share/pixmaps/network-wireless.png
Terminal=true
Categories=Application;Settings;
StartupNotify=true
EOF

# 구글시트 연동 설정 바로가기
cat > "$DESKTOP_DIR/구글시트연동.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=구글시트 연동 설정
Name[en]=Google Sheets Setup
Comment=구글시트 인증 및 연동 설정
Comment[en]=Google Sheets authentication and integration setup
Exec=lxterminal -e "cd $APP_DIR && python3 scripts/setup_google_sheets.py"
Icon=/usr/share/pixmaps/web-browser.png
Terminal=true
Categories=Application;Settings;
StartupNotify=true
EOF

# 권한 설정
chmod +x "$DESKTOP_DIR"/*.desktop

echo "✅ 바탕화면 바로가기 생성 완료!"
echo ""
echo "📱 생성된 바로가기:"
echo "  • 락카키대여기.desktop - 메인 앱 실행"
echo "  • 락카키대여기-테스트.desktop - 테스트 모드"
echo "  • 시스템상태확인.desktop - ESP32 연결 확인"
echo "  • WiFi설정.desktop - 네트워크 설정"
echo "  • 구글시트연동.desktop - 구글시트 설정"
echo ""
echo "🖱️ 바탕화면에서 더블클릭으로 실행하세요!"
