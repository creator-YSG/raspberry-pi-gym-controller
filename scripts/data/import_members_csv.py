#!/usr/bin/env python3
"""
CSV 파일로부터 회원 데이터 일괄 등록 스크립트

실제 헬스장 회원 명단 CSV 파일을 읽어서 SQLite 데이터베이스에 등록합니다.
"""

import sys
import os
import csv
import argparse
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.member_service import MemberService
from app.models.member import Member


def parse_membership_type(program_name: str) -> str:
    """가입프로그램명을 회원권 타입으로 변환
    
    Args:
        program_name: 가입프로그램 (예: "1.헬스1개월", "1.헬스2개월7.7", "1.헬스3+1")
        
    Returns:
        회원권 타입 (모든 회원이 basic)
    """
    # 모든 회원을 일반 회원(basic)으로 처리
    return 'basic'


def parse_date(date_str: str) -> datetime:
    """날짜 문자열을 datetime 객체로 변환 (만료일은 그 날의 마지막 시간으로 설정)
    
    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD 형식)
        
    Returns:
        datetime 객체 (23:59:59로 설정)
    """
    if not date_str:
        return None
    
    try:
        # 날짜를 파싱하고 그 날의 마지막 시간(23:59:59)으로 설정
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.replace(hour=23, minute=59, second=59)
    except ValueError:
        try:
            # 다른 형식도 시도
            date_obj = datetime.strptime(date_str, '%Y/%m/%d')
            return date_obj.replace(hour=23, minute=59, second=59)
        except ValueError:
            print(f"⚠️  날짜 형식 오류: {date_str}")
            return None


def validate_member_data(row: dict) -> tuple[bool, str]:
    """회원 데이터 유효성 검증
    
    Args:
        row: CSV 행 데이터
        
    Returns:
        (유효성 여부, 오류 메시지)
    """
    # 필수 필드 확인 (CSV 헤더는 "고객번호", "고객명")
    if not row.get('고객번호'):
        return False, "고객번호가 없습니다"
    
    if not row.get('고객명'):
        return False, "고객명이 없습니다"
    
    # 만료일 확인
    expiry_date_str = row.get('종료일')
    if expiry_date_str:
        expiry_date = parse_date(expiry_date_str)
        if expiry_date and expiry_date < datetime.now():
            return False, f"만료된 회원입니다 (만료일: {expiry_date_str})"
    
    return True, ""


def import_members_from_csv(csv_file_path: str, dry_run: bool = False) -> dict:
    """CSV 파일에서 회원 데이터 가져오기
    
    Args:
        csv_file_path: CSV 파일 경로
        dry_run: 실제 등록하지 않고 시뮬레이션만 실행
        
    Returns:
        결과 딕셔너리 (성공 수, 실패 수, 중복 수, 오류 목록)
    """
    print(f"🚀 회원 데이터 일괄 등록 시작")
    print(f"📄 파일: {csv_file_path}")
    if dry_run:
        print("🔍 시뮬레이션 모드 (실제 등록하지 않음)")
    
    # 결과 카운터
    results = {
        'total': 0,
        'success': 0,
        'duplicate': 0,
        'invalid': 0,
        'error': 0,
        'errors': []
    }
    
    # MemberService 초기화
    if not dry_run:
        member_service = MemberService('instance/gym_system.db')
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            # CSV 파일 읽기
            csv_reader = csv.DictReader(file)
            
            # 전체 행 수 확인 (진행률 표시용)
            rows = list(csv_reader)
            total_rows = len(rows)
            results['total'] = total_rows
            
            print(f"📊 총 {total_rows}명 발견")
            print()
            
            # 각 행 처리
            for i, row in enumerate(rows, 1):
                # 진행률 표시
                progress = int((i / total_rows) * 50)
                progress_bar = "=" * progress + "-" * (50 - progress)
                print(f"\r진행중... [{progress_bar}] {i}/{total_rows} ({i/total_rows*100:.1f}%)", end="")
                
                # 데이터 유효성 검증
                is_valid, error_msg = validate_member_data(row)
                if not is_valid:
                    results['invalid'] += 1
                    results['errors'].append(f"{i}번 줄: {error_msg}")
                    continue
                
                # 회원 데이터 생성 (CSV 헤더에 맞춰 수정)
                member_data = {
                    'member_id': row['고객번호'].strip(),
                    'member_name': row['고객명'].strip(),
                    'phone': row.get('핸드폰', '').strip(),
                    'membership_type': parse_membership_type(row.get('프로그램명', '')),
                    'program_name': row.get('프로그램명', '').strip(),  # 프로그램명 추가
                    'membership_expires': parse_date(row.get('종료일', '')),  # membership_expires로 변경
                    'status': 'active'
                }
                
                if dry_run:
                    # 시뮬레이션 모드: 실제 등록하지 않음
                    results['success'] += 1
                else:
                    # 실제 등록
                    try:
                        result = member_service.create_member(member_data)
                        if result['success']:
                            results['success'] += 1
                        else:
                            if '이미 등록된 회원' in result.get('error', ''):
                                results['duplicate'] += 1
                            else:
                                results['error'] += 1
                                results['errors'].append(f"{i}번 줄 ({member_data['member_id']}): {result.get('error', '알 수 없는 오류')}")
                    except Exception as e:
                        results['error'] += 1
                        results['errors'].append(f"{i}번 줄 ({member_data['member_id']}): {str(e)}")
            
            print()  # 진행률 표시 다음 줄로
            
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {csv_file_path}")
        return results
    except UnicodeDecodeError:
        print(f"❌ 파일 인코딩 오류: UTF-8로 저장해주세요")
        return results
    except Exception as e:
        print(f"❌ 파일 읽기 오류: {e}")
        return results
    finally:
        if not dry_run and 'member_service' in locals():
            member_service.close()
    
    return results


def print_results(results: dict, dry_run: bool = False):
    """결과 출력
    
    Args:
        results: import_members_from_csv 결과
        dry_run: 시뮬레이션 모드 여부
    """
    print()
    print("=" * 50)
    print("📊 최종 결과")
    print("=" * 50)
    
    if dry_run:
        print("🔍 시뮬레이션 결과:")
    
    print(f"📋 전체 데이터: {results['total']}명")
    print(f"✅ 등록 성공: {results['success']}명")
    
    if results['duplicate'] > 0:
        print(f"⚠️  중복 회원: {results['duplicate']}명 (이미 존재, 건너뜀)")
    
    if results['invalid'] > 0:
        print(f"❌ 유효하지 않음: {results['invalid']}명 (만료/데이터 오류)")
    
    if results['error'] > 0:
        print(f"🚫 등록 실패: {results['error']}명")
    
    # 오류 상세 정보
    if results['errors']:
        print()
        print("오류 상세:")
        for error in results['errors'][:10]:  # 최대 10개만 표시
            print(f"  • {error}")
        
        if len(results['errors']) > 10:
            print(f"  ... 외 {len(results['errors']) - 10}개 오류")
    
    if not dry_run and results['success'] > 0:
        print()
        print("✅ 등록 완료!")
        print(f"💡 웹 인터페이스에서 바코드 스캔으로 회원 확인이 가능합니다.")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='CSV 파일로부터 회원 데이터 일괄 등록')
    parser.add_argument('csv_file', help='CSV 파일 경로')
    parser.add_argument('--dry-run', action='store_true', help='시뮬레이션 모드 (실제 등록하지 않음)')
    parser.add_argument('--encoding', default='utf-8', help='CSV 파일 인코딩 (기본값: utf-8)')
    
    args = parser.parse_args()
    
    # 파일 존재 확인
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"❌ 파일을 찾을 수 없습니다: {args.csv_file}")
        return
    
    # 확인 메시지
    if not args.dry_run:
        print(f"📄 파일: {args.csv_file}")
        confirm = input("실제로 데이터베이스에 등록하시겠습니까? (y/N): ")
        if confirm.lower() not in ['y', 'yes']:
            print("취소되었습니다.")
            return
    
    # 회원 데이터 가져오기
    results = import_members_from_csv(args.csv_file, dry_run=args.dry_run)
    
    # 결과 출력
    print_results(results, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
