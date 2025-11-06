#!/bin/bash
# 라즈베리파이 배포 및 재시작 스크립트

echo "🚀 배포 시작..."

# 1. 파일 동기화
echo "📦 파일 동기화 중..."
rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude 'venv/' --exclude '.git/' \
  /Users/yunseong-geun/Projects/raspberry-pi-gym-controller/ \
  raspberry-pi:/home/pi/gym-controller/

if [ $? -ne 0 ]; then
    echo "❌ 파일 동기화 실패"
    exit 1
fi

echo "✅ 파일 동기화 완료"

# 2. 모든 프로세스 종료
echo "🛑 기존 프로세스 종료 중..."
ssh raspberry-pi "sudo killall -9 python3 chromium-browser chromium 2>/dev/null; sleep 2"

echo "✅ 프로세스 종료 완료"

# 3. Chromium 캐시 삭제
echo "🗑️  Chromium 캐시 삭제 중..."
ssh raspberry-pi "rm -rf ~/.cache/chromium ~/.config/chromium 2>/dev/null"

echo "✅ 캐시 삭제 완료"

# 4. Flask 시작
echo "🐍 Flask 시작 중..."
ssh raspberry-pi "cd /home/pi/gym-controller && nohup python3 run.py > /tmp/flask_app.log 2>&1 < /dev/null &"

sleep 4

# 5. Flask 시작 확인
flask_pid=$(ssh raspberry-pi "pgrep -f 'python3 run.py'")
if [ -z "$flask_pid" ]; then
    echo "❌ Flask 시작 실패"
    ssh raspberry-pi "tail -30 /tmp/flask_app.log"
    exit 1
fi

echo "✅ Flask 시작 완료 (PID: $flask_pid)"

# 6. Chromium 시작
echo "🌐 Chromium 시작 중..."
ssh raspberry-pi "DISPLAY=:0 chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run --disable-cache http://localhost:5000 > /dev/null 2>&1 &"

sleep 2

# 7. Chromium 시작 확인
chrome_pid=$(ssh raspberry-pi "pgrep -f chromium-browser")
if [ -z "$chrome_pid" ]; then
    echo "❌ Chromium 시작 실패"
    exit 1
fi

echo "✅ Chromium 시작 완료 (PID: $chrome_pid)"

# 8. 최종 확인
echo ""
echo "======================================"
echo "✅ 배포 완료!"
echo "======================================"
echo "Flask PID: $flask_pid"
echo "Chromium PID: $chrome_pid"
echo ""
echo "로그 확인: ssh raspberry-pi 'tail -f /tmp/flask_app.log'"
echo ""


