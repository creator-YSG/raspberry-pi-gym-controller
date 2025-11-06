#!/bin/bash

# 락카키 대여기 키오스크 완전 재시작 스크립트
# 용도: Flask 서버와 Chromium 키오스크를 안정적으로 재시작 (SSH 원격 실행)

RASPBERRY_PI="raspberry-pi"

echo "========================================"
echo "🔄 락카키 대여기 완전 재시작"
echo "시작 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

echo "[$(date '+%H:%M:%S')] 1️⃣ 기존 프로세스 종료 중..."

# 현재 프로세스 개수 확인
FLASK_COUNT=$(ssh $RASPBERRY_PI "pgrep -f 'python3 run.py' | wc -l")
CHROMIUM_COUNT=$(ssh $RASPBERRY_PI "pgrep chromium | wc -l")
echo "[$(date '+%H:%M:%S')]    - 종료 전 상태: Flask $FLASK_COUNT개, Chromium $CHROMIUM_COUNT개"

# Flask 서버 종료
ssh $RASPBERRY_PI "killall -9 python3 2>/dev/null"
echo "[$(date '+%H:%M:%S')]    - Flask 서버 종료"

# Chromium 브라우저 완전 종료 (모든 관련 프로세스)
ssh $RASPBERRY_PI "killall -9 chromium chromium-browser 2>/dev/null"
echo "[$(date '+%H:%M:%S')]    - Chromium 브라우저 종료"

echo "[$(date '+%H:%M:%S')] ⏳ 프로세스 완전 종료 대기 (2초)..."
sleep 2

# 종료 확인
REMAINING_FLASK=$(ssh $RASPBERRY_PI "pgrep -f 'python3 run.py' | wc -l")
REMAINING_CHROMIUM=$(ssh $RASPBERRY_PI "pgrep chromium | wc -l")

if [ "$REMAINING_FLASK" -gt 0 ] || [ "$REMAINING_CHROMIUM" -gt 0 ]; then
    echo "[$(date '+%H:%M:%S')] ⚠️  프로세스가 남아있음 (Flask: $REMAINING_FLASK, Chromium: $REMAINING_CHROMIUM), 재시도..."
    ssh $RASPBERRY_PI "killall -9 python3 chromium chromium-browser 2>/dev/null"
    sleep 2
fi

echo "[$(date '+%H:%M:%S')] ✅ 모든 프로세스 종료 완료"
echo ""
echo "[$(date '+%H:%M:%S')] 2️⃣ Flask 서버 시작 중..."

# Flask 서버 시작
ssh $RASPBERRY_PI "cd ~/gym-controller && python3 run.py --host 0.0.0.0 --port 5000 >>~/gym-controller/logs/flask.log 2>&1 &"
echo "[$(date '+%H:%M:%S')]    - Flask 서버 시작 명령 전송"

echo "[$(date '+%H:%M:%S')] ⏳ Flask 서버 준비 대기 (5초)..."
sleep 5

# Flask 서버 확인
FLASK_RUNNING=$(ssh $RASPBERRY_PI "pgrep -f 'python3 run.py' | wc -l")
if [ "$FLASK_RUNNING" -gt 0 ]; then
    FLASK_PID=$(ssh $RASPBERRY_PI "pgrep -f 'python3 run.py' | head -1")
    echo "[$(date '+%H:%M:%S')] ✅ Flask 서버 정상 시작 (PID: $FLASK_PID)"
else
    echo "[$(date '+%H:%M:%S')] ❌ Flask 서버 시작 실패!"
    exit 1
fi

echo ""
echo "[$(date '+%H:%M:%S')] 3️⃣ Chromium 키오스크 시작 중..."

# Chromium 키오스크 모드 시작
ssh $RASPBERRY_PI "DISPLAY=:0 chromium-browser --kiosk --no-sandbox --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state --disable-web-security --disable-features=TranslateUI --noerrdialogs --start-fullscreen --window-size=600,1024 --app=http://localhost:5000 >/dev/null 2>&1 &"
echo "[$(date '+%H:%M:%S')]    - Chromium 시작 명령 전송"

echo "[$(date '+%H:%M:%S')] ⏳ Chromium 시작 대기 (5초)..."
sleep 5

# Chromium 프로세스 확인
CHROMIUM_RUNNING=$(ssh $RASPBERRY_PI "pgrep chromium-browser | wc -l")
if [ "$CHROMIUM_RUNNING" -gt 0 ]; then
    CHROMIUM_PID=$(ssh $RASPBERRY_PI "pgrep chromium-browser | head -1")
    CHROMIUM_TOTAL=$(ssh $RASPBERRY_PI "pgrep chromium | wc -l")
    echo "[$(date '+%H:%M:%S')] ✅ Chromium 키오스크 정상 시작 (메인 PID: $CHROMIUM_PID, 전체 프로세스: $CHROMIUM_TOTAL개)"
    
    # Chromium 창 개수가 비정상적으로 많은 경우 경고
    if [ "$CHROMIUM_TOTAL" -gt 15 ]; then
        echo "[$(date '+%H:%M:%S')] ⚠️  경고: Chromium 프로세스가 $CHROMIUM_TOTAL개로 많습니다. (정상: 10~15개)"
        echo "[$(date '+%H:%M:%S')]    → 창이 여러 개 열려있을 수 있습니다. 확인해주세요."
    fi
else
    echo "[$(date '+%H:%M:%S')] ⚠️  Chromium PID 확인 실패 (백그라운드 실행 중일 수 있음)"
fi

echo ""
echo "========================================"
echo "[$(date '+%H:%M:%S')] ✅ 키오스크 재시작 완료!"
echo "Flask 서버: http://localhost:5000"
echo "Chromium: 키오스크 모드 실행 중"
echo "종료 시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 프로세스 상태 출력
echo ""
echo "📊 실행 중인 프로세스:"
echo "Flask 서버:"
ssh $RASPBERRY_PI "ps aux | grep 'python3 run.py' | grep -v grep | head -1"
echo ""
echo "Chromium 브라우저:"
ssh $RASPBERRY_PI "ps aux | grep 'chromium-browser' | grep -v grep | head -1"
CHROMIUM_COUNT=$(ssh $RASPBERRY_PI "pgrep chromium | wc -l")
echo "총 Chromium 프로세스: ${CHROMIUM_COUNT}개"

exit 0
