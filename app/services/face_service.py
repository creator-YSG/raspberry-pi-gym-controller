"""
얼굴인식 서비스 (TFLite MobileFaceNet + OpenCV DNN)

- OpenCV DNN: 얼굴 검출 (SSD)
- TFLite MobileFaceNet: 128D 임베딩 추출
- NumPy: 코사인 유사도 1:N 검색
- SQLite: 임베딩 저장/로드
"""

import numpy as np
import pickle
import logging
import cv2
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, List

logger = logging.getLogger(__name__)

# TFLite 런타임 (라즈베리파이)
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
except ImportError:
    try:
        import tensorflow.lite as tflite
        TFLITE_AVAILABLE = True
    except ImportError:
        TFLITE_AVAILABLE = False
        logger.warning("TFLite 런타임이 설치되지 않았습니다")


class FaceService:
    """얼굴인식 비즈니스 로직"""
    
    def __init__(self, db_path: str = 'instance/gym_system.db'):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = db_path
        
        # 모델 초기화
        self._init_models()
        
        # 임베딩 DB (메모리 캐시)
        self.db_embeddings: Optional[np.ndarray] = None
        self.member_ids: List[str] = []
        
        # 사진 저장 경로
        self.photos_dir = Path('instance/photos/faces')
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        
        # DB에서 임베딩 로드
        self._load_embeddings_from_db()
        
    def _init_models(self):
        """얼굴 검출(Haar) + 임베딩(TFLite) 모델 초기화"""
        models_dir = Path('models')
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 얼굴 검출 모델 (Haar Cascade - 빠름)
        self.face_cascade = None
        try:
            haar_path = models_dir / 'haarcascade_frontalface_default.xml'
            
            if haar_path.exists():
                self.face_cascade = cv2.CascadeClassifier(str(haar_path))
                logger.info("✅ 얼굴 검출 모델(Haar Cascade) 로드 완료")
            else:
                # OpenCV 기본 경로에서 시도
                default_haar = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.face_cascade = cv2.CascadeClassifier(default_haar)
                if self.face_cascade.empty():
                    logger.error("❌ Haar Cascade 모델을 찾을 수 없습니다")
                    self.face_cascade = None
                else:
                    logger.info("✅ 얼굴 검출 모델(Haar Cascade) 로드 완료 (기본 경로)")
        except Exception as e:
            logger.error(f"❌ Haar Cascade 로드 실패: {e}")
        
        # 2. 임베딩 모델 (TFLite MobileFaceNet)
        self.embedding_interpreter = None
        self.embedding_input_details = None
        self.embedding_output_details = None
        
        if not TFLITE_AVAILABLE:
            logger.warning("⚠️ TFLite 런타임 없음 - 임베딩 추출 불가")
            return
            
        try:
            embedding_model = models_dir / 'mobilefacenet.tflite'
            
            if embedding_model.exists():
                self.embedding_interpreter = tflite.Interpreter(
                    model_path=str(embedding_model)
                )
                self.embedding_interpreter.allocate_tensors()
                self.embedding_input_details = self.embedding_interpreter.get_input_details()
                self.embedding_output_details = self.embedding_interpreter.get_output_details()
                
                input_shape = self.embedding_input_details[0]['shape']
                output_shape = self.embedding_output_details[0]['shape']
                logger.info(f"✅ MobileFaceNet TFLite 로드 완료: 입력{input_shape} → 출력{output_shape}")
            else:
                logger.error("❌ MobileFaceNet 모델 파일이 없습니다: models/mobilefacenet.tflite")
        except Exception as e:
            logger.error(f"❌ MobileFaceNet 로드 실패: {e}")
    
    def _get_db_connection(self):
        """데이터베이스 연결 획득"""
        from database.database_manager import DatabaseManager
        db = DatabaseManager(self.db_path)
        db.connect()
        return db
    
    def _load_embeddings_from_db(self):
        """DB에서 모든 얼굴 임베딩 로드 (메모리 캐시)"""
        try:
            db = self._get_db_connection()
            
            cursor = db.execute_query("""
                SELECT member_id, face_embedding 
                FROM members 
                WHERE face_embedding IS NOT NULL 
                  AND face_enabled = 1
                ORDER BY member_id
            """)
            
            if not cursor:
                logger.warning("얼굴 임베딩 조회 실패")
                return
            
            embeddings = []
            self.member_ids = []
            
            for row in cursor.fetchall():
                member_id = row['member_id']
                embedding_blob = row['face_embedding']
                
                # pickle 역직렬화
                embedding = pickle.loads(embedding_blob)
                
                # 정규화
                embedding = embedding / np.linalg.norm(embedding)
                
                embeddings.append(embedding)
                self.member_ids.append(member_id)
            
            if embeddings:
                self.db_embeddings = np.array(embeddings, dtype='float32')
                logger.info(f"얼굴 DB 로드 완료: {len(self.member_ids)}명")
            else:
                self.db_embeddings = None
                logger.warning("등록된 얼굴이 없습니다")
            
            db.close()
            
        except Exception as e:
            logger.error(f"얼굴 DB 로드 오류: {e}")
            self.db_embeddings = None
            self.member_ids = []
    
    def reload_embeddings(self):
        """임베딩 DB 새로고침 (회원 등록/삭제 후 호출)"""
        self._load_embeddings_from_db()
    
    def extract_embedding(self, image: np.ndarray) -> Optional[np.ndarray]:
        """이미지에서 얼굴 임베딩 추출 (Haar + TFLite MobileFaceNet)
        
        Args:
            image: RGB 이미지 배열
            
        Returns:
            128차원 임베딩 벡터 또는 None (얼굴 없음)
        """
        if self.face_cascade is None:
            logger.error("얼굴 검출 모델이 초기화되지 않았습니다")
            return None
        
        if self.embedding_interpreter is None:
            logger.error("MobileFaceNet 모델이 초기화되지 않았습니다")
            return None
        
        try:
            # RGB -> BGR 변환
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            else:
                image_bgr = image
            
            h, w = image_bgr.shape[:2]
            
            # 1. 얼굴 검출 (Haar Cascade - 빠름)
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,
                minNeighbors=3,
                minSize=(40, 40),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            if len(faces) == 0:
                return None
            
            # 가장 큰 얼굴 선택
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            (x, y, fw, fh) = largest_face
            
            # 2. 얼굴 영역 추출 (마진 추가 15%)
            margin_x = int(fw * 0.15)
            margin_y = int(fh * 0.15)
            x1 = max(0, x - margin_x)
            y1 = max(0, y - margin_y)
            x2 = min(w, x + fw + margin_x)
            y2 = min(h, y + fh + margin_y)
            
            face_roi = image_bgr[y1:y2, x1:x2]
            
            if face_roi.size == 0:
                return None
            
            # 3. MobileFaceNet 전처리
            # - 크기: 112x112
            # - 색공간: RGB
            # - 정규화: [-1, 1] (sirius-ai/MobileFaceNet_TF 기준)
            face_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
            face_resized = cv2.resize(face_rgb, (112, 112))
            face_normalized = (face_resized.astype('float32') - 127.5) / 128.0
            face_input = np.expand_dims(face_normalized, axis=0)  # [1, 112, 112, 3]
            
            # 4. TFLite 추론
            self.embedding_interpreter.set_tensor(
                self.embedding_input_details[0]['index'], 
                face_input
            )
            self.embedding_interpreter.invoke()
            
            embedding = self.embedding_interpreter.get_tensor(
                self.embedding_output_details[0]['index']
            )[0]  # [128]
            
            return embedding.astype('float32')
            
        except Exception as e:
            logger.error(f"임베딩 추출 오류: {e}", exc_info=True)
            return None
    
    def detect_face(self, image: np.ndarray) -> bool:
        """이미지에 얼굴이 있는지 확인
        
        Args:
            image: RGB 이미지 배열
            
        Returns:
            얼굴 존재 여부
        """
        embedding = self.extract_embedding(image)
        return embedding is not None
    
    def register_face(self, member_id: str, image: np.ndarray, 
                      save_photo: bool = True) -> Dict:
        """회원 얼굴 등록
        
        Args:
            member_id: 회원 ID
            image: RGB 이미지 배열
            save_photo: 사진 저장 여부
            
        Returns:
            등록 결과 딕셔너리
        """
        try:
            # 임베딩 추출
            embedding = self.extract_embedding(image)
            
            if embedding is None:
                return {
                    'success': False,
                    'error': '얼굴을 찾을 수 없습니다. 카메라를 정면으로 보고 다시 시도해주세요.',
                    'error_type': 'face_not_found'
                }
            
            # 임베딩 직렬화
            embedding_blob = pickle.dumps(embedding)
            
            # 임베딩 파일 저장 (로컬)
            embeddings_dir = Path('instance/embeddings')
            embeddings_dir.mkdir(parents=True, exist_ok=True)
            embedding_file_path = str(embeddings_dir / f"{member_id}.pkl")
            
            with open(embedding_file_path, 'wb') as f:
                pickle.dump({
                    'member_id': member_id,
                    'embedding': embedding,
                    'registered_at': datetime.now().isoformat()
                }, f)
            
            # 사진 저장
            photo_path = None
            photo_url = None
            if save_photo:
                photo_path = str(self.photos_dir / f"{member_id}.jpg")
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(photo_path, image_bgr)
                
                # 구글 드라이브 업로드 (백그라운드)
                self._upload_member_photo_async(member_id, photo_path)
            
            # 임베딩 파일도 드라이브 업로드 (백그라운드)
            self._upload_embedding_async(member_id, embedding_file_path)
            
            # DB 업데이트
            db = self._get_db_connection()
            
            cursor = db.execute_query("""
                UPDATE members 
                SET face_embedding = ?, 
                    face_photo_path = ?,
                    face_registered_at = ?,
                    face_enabled = 1
                WHERE member_id = ?
            """, (embedding_blob, photo_path, datetime.now().isoformat(), member_id))
            
            if cursor is None:
                db.close()
                return {
                    'success': False,
                    'error': '데이터베이스 업데이트 실패',
                    'error_type': 'db_error'
                }
            
            db.close()
            
            # 메모리 캐시 갱신
            self._load_embeddings_from_db()
            
            logger.info(f"얼굴 등록 완료: {member_id}")
            return {
                'success': True,
                'member_id': member_id,
                'photo_path': photo_path,
                'message': f'{member_id} 얼굴 등록이 완료되었습니다.'
            }
            
        except Exception as e:
            logger.error(f"얼굴 등록 오류: {member_id}, {e}")
            return {
                'success': False,
                'error': '얼굴 등록 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }
    
    def unregister_face(self, member_id: str) -> Dict:
        """회원 얼굴 등록 해제
        
        Args:
            member_id: 회원 ID
            
        Returns:
            해제 결과 딕셔너리
        """
        try:
            db = self._get_db_connection()
            
            cursor = db.execute_query("""
                UPDATE members 
                SET face_embedding = NULL, 
                    face_photo_path = NULL,
                    face_registered_at = NULL,
                    face_enabled = 0
                WHERE member_id = ?
            """, (member_id,))
            
            db.close()
            
            # 메모리 캐시 갱신
            self._load_embeddings_from_db()
            
            # 참고: 
            # - 로컬 임베딩 파일(.pkl)은 백업용으로 유지
            # - Drive 파일도 백업용으로 유지
            # - 실제 얼굴 인식은 DB의 face_embedding(NULL로 설정됨)을 사용
            
            logger.info(f"얼굴 등록 해제: {member_id}")
            return {
                'success': True,
                'member_id': member_id,
                'message': f'{member_id} 얼굴 등록이 해제되었습니다.'
            }
            
        except Exception as e:
            logger.error(f"얼굴 등록 해제 오류: {member_id}, {e}")
            return {
                'success': False,
                'error': '얼굴 등록 해제 중 오류가 발생했습니다.'
            }
    
    def authenticate_by_face(self, image: np.ndarray, 
                             threshold: float = 0.85) -> Optional[Tuple[str, float]]:
        """얼굴로 회원 인증 (1:N 검색)
        
        Args:
            image: RGB 이미지 배열
            threshold: 유사도 임계값 (0.85 = 85%)
            
        Returns:
            (member_id, similarity) 튜플 또는 None
        """
        if self.db_embeddings is None or len(self.member_ids) == 0:
            logger.warning("등록된 얼굴이 없습니다")
            return None
        
        # 현재 이미지에서 임베딩 추출
        current_embedding = self.extract_embedding(image)
        
        if current_embedding is None:
            logger.warning("인증 이미지에서 얼굴을 찾을 수 없습니다")
            return None
        
        # 정규화
        current_embedding = current_embedding / np.linalg.norm(current_embedding)
        
        # 코사인 유사도 계산 (NumPy 벡터 연산)
        similarities = np.dot(self.db_embeddings, current_embedding)
        
        # 최고 유사도 찾기
        best_idx = np.argmax(similarities)
        best_similarity = float(similarities[best_idx])
        
        logger.debug(f"얼굴 인식 결과: 최고 유사도 {best_similarity:.3f}, "
                    f"회원 {self.member_ids[best_idx]}")
        
        if best_similarity >= threshold:
            return (self.member_ids[best_idx], best_similarity)
        
        return None
    
    def process_face_auth(self, image: np.ndarray) -> Dict:
        """얼굴 인증 처리 (전체 플로우)
        
        Args:
            image: RGB 이미지 배열
            
        Returns:
            인증 결과 딕셔너리
        """
        import time
        t_start = time.time()
        
        try:
            # 1. 얼굴 인증
            result = self.authenticate_by_face(image, threshold=0.85)
            
            t_auth = time.time()
            
            if result is None:
                # 얼굴이 없거나 매칭 실패
                embedding = self.extract_embedding(image)
                
                if embedding is None:
                    return {
                        'success': False,
                        'error': '얼굴을 찾을 수 없습니다. 카메라를 정면으로 봐주세요.',
                        'error_type': 'face_not_detected',
                        'help_message': '바코드 또는 QR 코드를 사용해주세요.'
                    }
                else:
                    return {
                        'success': False,
                        'error': '등록된 얼굴이 아닙니다.',
                        'error_type': 'face_not_found',
                        'help_message': '바코드 또는 QR 코드를 사용해주세요.'
                    }
            
            member_id, similarity = result
            
            # 2. 회원 유효성 검증
            from app.services.member_service import MemberService
            member_service = MemberService(self.db_path)
            validation = member_service.validate_member(member_id)
            
            t_validate = time.time()
            
            logger.info(f"⏱️ [PERF-FACE] 얼굴 인증: {member_id} | "
                       f"인증: {(t_auth - t_start)*1000:.2f}ms | "
                       f"검증: {(t_validate - t_auth)*1000:.2f}ms | "
                       f"유사도: {similarity:.3f}")
            
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['error'],
                    'error_type': 'member_invalid',
                    'member_id': member_id,
                    'similarity': similarity
                }
            
            member = validation['member']
            
            # 3. 대여/반납 판단
            if member.is_renting:
                return {
                    'success': True,
                    'action': 'return',
                    'member_id': member_id,
                    'member_name': member.name,
                    'current_locker': member.currently_renting,
                    'auth_method': 'face',
                    'similarity': similarity
                }
            else:
                return {
                    'success': True,
                    'action': 'rental',
                    'member_id': member_id,
                    'member_name': member.name,
                    'auth_method': 'face',
                    'similarity': similarity
                }
                
        except Exception as e:
            logger.error(f"얼굴 인증 처리 오류: {e}", exc_info=True)
            return {
                'success': False,
                'error': '얼굴 인증 처리 중 오류가 발생했습니다.',
                'error_type': 'system_error'
            }
    
    def _upload_member_photo_async(self, member_id: str, photo_path: str):
        """회원 사진을 구글 드라이브에 업로드 (백그라운드)
        
        Args:
            member_id: 회원 ID
            photo_path: 로컬 사진 경로
        """
        import threading
        
        def upload_task():
            try:
                from app.services.drive_service import get_drive_service
                
                drive_service = get_drive_service()
                photo_url = drive_service.upload_member_photo(photo_path, member_id)
                
                if photo_url:
                    # DB에 URL 저장
                    db = self._get_db_connection()
                    db.execute_query("""
                        UPDATE members 
                        SET face_photo_url = ?
                        WHERE member_id = ?
                    """, (photo_url, member_id))
                    db.close()
                    
                    logger.info(f"☁️ 회원 사진 드라이브 업로드 완료: {member_id} → {photo_url}")
                    
            except Exception as e:
                logger.warning(f"회원 사진 드라이브 업로드 오류: {member_id}, {e}")
        
        thread = threading.Thread(target=upload_task, daemon=True)
        thread.start()
    
    def _upload_embedding_async(self, member_id: str, embedding_path: str):
        """임베딩 파일을 구글 드라이브에 업로드 (백그라운드)
        
        Args:
            member_id: 회원 ID
            embedding_path: 로컬 임베딩 파일 경로
        """
        import threading
        
        def upload_task():
            try:
                from app.services.drive_service import get_drive_service
                
                drive_service = get_drive_service()
                
                if drive_service.connect():
                    # embeddings 폴더에 업로드
                    url = drive_service.upload_file(
                        embedding_path,
                        'embeddings',  # 락카키대여기-사진/embeddings/
                        f'{member_id}.pkl'
                    )
                    
                    if url:
                        logger.info(f"☁️ 임베딩 드라이브 업로드 완료: {member_id} → {url}")
                    else:
                        logger.warning(f"임베딩 드라이브 업로드 실패: {member_id}")
                    
            except Exception as e:
                logger.warning(f"임베딩 드라이브 업로드 오류: {member_id}, {e}")
        
        thread = threading.Thread(target=upload_task, daemon=True)
        thread.start()
    
    def get_registered_count(self) -> int:
        """등록된 얼굴 수 반환"""
        return len(self.member_ids) if self.member_ids else 0
    
    def get_status(self) -> Dict:
        """서비스 상태 반환"""
        return {
            'detector_initialized': self.face_cascade is not None,
            'embedding_initialized': self.embedding_interpreter is not None,
            'tflite_available': TFLITE_AVAILABLE,
            'registered_faces': self.get_registered_count(),
            'member_ids': self.member_ids[:10] if self.member_ids else [],
            'db_path': self.db_path
        }


# 싱글톤 인스턴스
_face_service: Optional[FaceService] = None


def get_face_service(db_path: str = 'instance/gym_system.db') -> FaceService:
    """FaceService 싱글톤 인스턴스 반환
    
    Args:
        db_path: 데이터베이스 파일 경로
        
    Returns:
        FaceService 인스턴스
    """
    global _face_service
    
    if _face_service is None:
        _face_service = FaceService(db_path=db_path)
        
    return _face_service

