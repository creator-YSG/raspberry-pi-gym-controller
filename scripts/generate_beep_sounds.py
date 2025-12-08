#!/usr/bin/env python3
"""
비프음 생성 스크립트
라즈베리파이용 다양한 알림음 생성
"""

import numpy as np
import wave
import os

def generate_beep(frequency=800, duration=0.2, sample_rate=44100, amplitude=0.3):
    """
    비프음 생성
    
    Args:
        frequency: 주파수 (Hz)
        duration: 지속시간 (초)
        sample_rate: 샘플링 레이트
        amplitude: 음량 (0.0 - 1.0)
    """
    frames = int(duration * sample_rate)
    t = np.linspace(0, duration, frames)
    
    # 사인파 생성
    wave_data = amplitude * np.sin(2 * np.pi * frequency * t)
    
    # 시작과 끝 페이드 효과 (클릭 노이즈 방지)
    fade_frames = int(0.01 * sample_rate)
    if fade_frames < frames:
        wave_data[:fade_frames] *= np.linspace(0, 1, fade_frames)
        wave_data[-fade_frames:] *= np.linspace(1, 0, fade_frames)
    
    return wave_data

def save_wav(wave_data, filename, sample_rate=44100):
    """WAV 파일로 저장"""
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # 모노
        wav_file.setsampwidth(2)  # 16비트
        wav_file.setframerate(sample_rate)
        
        # 16비트 정수로 변환
        wave_data_int = (wave_data * 32767).astype(np.int16)
        wav_file.writeframes(wave_data_int.tobytes())

def generate_multi_beep(frequencies, durations, gaps=None):
    """
    다중 비프음 생성
    
    Args:
        frequencies: 주파수 리스트
        durations: 각 비프음의 지속시간 리스트
        gaps: 비프음 간 간격 (초)
    """
    if gaps is None:
        gaps = [0.05] * (len(frequencies) - 1)
    
    result = np.array([])
    sample_rate = 44100
    
    for i, (freq, duration) in enumerate(zip(frequencies, durations)):
        beep = generate_beep(freq, duration)
        result = np.concatenate([result, beep])
        
        # 마지막이 아니면 간격 추가
        if i < len(frequencies) - 1:
            gap_samples = int(gaps[i] * sample_rate)
            silence = np.zeros(gap_samples)
            result = np.concatenate([result, silence])
    
    return result

def create_sound_library():
    """다양한 알림음 라이브러리 생성"""
    
    # 사운드 파일 저장 디렉토리
    sounds_dir = "/Users/yunseong-geun/Projects/raspberry-pi-gym-controller/app/static/sounds"
    os.makedirs(sounds_dir, exist_ok=True)
    
    print("🔊 비프음 파일 생성 중...")
    
    # 1. 바코드 스캔 성공음 (높은 음 → 낮은 음)
    success_beep = generate_multi_beep([1000, 600], [0.1, 0.2])
    save_wav(success_beep, f"{sounds_dir}/barcode_success.wav")
    print("✅ barcode_success.wav 생성됨")
    
    # 2. 오류/실패음 (낮은 음 3회)
    error_beep = generate_multi_beep([400, 400, 400], [0.15, 0.15, 0.15], [0.1, 0.1])
    save_wav(error_beep, f"{sounds_dir}/error.wav")
    print("❌ error.wav 생성됨")
    
    # 3. 단순 확인음 (중간 높이 1회)
    confirm_beep = generate_beep(800, 0.15)
    save_wav(confirm_beep, f"{sounds_dir}/confirm.wav")
    print("🔔 confirm.wav 생성됨")
    
    # 4. 경고음 (고음 2회)
    warning_beep = generate_multi_beep([1200, 1200], [0.1, 0.1], [0.1])
    save_wav(warning_beep, f"{sounds_dir}/warning.wav")
    print("⚠️ warning.wav 생성됨")
    
    # 5. 시작음 (상승음계)
    startup_beep = generate_multi_beep([523, 659, 784], [0.2, 0.2, 0.3])
    save_wav(startup_beep, f"{sounds_dir}/startup.wav")
    print("🚀 startup.wav 생성됨")
    
    # 6. 완료음 (하강음계)
    complete_beep = generate_multi_beep([784, 659, 523], [0.15, 0.15, 0.3])
    save_wav(complete_beep, f"{sounds_dir}/complete.wav")
    print("✨ complete.wav 생성됨")
    
    # 7. 짧은 클릭음 (UI 피드백용)
    click_beep = generate_beep(1000, 0.05, amplitude=0.2)
    save_wav(click_beep, f"{sounds_dir}/click.wav")
    print("👆 click.wav 생성됨")
    
    print(f"\n🎵 모든 사운드 파일이 {sounds_dir}에 생성되었습니다!")
    
    return sounds_dir

if __name__ == "__main__":
    try:
        import numpy
        import wave
        create_sound_library()
    except ImportError as e:
        print(f"❌ 필수 라이브러리가 설치되지 않음: {e}")
        print("다음 명령어로 설치하세요: pip install numpy")