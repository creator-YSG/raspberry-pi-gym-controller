#!/bin/bash
# 라즈베리파이 락카키 대여기 키오스크 모드 실행 스크립트

echo "🏋️ 락카키 대여기 키오스크 모드 시작"
echo "=================================="

# 프로젝트 디렉토리로 이동
cd /home/pi/raspberry-pi-gym-controller

# Flask 서버를 백그라운드에서 시작
echo "🚀 Flask 서버 시작 중..."
python3 run.py --host 0.0.0.0 --port 5000 > logs/flask.log 2>&1 &
FLASK_PID=$!

# 서버가 시작될 때까지 대기
echo "⏳ 서버 시작 대기 중..."
sleep 10

# 서버 상태 확인
if curl -s http://localhost:5000 > /dev/null; then
    echo "✅ Flask 서버 시작 완료"
else
    echo "❌ Flask 서버 시작 실패"
    kill $FLASK_PID 2>/dev/null
    exit 1
fi

# X11 디스플레이 설정
export DISPLAY=:0

# 화면 보호기 비활성화
xset s off
xset -dpms
xset s noblank

# 마우스 커서 숨기기
unclutter -idle 1 -root &

# Chromium 브라우저를 키오스크 모드로 실행
echo "🖥️ 브라우저 키오스크 모드 시작..."
chromium-browser \
    --kiosk \
    --no-sandbox \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-web-security \
    --disable-features=TranslateUI \
    --disable-ipc-flooding-protection \
    --noerrdialogs \
    --start-fullscreen \
    --window-size=600,1024 \
    --app=http://localhost:5000 \
    2>/dev/null &

BROWSER_PID=$!

echo "✅ 키오스크 모드 실행 완료"
echo "Flask PID: $FLASK_PID"
echo "Browser PID: $BROWSER_PID"
echo ""
echo "종료하려면 Ctrl+Alt+T로 터미널을 열고 pkill chromium 실행"

# PID 파일 저장 (나중에 종료할 때 사용)
echo "$FLASK_PID" > /tmp/flask.pid
echo "$BROWSER_PID" > /tmp/browser.pid

# 브라우저가 종료될 때까지 대기
wait $BROWSER_PID

# 브라우저가 종료되면 Flask 서버도 종료
echo "🛑 키오스크 모드 종료 중..."
kill $FLASK_PID 2>/dev/null
rm -f /tmp/flask.pid /tmp/browser.pid

echo "✅ 종료 완료"
