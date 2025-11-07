#!/bin/bash
# 락카키 대여기 키오스크 모드 종료 스크립트

echo "🛑 락카키 대여기 키오스크 모드 종료"
echo "================================="

# Chromium 브라우저 종료
echo "🌐 브라우저 종료 중..."
pkill -f chromium-browser 2>/dev/null
pkill chromium 2>/dev/null

# Flask 서버 종료
echo "🚀 Flask 서버 종료 중..."
if [ -f /tmp/flask.pid ]; then
    FLASK_PID=$(cat /tmp/flask.pid)
    kill $FLASK_PID 2>/dev/null
    rm -f /tmp/flask.pid
fi

# Python Flask 프로세스 강제 종료
pkill -f "python3 run.py" 2>/dev/null

# unclutter 종료 (마우스 커서 숨기기 해제)
pkill unclutter 2>/dev/null

# 브라우저 PID 파일 삭제
rm -f /tmp/browser.pid

echo "✅ 키오스크 모드 종료 완료"
echo ""
echo "화면 보호기가 다시 활성화됩니다."

# 화면 보호기 재활성화 (선택사항)
export DISPLAY=:0
xset s on 2>/dev/null
xset +dpms 2>/dev/null
