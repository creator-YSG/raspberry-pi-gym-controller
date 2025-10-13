#!/usr/bin/env python3
"""
회원 권한 업데이트 스크립트
CSV 파일에서 성별과 고객구분을 읽어서 락커 접근 권한을 설정합니다.
"""

import sys
import os
import csv
import sqlite3
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database_manager import DatabaseManager


def parse_member_category(customer_type: str) -> str:
    """고객구분에서 회원 카테고리 결정"""
    staff_types = ['대학교수', '대학직원']
    if customer_type in staff_types:
        return 'staff'
    else:
        return 'general'


def parse_gender(gender_str: str) -> str:
    """성별 문자열을 표준화"""
    if gender_str == '남자':
        return 'male'
    elif gender_str == '여자':
        return 'female'
    else:
        return 'male'  # 기본값


def parse_expiry_date(date_str: str) -> str:
    """만료일자 문자열을 ISO 형식으로 변환"""
    if not date_str or date_str.strip() == '':
        return None
    
    try:
        # CSV에서 오는 날짜 형식: YYYY-MM-DD
        from datetime import datetime
        
        # 다양한 날짜 형식 처리
        date_formats = [
            '%Y-%m-%d',      # 2025-10-14
            '%Y/%m/%d',      # 2025/10/14
            '%m/%d/%Y',      # 10/14/2025
            '%d/%m/%Y',      # 14/10/2025
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt)
                return parsed_date.date().isoformat()
            except ValueError:
                continue
        
        # 파싱 실패 시 원본 반환 (이미 ISO 형식일 수 있음)
        return date_str.strip()
        
    except Exception as e:
        print(f"⚠️  날짜 파싱 오류 ({date_str}): {e}")
        return None


def update_member_permissions_from_csv(csv_file_path: str, db_path: str = 'instance/gym_system.db'):
    """CSV 파일에서 회원 권한 정보를 읽어서 데이터베이스 업데이트"""
    
    print(f"📊 CSV 파일에서 회원 권한 업데이트 시작: {csv_file_path}")
    
    # 데이터베이스 연결
    db = DatabaseManager(db_path)
    db.connect()
    
    try:
        # CSV 파일 읽기
        updated_count = 0
        error_count = 0
        
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            # 첫 번째 줄 건너뛰기 (빈 줄)
            first_line = file.readline().strip()
            if not first_line:
                print("⚠️  첫 번째 줄이 비어있습니다. 두 번째 줄을 헤더로 사용합니다.")
            
            # CSV 리더 생성 (현재 위치에서)
            csv_reader = csv.DictReader(file)
            
            # 헤더 확인
            required_columns = ['고객번호', '성별', '고객구분', '종료일']
            missing_columns = [col for col in required_columns if col not in csv_reader.fieldnames]
            if missing_columns:
                print(f"❌ 필수 컬럼이 없습니다: {missing_columns}")
                return
            
            print(f"📋 CSV 헤더: {csv_reader.fieldnames}")
            
            # 각 행 처리
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    member_id = row.get('고객번호', '').strip()
                    gender_str = row.get('성별', '').strip()
                    customer_type = row.get('고객구분', '').strip()
                    expiry_date_str = row.get('종료일', '').strip()
                    
                    if not member_id:
                        print(f"⚠️  행 {row_num}: 고객번호가 없습니다.")
                        continue
                    
                    # 성별과 회원 카테고리 파싱
                    gender = parse_gender(gender_str)
                    member_category = parse_member_category(customer_type)
                    
                    # 만료일자 파싱
                    expiry_date = parse_expiry_date(expiry_date_str)
                    
                    # 데이터베이스에서 회원 존재 확인
                    cursor = db.execute_query(
                        "SELECT member_id FROM members WHERE member_id = ?",
                        (member_id,)
                    )
                    
                    if cursor and cursor.fetchone():
                        # 기존 회원 업데이트
                        db.execute_query("""
                            UPDATE members 
                            SET gender = ?, member_category = ?, customer_type = ?, expiry_date = ?, updated_at = ?
                            WHERE member_id = ?
                        """, (gender, member_category, customer_type, expiry_date, datetime.now().isoformat(), member_id))
                        
                        updated_count += 1
                        
                        # 교직원인 경우 로그 출력
                        if member_category == 'staff':
                            print(f"👔 교직원 권한 설정: {member_id} ({customer_type}, {gender_str})")
                    else:
                        # 새 회원 생성 (기본 정보만)
                        member_name = row.get('고객명', f'회원_{member_id}').strip()
                        phone = row.get('핸드폰', '').strip()
                        
                        db.execute_query("""
                            INSERT INTO members (
                                member_id, member_name, phone, gender, 
                                member_category, customer_type, expiry_date, status,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            member_id, member_name, phone, gender,
                            member_category, customer_type, expiry_date, 'active',
                            datetime.now().isoformat(), datetime.now().isoformat()
                        ))
                        
                        updated_count += 1
                        print(f"➕ 새 회원 생성: {member_id} ({member_name}, {customer_type}, {gender_str})")
                        
                        if member_category == 'staff':
                            print(f"   👔 교직원 권한 부여됨")
                    
                except Exception as e:
                    error_count += 1
                    print(f"❌ 행 {row_num} 처리 오류: {e}")
                    continue
        
        print(f"\n✅ 회원 권한 업데이트 완료!")
        print(f"   📊 처리된 회원: {updated_count}명")
        print(f"   ❌ 오류 발생: {error_count}건")
        
        # 교직원 통계
        cursor = db.execute_query(
            "SELECT COUNT(*) as count FROM members WHERE member_category = 'staff'"
        )
        if cursor:
            staff_count = cursor.fetchone()['count']
            print(f"   👔 총 교직원: {staff_count}명")
        
        # 성별 통계
        cursor = db.execute_query("""
            SELECT gender, COUNT(*) as count 
            FROM members 
            GROUP BY gender
        """)
        if cursor:
            gender_stats = cursor.fetchall()
            for stat in gender_stats:
                gender_name = '남자' if stat['gender'] == 'male' else '여자'
                print(f"   👤 {gender_name}: {stat['count']}명")
        
    except Exception as e:
        print(f"❌ 전체 처리 오류: {e}")
    finally:
        db.close()


def main():
    """메인 함수"""
    if len(sys.argv) != 2:
        print("사용법: python update_member_permissions.py <CSV파일경로>")
        print("예시: python update_member_permissions.py '251013_유효회원목록_회원등급포함.xlsx - Sheet1.csv'")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    
    if not os.path.exists(csv_file_path):
        print(f"❌ CSV 파일을 찾을 수 없습니다: {csv_file_path}")
        sys.exit(1)
    
    update_member_permissions_from_csv(csv_file_path)


if __name__ == "__main__":
    main()
