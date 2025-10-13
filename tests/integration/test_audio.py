#!/usr/bin/env python3
"""
라즈베리파이 오디오 출력 테스트

다양한 방법으로 소리 출력을 테스트합니다.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def test_system_beep():
    """시스템 비프음 테스트"""
    print("🔊 시스템 비프음 테스트...")
    try:
        # 터미널 벨 소리
        print('\a')  # ASCII 벨 문자
        time.sleep(1)
        
        # 또는 echo 명령으로
        os.system('echo -e "\\a"')
        print("✅ 시스템 비프음 완료 (들렸나요?)")
        return True
    except Exception as e:
        print(f"❌ 시스템 비프음 실패: {e}")
        return False

def test_speaker_test():
    """speaker-test 명령으로 테스트"""
    print("\n🔊 speaker-test 명령 테스트...")
    try:
        # 2초간 화이트 노이즈 출력
        result = subprocess.run([
            'speaker-test', '-t', 'sine', '-f', '1000', '-l', '1'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ speaker-test 성공")
            return True
        else:
            print(f"❌ speaker-test 실패: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✅ speaker-test 타임아웃 (정상 - 소리가 났을 것입니다)")
        return True
    except FileNotFoundError:
        print("❌ speaker-test 명령이 없습니다")
        return False
    except Exception as e:
        print(f"❌ speaker-test 오류: {e}")
        return False

def test_aplay_wav():
    """WAV 파일 재생 테스트 (간단한 톤 생성)"""
    print("\n🔊 WAV 파일 재생 테스트...")
    try:
        # 간단한 톤 생성해서 재생
        import numpy as np
        import wave
        
        # 1초간 440Hz 톤 생성
        sample_rate = 44100
        duration = 1.0
        frequency = 440.0
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        wave_data = np.sin(frequency * 2 * np.pi * t)
        
        # 16비트로 변환
        wave_data = (wave_data * 32767).astype(np.int16)
        
        # WAV 파일로 저장
        test_file = "/tmp/test_tone.wav"
        with wave.open(test_file, 'w') as wav_file:
            wav_file.setnchannels(1)  # 모노
            wav_file.setsampwidth(2)  # 16비트
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(wave_data.tobytes())
        
        # aplay로 재생
        result = subprocess.run(['aplay', test_file], capture_output=True, text=True)
        
        # 파일 삭제
        os.remove(test_file)
        
        if result.returncode == 0:
            print("✅ WAV 파일 재생 성공")
            return True
        else:
            print(f"❌ WAV 파일 재생 실패: {result.stderr}")
            return False
            
    except ImportError:
        print("❌ numpy가 설치되지 않음 - WAV 테스트 건너뛰기")
        return False
    except Exception as e:
        print(f"❌ WAV 파일 재생 오류: {e}")
        return False

def test_audio_devices():
    """오디오 디바이스 확인"""
    print("\n🔊 오디오 디바이스 확인...")
    try:
        # ALSA 디바이스 목록
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        if result.returncode == 0:
            print("📱 사용 가능한 오디오 디바이스:")
            print(result.stdout)
            return True
        else:
            print("❌ 오디오 디바이스 확인 실패")
            return False
    except Exception as e:
        print(f"❌ 오디오 디바이스 확인 오류: {e}")
        return False

def test_pulseaudio():
    """PulseAudio 상태 확인"""
    print("\n🔊 PulseAudio 상태 확인...")
    try:
        # PulseAudio 정보
        result = subprocess.run(['pactl', 'info'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ PulseAudio 작동 중")
            print("📱 PulseAudio 정보:")
            print(result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout)
            return True
        else:
            print("❌ PulseAudio 없음 또는 오류")
            return False
    except Exception as e:
        print(f"❌ PulseAudio 확인 오류: {e}")
        return False

def test_simple_sound():
    """가장 간단한 소리 테스트"""
    print("\n🔊 간단한 소리 테스트...")
    try:
        # /dev/audio에 간단한 데이터 쓰기 (있다면)
        commands = [
            'cat /dev/urandom | head -c 4096 > /dev/audio',  # 랜덤 노이즈
            'yes | head -c 4096 > /dev/audio',  # 반복 문자
        ]
        
        for cmd in commands:
            try:
                os.system(f'timeout 1 {cmd} 2>/dev/null')
                print(f"✅ 명령 실행: {cmd[:30]}...")
                time.sleep(0.5)
            except:
                continue
                
        return True
    except Exception as e:
        print(f"❌ 간단한 소리 테스트 오류: {e}")
        return False

def main():
    print("🎵 라즈베리파이 오디오 출력 테스트")
    print("=" * 50)
    
    tests = [
        ("시스템 비프음", test_system_beep),
        ("오디오 디바이스 확인", test_audio_devices),
        ("PulseAudio 확인", test_pulseaudio),
        ("speaker-test", test_speaker_test),
        ("WAV 파일 재생", test_aplay_wav),
        ("간단한 소리", test_simple_sound),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 테스트 중 오류: {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # 테스트 간 간격
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📋 테스트 결과 요약:")
    
    success_count = 0
    for test_name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  • {test_name}: {status}")
        if success:
            success_count += 1
    
    print(f"\n🎯 전체 결과: {success_count}/{len(results)} 성공")
    
    if success_count > 0:
        print("🔊 일부 또는 모든 오디오 테스트가 성공했습니다!")
        print("만약 소리가 들리지 않았다면:")
        print("  1. 스피커/헤드폰이 연결되어 있는지 확인")
        print("  2. 볼륨이 켜져 있는지 확인 (alsamixer)")
        print("  3. 오디오 출력 장치 설정 확인 (raspi-config)")
    else:
        print("❌ 모든 오디오 테스트가 실패했습니다.")
        print("🔧 해결 방법:")
        print("  1. sudo apt update && sudo apt install alsa-utils")
        print("  2. sudo raspi-config에서 오디오 설정 확인")
        print("  3. 오디오 출력을 HDMI 또는 3.5mm 잭으로 변경")

if __name__ == "__main__":
    main()
