"""
얼굴인식 서비스 (MediaPipe + NumPy)

- MediaPipe FaceMesh: 얼굴 랜드마크 추출 (1404차원 임베딩)
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


class FaceService:
    """얼굴인식 비즈니스 로직"""
    
    def __init__(self, db_path: str = 'instance/gym_system.db'):
        """
        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = db_path
        
        # MediaPipe 초기화
        self._init_mediapipe()
        
        # 임베딩 DB (메모리 캐시)
        self.db_embeddings: Optional[np.ndarray] = None
        self.member_ids: List[str] = []
        
        # 사진 저장 경로
        self.photos_dir = Path('instance/photos/faces')
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        
        # DB에서 임베딩 로드
        self._load_embeddings_from_db()
        
    def _init_mediapipe(self):
        """MediaPipe 초기화"""
        try:
            import mediapipe as mp
            
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            logger.info("MediaPipe FaceMesh 초기화 완료")
            
        except ImportError as e:
            logger.error(f"MediaPipe를 찾을 수 없습니다: {e}")
            logger.error("pip install mediapipe 를 실행하세요")
            self.face_mesh = None
    
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
        """이미지에서 얼굴 임베딩 추출
        
        Args:
            image: RGB 이미지 배열
            
        Returns:
            1404차원 임베딩 벡터 또는 None (얼굴 없음)
        """
        if self.face_mesh is None:
            logger.error("MediaPipe가 초기화되지 않았습니다")
            return None
        
        try:
            # MediaPipe 처리
            results = self.face_mesh.process(image)
            
            if not results.multi_face_landmarks:
                return None
            
            # 첫 번째 얼굴의 랜드마크 추출
            landmarks = results.multi_face_landmarks[0]
            
            # 468개 랜드마크 × 3좌표(x, y, z) = 1404차원
            embedding = np.array([
                [lm.x, lm.y, lm.z] 
                for lm in landmarks.landmark
            ]).flatten()
            
            return embedding.astype('float32')
            
        except Exception as e:
            logger.error(f"임베딩 추출 오류: {e}")
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
            
            # 사진 저장
            photo_path = None
            if save_photo:
                photo_path = str(self.photos_dir / f"{member_id}.jpg")
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(photo_path, image_bgr)
            
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
    
    def get_registered_count(self) -> int:
        """등록된 얼굴 수 반환"""
        return len(self.member_ids) if self.member_ids else 0
    
    def get_status(self) -> Dict:
        """서비스 상태 반환"""
        return {
            'mediapipe_initialized': self.face_mesh is not None,
            'registered_faces': self.get_registered_count(),
            'member_ids': self.member_ids[:10] if self.member_ids else [],  # 처음 10명만
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

