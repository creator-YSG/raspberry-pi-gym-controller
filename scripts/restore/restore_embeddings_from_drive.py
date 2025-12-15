#!/usr/bin/env python3
"""
Google Drive에서 얼굴 임베딩 복원

사용법:
    python scripts/restore/restore_embeddings_from_drive.py
    
설명:
    - Google Drive의 embeddings 폴더에서 모든 .pkl 파일 다운로드
    - 로컬 DB에 임베딩 복원
    - 라즈베리파이 교체 또는 DB 초기화 시 사용
"""

import sys
import pickle
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database.database_manager import DatabaseManager
from app.services.drive_service import get_drive_service


def restore_embeddings_from_drive():
    """Google Drive에서 모든 임베딩 파일 다운로드 및 복원"""
    
    print('=' * 60)
    print('📥 Google Drive에서 얼굴 임베딩 복원')
    print('=' * 60)
    
    # Drive 연결
    print('\n[1] Google Drive 연결')
    print('-' * 60)
    drive_service = get_drive_service()
    
    if not drive_service.connect():
        print('❌ Drive 연결 실패')
        return 1
    
    print('✅ Drive 연결 성공')
    
    # embeddings 폴더에서 모든 .pkl 파일 목록 가져오기
    print('\n[2] 임베딩 파일 목록 조회')
    print('-' * 60)
    
    try:
        # embeddings 폴더 ID 가져오기
        folder_id = drive_service._get_or_create_folder('embeddings')
        
        if not folder_id:
            print('❌ embeddings 폴더를 찾을 수 없습니다')
            return 1
        
        # 폴더 내 파일 목록
        results = drive_service.service.files().list(
            q=f"'{folder_id}' in parents and trashed=false and name contains '.pkl'",
            fields="files(id, name, createdTime)"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print('⚠️  복원할 임베딩 파일이 없습니다')
            return 0
        
        print(f'✅ 발견된 파일: {len(files)}개')
        for f in files:
            print(f'   - {f["name"]} ({f["createdTime"]})')
        
    except Exception as e:
        print(f'❌ 파일 목록 조회 실패: {e}')
        return 1
    
    # 다운로드 디렉토리 생성
    download_dir = project_root / 'instance' / 'embeddings'
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # 파일 다운로드 및 DB 복원
    print('\n[3] 임베딩 파일 다운로드 및 복원')
    print('-' * 60)
    
    db = DatabaseManager(str(project_root / 'instance' / 'gym_system.db'))
    if not db.connect():
        print('❌ DB 연결 실패')
        return 1
    
    restored_count = 0
    
    for file in files:
        try:
            member_id = file['name'].replace('.pkl', '')
            local_path = download_dir / file['name']
            
            # 파일 다운로드
            request = drive_service.service.files().get_media(fileId=file['id'])
            with open(local_path, 'wb') as f:
                f.write(request.execute())
            
            # Pickle 파일 로드
            with open(local_path, 'rb') as f:
                data = pickle.load(f)
            
            # 임베딩 추출
            embedding = data['embedding']
            registered_at = data.get('registered_at', datetime.now().isoformat())
            
            # DB에 저장
            embedding_blob = pickle.dumps(embedding)
            
            db.execute_query("""
                UPDATE members 
                SET face_embedding = ?,
                    face_registered_at = ?,
                    face_enabled = 1
                WHERE member_id = ?
            """, (embedding_blob, registered_at, member_id))
            
            print(f'   ✅ {member_id}: 복원 완료')
            restored_count += 1
            
        except Exception as e:
            print(f'   ❌ {file["name"]}: 복원 실패 - {e}')
    
    db.close()
    
    print('\n' + '=' * 60)
    print(f'✅ 복원 완료: {restored_count}/{len(files)}개')
    print('=' * 60)
    print()
    print('📌 참고:')
    print('   - 로컬 DB에 임베딩이 복원되었습니다')
    print('   - FaceService를 재시작하면 메모리에 로드됩니다')
    print('   - 얼굴 인식이 정상 작동하는지 테스트하세요')
    print()
    
    return 0


def restore_single_embedding(member_id: str):
    """특정 회원의 임베딩만 복원
    
    Args:
        member_id: 회원 ID
    """
    print(f'📥 {member_id} 임베딩 복원 중...')
    
    drive_service = get_drive_service()
    if not drive_service.connect():
        print('❌ Drive 연결 실패')
        return False
    
    try:
        # embeddings 폴더에서 파일 검색
        folder_id = drive_service._get_or_create_folder('embeddings')
        
        results = drive_service.service.files().list(
            q=f"'{folder_id}' in parents and name='{member_id}.pkl' and trashed=false",
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            print(f'❌ {member_id}.pkl 파일을 찾을 수 없습니다')
            return False
        
        file = files[0]
        
        # 다운로드
        download_dir = project_root / 'instance' / 'embeddings'
        download_dir.mkdir(parents=True, exist_ok=True)
        local_path = download_dir / f'{member_id}.pkl'
        
        request = drive_service.service.files().get_media(fileId=file['id'])
        with open(local_path, 'wb') as f:
            f.write(request.execute())
        
        # 로드 및 DB 저장
        with open(local_path, 'rb') as f:
            data = pickle.load(f)
        
        embedding_blob = pickle.dumps(data['embedding'])
        
        db = DatabaseManager(str(project_root / 'instance' / 'gym_system.db'))
        db.connect()
        
        db.execute_query("""
            UPDATE members 
            SET face_embedding = ?,
                face_registered_at = ?,
                face_enabled = 1
            WHERE member_id = ?
        """, (embedding_blob, data.get('registered_at'), member_id))
        
        db.close()
        
        print(f'✅ {member_id} 임베딩 복원 완료')
        return True
        
    except Exception as e:
        print(f'❌ 복원 실패: {e}')
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 특정 회원 복원
        member_id = sys.argv[1]
        restore_single_embedding(member_id)
    else:
        # 전체 복원
        sys.exit(restore_embeddings_from_drive())

