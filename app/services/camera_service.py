"""
카메라 서비스 (라즈베리파이 카메라 + USB 웹캠 지원)

- picamera2: 라즈베리파이 카메라 V1/V2/V3
- OpenCV VideoCapture: USB 웹캠 (폴백)
- MJPEG 스트림 생성
- 프레임 변화 감지 (모션 디텍션)

NOTE: picamera2 RGB888 형식은 실제로 BGR 순서로 출력됨
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
        self.use_picamera = use_picamera
        self.resolution = resolution
        self.camera = None
        self.is_running = False
        self._lock = threading.Lock()
        
        self._prev_frame = None
        self._motion_detected = False
        self._motion_threshold = 50000  # 민감도 더 낮춤 (25000 → 50000)
        self._last_motion_time = 0
        self._motion_cooldown = 2.0  # 쿨다운 (2초)
        self._camera_start_time = 0  # 카메라 시작 시간
        self._motion_warmup = 5.0  # 시작 후 5초간 모션 무시
        
        self._current_frame = None
        self._frame_lock = threading.Lock()
        
        self.photos_dir = Path("instance/photos")
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        
    def start(self) -> bool:
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
                    self._camera_start_time = time.time()  # 시작 시간 기록
                    self._prev_frame = None  # 모션 감지 초기화
                    self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
                    self._capture_thread.start()
                    logger.info(f"카메라 시작 완료 (picamera: {self.use_picamera})")
                return success
            except Exception as e:
                logger.error(f"카메라 시작 실패: {e}")
                return False
    
    def _start_picamera(self) -> bool:
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
            logger.warning("picamera2 없음. USB 웹캠으로 전환")
            self.use_picamera = False
            return self._start_usb_camera()
        except Exception as e:
            logger.error(f"Picamera2 초기화 실패: {e}")
            self.use_picamera = False
            return self._start_usb_camera()
    
    def _start_usb_camera(self) -> bool:
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
        """프레임 캡처 루프 (모션 감지용 10fps)"""
        frame_count = 0
        while self.is_running:
            try:
                frame = self._capture_frame_internal()
                if frame is not None:
                    with self._frame_lock:
                        self._current_frame = frame.copy()
                    
                    # 모션 감지는 3프레임마다 (CPU 절약)
                    frame_count += 1
                    if frame_count % 3 == 0:
                        self._update_motion_detection(frame)
                
                time.sleep(0.1)  # 10fps (30fps → 10fps로 변경)
            except Exception as e:
                logger.error(f"프레임 캡처 오류: {e}")
                time.sleep(0.1)
    
    def _capture_frame_internal(self) -> Optional[np.ndarray]:
        try:
            if self.use_picamera and self.camera:
                # Picamera2 RGB888 = 실제 BGR 순서
                return self.camera.capture_array()
            elif self.camera:
                ret, frame = self.camera.read()
                if ret:
                    return frame  # OpenCV는 BGR
            return None
        except Exception as e:
            logger.error(f"프레임 캡처 오류: {e}")
            return None
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """현재 프레임 반환 (BGR 포맷)"""
        with self._frame_lock:
            if self._current_frame is not None:
                return self._current_frame.copy()
        return None
    
    def capture_snapshot(self, save_path: Optional[str] = None) -> Optional[str]:
        frame = self.capture_frame()
        if frame is None:
            logger.error("스냅샷 캡처 실패: 프레임 없음")
            return None
        try:
            if save_path is None:
                now = datetime.now()
                year_month_dir = self.photos_dir / "rentals" / str(now.year) / f"{now.month:02d}"
                year_month_dir.mkdir(parents=True, exist_ok=True)
                filename = f"snap_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
                save_path = str(year_month_dir / filename)
            
            # BGR 그대로 저장 (OpenCV 기본)
            cv2.imwrite(save_path, frame)
            logger.info(f"스냅샷 저장: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"스냅샷 저장 실패: {e}")
            return None
    
    def capture_rental_photo(self, rental_id: str) -> Optional[str]:
        now = datetime.now()
        year_month_dir = self.photos_dir / "rentals" / str(now.year) / f"{now.month:02d}"
        year_month_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{rental_id}_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = str(year_month_dir / filename)
        return self.capture_snapshot(save_path)
    
    def _update_motion_detection(self, frame: np.ndarray):
        """모션 감지 (저해상도로 CPU 절약)"""
        try:
            current_time = time.time()
            
            # 카메라 시작 후 warmup 시간 동안은 모션 무시 (자동 노출 안정화)
            if current_time - self._camera_start_time < self._motion_warmup:
                return
            
            # 저해상도로 리사이즈 (640x480 → 160x120) - CPU 절약
            small = cv2.resize(frame, (160, 120))
            
            # BGR → GRAY
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (11, 11), 0)  # 작은 이미지에 맞게 커널도 줄임
            
            if self._prev_frame is None:
                self._prev_frame = gray
                return
            
            frame_delta = cv2.absdiff(self._prev_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            motion_pixels = cv2.countNonZero(thresh)
            
            # 해상도가 1/16이므로 threshold도 조정 (50000 → 3000)
            adjusted_threshold = 3000
            
            if motion_pixels > adjusted_threshold:
                if current_time - self._last_motion_time > self._motion_cooldown:
                    self._motion_detected = True
                    self._last_motion_time = current_time
                    logger.info(f"모션 감지: {motion_pixels} 픽셀 (threshold: {adjusted_threshold})")
            
            self._prev_frame = gray
        except Exception as e:
            logger.error(f"모션 감지 오류: {e}")
    
    def check_motion(self) -> bool:
        if self._motion_detected:
            self._motion_detected = False
            return True
        return False
    
    def generate_mjpeg_stream(self) -> Generator[bytes, None, None]:
        while self.is_running:
            frame = self.capture_frame()
            if frame is not None:
                try:
                    # BGR 그대로 JPEG 인코딩
                    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + 
                           buffer.tobytes() + b"\r\n")
                except Exception as e:
                    logger.error(f"MJPEG 인코딩 오류: {e}")
            time.sleep(0.033)
    
    def set_motion_threshold(self, threshold: int):
        self._motion_threshold = threshold
        logger.info(f"모션 감지 임계값: {threshold}")
    
    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "use_picamera": self.use_picamera,
            "resolution": self.resolution,
            "has_frame": self._current_frame is not None,
            "motion_threshold": self._motion_threshold
        }


_camera_service: Optional[CameraService] = None


def get_camera_service(use_picamera: bool = True) -> CameraService:
    global _camera_service
    if _camera_service is None:
        _camera_service = CameraService(use_picamera=use_picamera)
    return _camera_service
