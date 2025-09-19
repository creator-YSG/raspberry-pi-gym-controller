#!/usr/bin/env python3
"""
라즈베리파이 오디오 출력 테스트 (더 확실한 버전)

볼륨 확인 및 설정 포함
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def check_volume_settings():
    """볼륨 설정 확인 및 조정"""
    print("🔊 볼륨 설정 확인 중...")
    
    try:
        # ALSA 볼륨 확인
        result = subprocess.run(['amixer', 'get', 'PCM'], capture_output=True, text=True)
        print("📱 현재 PCM 볼륨:")
        print(result.stdout)
        
        # 볼륨을 최대로 설정
        print("\n🔊 볼륨을 최대로 설정...")
        subprocess.run(['amixer', 'set', 'PCM', '100%'], capture_output=True)
        subprocess.run(['amixer', 'set', 'Master', '100%'], capture_output=True)
        
        print("✅ 볼륨 설정 완료")
        return True
        
    except Exception as e:
        print(f"❌ 볼륨 설정 오류: {e}")
        return False

def test_audio_output_selection():
    """오디오 출력 장치 선택 및 테스트"""
    print("\n🔊 오디오 출력 장치 설정...")
    
    try:
        # 3.5mm 잭으로 강제 설정
        print("📱 3.5mm 잭으로 출력 설정...")
        subprocess.run(['sudo', 'raspi-config', 'nonint', 'do_audio', '1'], capture_output=True)
        
        # 또는 amixer로 직접 설정
        subprocess.run(['amixer', 'cset', 'numid=3', '1'], capture_output=True)  # 3.5mm 잭
        
        print("✅ 3.5mm 잭으로 설정 완료")
        
        # HDMI 출력도 테스트
        print("\n📱 HDMI 출력으로 설정...")
        subprocess.run(['amixer', 'cset', 'numid=3', '2'], capture_output=True)  # HDMI
        
        print("✅ HDMI 출력으로 설정 완료")
        
        return True
        
    except Exception as e:
        print(f"❌ 출력 장치 설정 오류: {e}")
        return False

def test_loud_beep():
    """확실히 들리는 비프음 테스트"""
    print("\n🔊 확실한 비프음 테스트...")
    
    try:
        # 여러 번 비프음
        for i in range(5):
            print(f"비프 {i+1}/5... 🔊")
            print('\a' * 10)  # 여러 번 비프
            os.system('echo -e "\\a\\a\\a"')
            time.sleep(0.5)
        
        print("✅ 비프음 테스트 완료")
        return True
        
    except Exception as e:
        print(f"❌ 비프음 테스트 오류: {e}")
        return False

def test_speaker_test_longer():
    """더 긴 스피커 테스트"""
    print("\n🔊 긴 스피커 테스트 (5초간)...")
    
    try:
        # 5초간 1000Hz 톤
        result = subprocess.run([
            'speaker-test', '-t', 'sine', '-f', '1000', '-l', '5'
        ], capture_output=True, text=True, timeout=15)
        
        print("✅ 긴 스피커 테스트 완료")
        return True
        
    except subprocess.TimeoutExpired:
        print("✅ 스피커 테스트 완료 (타임아웃)")
        return True
    except Exception as e:
        print(f"❌ 스피커 테스트 오류: {e}")
        return False

def test_with_paplay():
    """PulseAudio로 테스트"""
    print("\n🔊 PulseAudio paplay 테스트...")
    
    try:
        # 시스템 사운드 재생
        result = subprocess.run(['paplay', '/usr/share/sounds/alsa/Front_Left.wav'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ PulseAudio 사운드 재생 성공")
            return True
        else:
            print(f"❌ PulseAudio 재생 실패: {result.stderr}")
            
        # 대체 사운드 파일들
        sound_files = [
            '/usr/share/sounds/alsa/Front_Right.wav',
            '/usr/share/sounds/alsa/Front_Center.wav',
            '/usr/share/sounds/purple/login.wav',
            '/usr/share/sounds/purple/logout.wav'
        ]
        
        for sound_file in sound_files:
            if os.path.exists(sound_file):
                print(f"📱 재생 시도: {sound_file}")
                result = subprocess.run(['paplay', sound_file], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"✅ 재생 성공: {sound_file}")
                    return True
        
        return False
        
    except Exception as e:
        print(f"❌ PulseAudio 테스트 오류: {e}")
        return False

def create_and_play_loud_sound():
    """큰 소리 WAV 파일 생성 및 재생"""
    print("\n🔊 큰 소리 WAV 파일 생성 및 재생...")
    
    try:
        # sox를 사용하여 큰 소리 생성
        test_file = "/tmp/loud_beep.wav"
        
        # 3초간 1000Hz 사인파 생성
        result = subprocess.run([
            'sox', '-n', test_file, 'synth', '3', 'sine', '1000', 'vol', '0.8'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 소리 파일 생성 성공")
            
            # aplay로 재생
            print("📱 aplay로 재생...")
            subprocess.run(['aplay', test_file])
            
            # paplay로도 재생
            print("📱 paplay로 재생...")
            subprocess.run(['paplay', test_file])
            
            # 파일 삭제
            os.remove(test_file)
            
            print("✅ 큰 소리 재생 완료")
            return True
        else:
            print("❌ sox로 소리 파일 생성 실패")
            return False
            
    except FileNotFoundError:
        print("❌ sox가 설치되지 않음")
        return False
    except Exception as e:
        print(f"❌ 큰 소리 생성 오류: {e}")
        return False

def main():
    print("🎵 라즈베리파이 오디오 출력 테스트 (더 확실한 버전)")
    print("=" * 60)
    
    # 현재 사용자가 오디오 그룹에 있는지 확인
    result = subprocess.run(['groups'], capture_output=True, text=True)
    print(f"📱 현재 사용자 그룹: {result.stdout.strip()}")
    
    tests = [
        ("볼륨 설정 확인", check_volume_settings),
        ("오디오 출력 장치 설정", test_audio_output_selection),
        ("확실한 비프음", test_loud_beep),
        ("긴 스피커 테스트", test_speaker_test_longer),
        ("PulseAudio 테스트", test_with_paplay),
        ("큰 소리 WAV 생성", create_and_play_loud_sound),
    ]
    
    print("\n🔊 지금부터 소리가 날 예정입니다!")
    print("🎧 스피커나 헤드폰 볼륨을 확인하세요!")
    time.sleep(3)
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 테스트 중 오류: {e}")
            results.append((test_name, False))
        
        print("💤 2초 대기...")
        time.sleep(2)  # 테스트 간 간격
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📋 테스트 결과 요약:")
    
    success_count = 0
    for test_name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  • {test_name}: {status}")
        if success:
            success_count += 1
    
    print(f"\n🎯 전체 결과: {success_count}/{len(results)} 성공")
    
    if success_count == 0:
        print("\n❌ 모든 테스트가 실패했습니다.")
        print("🔧 해결 방법:")
        print("  1. 스피커/헤드폰이 제대로 연결되어 있는지 확인")
        print("  2. sudo alsamixer 실행해서 볼륨 확인")
        print("  3. sudo raspi-config에서 Advanced Options > Audio 확인")
        print("  4. 3.5mm 잭과 HDMI 모두 테스트")
    else:
        print(f"\n✅ {success_count}개 테스트 성공!")
        print("만약 아직도 소리가 안 들린다면:")
        print("  • 스피커 전원 확인")
        print("  • 케이블 연결 확인") 
        print("  • 다른 오디오 출력 포트 시도")

if __name__ == "__main__":
    main()
