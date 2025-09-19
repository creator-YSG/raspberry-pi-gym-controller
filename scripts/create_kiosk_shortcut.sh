#!/bin/bash
# 라즈베리파이 데스크톱에 락카키 대여기 바로가기 생성

DESKTOP_DIR="$HOME/Desktop"
SCRIPT_DIR="/home/pi/gym-controller/scripts"

echo "🖥️ 데스크톱 바로가기 생성 중..."

# 데스크톱 디렉토리 생성 (없으면)
mkdir -p "$DESKTOP_DIR"

# 락카키 대여기 실행 바로가기
cat > "$DESKTOP_DIR/락카키대여기.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=락카키 대여기
Name[en]=Locker Key Rental System
Comment=헬스장 락카키 대여 키오스크 앱
Comment[en]=Gym locker key rental kiosk application
Icon=applications-games
Exec=lxterminal -e "cd /home/pi/gym-controller && ./scripts/start_kiosk.sh"
Terminal=false
StartupNotify=true
Categories=Application;
EOF

# 락카키 대여기 종료 바로가기
cat > "$DESKTOP_DIR/락카키대여기종료.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=락카키 대여기 종료
Name[en]=Stop Locker System
Comment=락카키 대여기 키오스크 모드 종료
Comment[en]=Stop locker rental kiosk mode
Icon=application-exit
Exec=lxterminal -e "/home/pi/gym-controller/scripts/stop_kiosk.sh && read -p '엔터를 눌러 창을 닫으세요...'"
Terminal=false
StartupNotify=true
Categories=Application;
EOF

# 실행 권한 부여
chmod +x "$DESKTOP_DIR/락카키대여기.desktop"
chmod +x "$DESKTOP_DIR/락카키대여기종료.desktop"

echo "✅ 데스크톱 바로가기 생성 완료"
echo "📱 바로가기:"
echo "  • 락카키대여기.desktop - 키오스크 모드 실행"
echo "  • 락카키대여기종료.desktop - 키오스크 모드 종료"
