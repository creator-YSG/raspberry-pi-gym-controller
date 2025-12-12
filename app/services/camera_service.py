"""
카메라 서비스 (라즈베리파이 카메라 + USB 웹캠 지원)

- picamera2: 라즈베리파이 카메라 V1/V2/V3
- OpenCV VideoCapture: USB 웹캠 (폴백)
- MJPEG 스트림 생성
- 프레임 변화 감지 (모션 디텍션)
"""

import cv2
import numpy as np
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator, Tuple

logger = logging.getLogger(__name__)


class CameraService:
    """카메라 제어 및 프레임 변화 감지"""
    
    def __init__(self, use_picamera: bool = True, resolution: Tuple[int, int] = (640, 480)):
        """
        Args:
            use_picamera: 라즈베리파이 카메라 사용 여부 (False면 USB 웹캠)
            resolution: 카메라 해상도 (width, height)
        """
        self.use_picamera = use_picamera
        self.resolution = resolution
        self.camera = None
        self.is_running = False
        self._lock = threading.Lock()
        
        # 프레임 변화 감지용
        self._prev_frame = None
        self._motion_detected = False
        self._motion_threshold = 5000  # 변화량 임계값 (픽셀 수)
        self._last_motion_time = 0
        self._motion_cooldown = 1.0  # 모션 감지 후 쿨다운 (초)
        
        # 현재 프레임 캐시
        self._current_frame = None
        self._frame_lock = threading.Lock()
        
        # 사진 저장 경로
        self.photos_dir = Path('instance/photos')
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        
    def start(self) -> bool:
        """카메라 시작
        
        Returns:
            시작 성공 여부
        """
        with self._lock:
            if self.is_running:
                return True
                
            try:
                if self.use_picamera:
                    success = self._start_picamera()
                else:
                    success = self._start_usb_camera()
                
                if success:
                    self.is_running = True
                    # 백그라운드 프레임 캡처 스레드 시작
                    self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
                    self._capture_thread.start()
                    logger.info(f"카메라 시작 완료 (picamera: {self.use_picamera})")
                    
                return success
                
            except Exception as e:
                logger.error(f"카메라 시작 실패: {e}")
                return False
    
    def _start_picamera(self) -> bool:
        """라즈베리파이 카메라 초기화"""
        try:
            from picamera2 import Picamera2
            
            self.camera = Picamera2()
            config = self.camera.create_preview_configuration(
                main={"size": self.resolution, "format": "RGB888"}
            )
            self.camera.configure(config)
            self.camera.start()
            logger.info("Picamera2 초기화 완료")
            return True
            
        except ImportError:
            logger.warning("picamera2를 찾을 수 없습니다. USB 웹캠으로 전환합니다.")
            self.use_picamera = False
            return self._start_usb_camera()
            
        except Exception as e:
            logger.error(f"Picamera2 초기화 실패: {e}")
            logger.info("USB 웹캠으로 전환 시도...")
            self.use_picamera = False
            return self._start_usb_camera()
    
    def _start_usb_camera(self) -> bool:
        """USB 웹캠 초기화"""
        try:
            self.camera = cv2.VideoCapture(0)
            
            if not self.camera.isOpened():
                logger.error("USB 웹캠을 열 수 없습니다")
                return False
            
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            logger.info("USB 웹캠 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"USB 웹캠 초기화 실패: {e}")
            return False
    
    def stop(self):
        """카메라 정지"""
        with self._lock:
            self.is_running = False
            
            try:
                if self.camera:
                    if self.use_picamera:
                        self.camera.stop()
                    else:
                        self.camera.release()
                    self.camera = None
                    logger.info("카메라 정지 완료")
            except Exception as e:
                logger.error(f"카메라 정지 오류: {e}")
    
    def _capture_loop(self):
        """백그라운드 프레임 캡처 루프"""
        while self.is_running:
            try:
                frame = self._capture_frame_internal()
                
                if frame is not None:
                    with self._frame_lock:
                        self._current_frame = frame.copy()
                    
                    # 프레임 변화 감지 업데이트
                    self._update_motion_detection(frame)
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                logger.error(f"프레임 캡처 오류: {e}")
                time.sleep(0.1)
    
    def _capture_frame_internal(self) -> Optional[np.ndarray]:
        """내부 프레임 캡처"""
        try:
            if self.use_picamera and self.camera:
                # Picamera2는 RGB 포맷으로 반환
                frame = self.camera.capture_array()
                return frame
            elif self.camera:
                ret, frame = self.camera.read()
                if ret:
                    # OpenCV는 BGR, RGB로 변환
                    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return None
        except Exception as e:
            logger.error(f"프레임 캡처 오류: {e}")
            return None
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """현재 프레임 반환 (RGB 포맷)
        
        Returns:
            RGB 이미지 배열 또는 None
        """
        with self._frame_lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
        return None
    
    def capture_snapshot(self, save_path: Optional[str] = None) -> Optional[str]:
        """스냅샷 촬영 및 저장
        
        Args:
            save_path: 저장 경로 (None이면 자동 생성)
            
        Returns:
            저장된 파일 경로 또는 None
        """
        frame = self.capture_frame()
        
        if frame is None:
            logger.error("스냅샷 캡처 실패: 프레임 없음")
            return None
        
        try:
            if save_path is None:
                # 자동 경로 생성: instance/photos/rentals/2025/12/snap_20251212_143052.jpg
                now = datetime.now()
                year_month_dir = self.photos_dir / 'rentals' / str(now.year) / f"{now.month:02d}"
                year_month_dir.mkdir(parents=True, exist_ok=True)
                
                filename = f"snap_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
                save_path = str(year_month_dir / filename)
            
            # RGB → BGR 변환 후 저장
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imwrite(save_path, frame_bgr)
            
            logger.info(f"스냅샷 저장: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"스냅샷 저장 실패: {e}")
            return None
    
    def capture_rental_photo(self, rental_id: str) -> Optional[str]:
        """대여/반납 시 인증 사진 촬영
        
        Args:
            rental_id: 대여 ID (트랜잭션 ID)
            
        Returns:
            저장된 파일 경로 또는 None
        """
        now = datetime.now()
        year_month_dir = self.photos_dir / 'rentals' / str(now.year) / f"{now.month:02d}"
        year_month_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명: R12345_20251212_143052.jpg
        filename = f"{rental_id}_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = str(year_month_dir / filename)
        
        return self.capture_snapshot(save_path)
    
    def _update_motion_detection(self, frame: np.ndarray):
        """프레임 변화 감지 업데이트"""
        try:
            # 그레이스케일 변환
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            if self._prev_frame is None:
                self._prev_frame = gray
                return
            
            # 프레임 차이 계산
            frame_delta = cv2.absdiff(self._prev_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            # 변화된 픽셀 수
            motion_pixels = cv2.countNonZero(thresh)
            
            current_time = time.time()
            
            # 쿨다운 체크 후 모션 감지 상태 업데이트
            if motion_pixels > self._motion_threshold:
                if current_time - self._last_motion_time > self._motion_cooldown:
                    self._motion_detected = True
                    self._last_motion_time = current_time
                    logger.debug(f"모션 감지: {motion_pixels} 픽셀 변화")
            
            self._prev_frame = gray
            
        except Exception as e:
            logger.error(f"모션 감지 오류: {e}")
    
    def check_motion(self) -> bool:
        """프레임 변화 감지 여부 확인 (폴링용)
        
        Returns:
            모션 감지 여부 (True면 사람이 접근함)
        """
        # 한 번 읽으면 리셋
        if self._motion_detected:
            self._motion_detected = False
            return True
        return False
    
    def generate_mjpeg_stream(self) -> Generator[bytes, None, None]:
        """MJPEG 스트림 생성 (Flask Response용)
        
        Yields:
            MJPEG 프레임 바이트
        """
        while self.is_running:
            frame = self.capture_frame()
            
            if frame is not None:
                try:
                    # RGB → BGR 변환
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # JPEG 인코딩
                    _, buffer = cv2.imencode('.jpg', frame_bgr, 
                                            [cv2.IMWRITE_JPEG_QUALITY, 80])
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           buffer.tobytes() + b'\r\n')
                           
                except Exception as e:
                    logger.error(f"MJPEG 인코딩 오류: {e}")
            
            time.sleep(0.033)  # ~30 FPS
    
    def set_motion_threshold(self, threshold: int):
        """모션 감지 임계값 설정
        
        Args:
            threshold: 변화 픽셀 수 임계값
        """
        self._motion_threshold = threshold
        logger.info(f"모션 감지 임계값 설정: {threshold}")
    
    def get_status(self) -> dict:
        """카메라 상태 반환"""
        return {
            'is_running': self.is_running,
            'use_picamera': self.use_picamera,
            'resolution': self.resolution,
            'has_frame': self._current_frame is not None,
            'motion_threshold': self._motion_threshold
        }


# 싱글톤 인스턴스
_camera_service: Optional[CameraService] = None


def get_camera_service(use_picamera: bool = True) -> CameraService:
    """카메라 서비스 싱글톤 인스턴스 반환
    
    Args:
        use_picamera: 라즈베리파이 카메라 사용 여부
        
    Returns:
        CameraService 인스턴스
    """
    global _camera_service
    
    if _camera_service is None:
        _camera_service = CameraService(use_picamera=use_picamera)
        
    return _camera_service

