import os
import threading
import subprocess
from pathlib import Path

class AudioService:
    """라즈베리파이용 간단한 오디오 서비스"""
    
    def __init__(self):
        self.sounds_dir = Path(__file__).parent.parent / "static" / "sounds"
        self.sounds_dir.mkdir(exist_ok=True)
        
    def beep(self):
        """간단한 비프음 재생"""
        try:
            # 라즈베리파이에서 간단한 비프음
            subprocess.run(['aplay', '/dev/stdin'], input=b'\x07', timeout=1)
        except:
            try:
                # 대안: 시스템 벨
                subprocess.run(['printf', '\a'], timeout=1)
            except:
                pass
    
    def beep_async(self):
        """비동기 비프음 (메인 스레드 블로킹 방지)"""
        threading.Thread(target=self.beep, daemon=True).start()

# 전역 인스턴스
audio = AudioService()

def play_beep():
    """바코드 스캔 시 호출할 함수"""
    audio.beep_async()