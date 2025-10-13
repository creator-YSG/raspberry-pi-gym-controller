#!/bin/bash
# 키오스크 모드 설정/해제 스크립트

APP_DIR="/home/pi/gym-controller"
AUTOSTART_DIR="/home/pi/.config/autostart"

show_menu() {
    echo "🖥️ 락카키 대여기 키오스크 모드 설정"
    echo "=================================="
    echo ""
    echo "현재 모드 확인 중..."
    
    if [ -f "$AUTOSTART_DIR/locker-kiosk.desktop" ]; then
        echo "✅ 키오스크 모드: 활성화됨"
        echo "   (부팅 시 앱이 자동으로 전체화면 실행)"
    else
        echo "📱 일반 모드: 활성화됨" 
        echo "   (바탕화면에서 수동 실행)"
    fi
    
    echo ""
    echo "🔧 설정 옵션:"
    echo "1) 키오스크 모드 활성화 (자동 시작 + 전체화면)"
    echo "2) 일반 모드로 전환 (수동 시작)"
    echo "3) 현재 설정 확인"
    echo "4) 종료"
    echo ""
}

enable_kiosk_mode() {
    echo "🔄 키오스크 모드 활성화 중..."
    
    # autostart 디렉토리 생성
    mkdir -p "$AUTOSTART_DIR"
    
    # 키오스크 모드 autostart 파일 생성
    cat > "$AUTOSTART_DIR/locker-kiosk.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Locker Kiosk
Exec=/bin/bash -c 'sleep 10 && cd $APP_DIR && python3 main.py'
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
    
    # 화면 보호기 및 절전 모드 비활성화
    cat > "$AUTOSTART_DIR/disable-screensaver.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Disable Screensaver
Exec=/bin/bash -c 'xset s off && xset -dpms && xset s noblank'
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
    
    echo "✅ 키오스크 모드 활성화 완료!"
    echo ""
    echo "📋 설정된 기능:"
    echo "  • 부팅 시 10초 후 앱 자동 실행"
    echo "  • 화면 보호기 비활성화"
    echo "  • 절전 모드 비활성화"
    echo ""
    echo "🔄 재부팅 후 적용됩니다."
}

disable_kiosk_mode() {
    echo "🔄 일반 모드로 전환 중..."
    
    # autostart 파일들 제거
    rm -f "$AUTOSTART_DIR/locker-kiosk.desktop"
    rm -f "$AUTOSTART_DIR/disable-screensaver.desktop"
    
    echo "✅ 일반 모드로 전환 완료!"
    echo ""
    echo "📋 현재 상태:"
    echo "  • 수동 실행 모드 (바탕화면 바로가기 사용)"
    echo "  • 화면 보호기 활성화"
    echo "  • 표준 절전 모드"
    echo ""
    echo "🔄 재부팅 후 적용됩니다."
}

check_status() {
    echo "🔍 현재 시스템 상태"
    echo "=================="
    echo ""
    
    # 키오스크 모드 확인
    if [ -f "$AUTOSTART_DIR/locker-kiosk.desktop" ]; then
        echo "🖥️ 모드: 키오스크 모드"
        echo "📁 Autostart 파일: 존재함"
    else
        echo "🖥️ 모드: 일반 모드"  
        echo "📁 Autostart 파일: 없음"
    fi
    
    # 앱 디렉토리 확인
    if [ -d "$APP_DIR" ]; then
        echo "📂 앱 디렉토리: 존재함 ($APP_DIR)"
    else
        echo "📂 앱 디렉토리: 없음 ($APP_DIR)"
    fi
    
    # Python 앱 확인
    if [ -f "$APP_DIR/main.py" ]; then
        echo "🐍 메인 앱: 존재함"
    else
        echo "🐍 메인 앱: 없음"
    fi
    
    # 네트워크 상태
    if ping -c 1 google.com &> /dev/null; then
        echo "🌐 인터넷 연결: 정상"
    else
        echo "🌐 인터넷 연결: 없음"
    fi
    
    # USB 포트 확인
    echo "🔌 USB 시리얼 포트:"
    if ls /dev/ttyUSB* 2>/dev/null; then
        echo "   ESP32 디바이스 감지됨"
    else
        echo "   ESP32 디바이스 없음"
    fi
}

main() {
    while true; do
        clear
        show_menu
        
        read -p "선택하세요 (1-4): " choice
        
        case $choice in
            1)
                echo ""
                enable_kiosk_mode
                read -p "👆 Enter 키를 눌러 계속..."
                ;;
            2)
                echo ""
                disable_kiosk_mode
                read -p "👆 Enter 키를 눌러 계속..."
                ;;
            3)
                echo ""
                check_status
                read -p "👆 Enter 키를 눌러 계속..."
                ;;
            4)
                echo "👋 설정을 종료합니다."
                exit 0
                ;;
            *)
                echo "❌ 올바른 번호를 선택하세요 (1-4)"
                read -p "👆 Enter 키를 눌러 계속..."
                ;;
        esac
    done
}

# 권한 확인
if [ "$EUID" -eq 0 ]; then
    echo "❌ root 권한으로 실행하지 마세요"
    echo "일반 사용자(pi)로 실행해주세요"
    exit 1
fi

main
