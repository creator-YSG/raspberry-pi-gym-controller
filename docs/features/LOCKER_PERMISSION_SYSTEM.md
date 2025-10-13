# 🔐 락커 권한 시스템 가이드

## 📋 개요

헬스장 락커 시스템이 회원 구분에 따른 3개 구역 접근 권한 시스템으로 업그레이드되었습니다.

### 🏢 구역 구성
- **남자 구역 (MALE)**: M01-M70 (70개)
- **여자 구역 (FEMALE)**: F01-F50 (50개)  
- **교직원 구역 (STAFF)**: S01-S20 (20개)

## 👥 회원 구분 및 권한

### 🎓 교직원 (Staff)
- **대상**: 대학교수, 대학직원
- **권한**: 성별 구역 + 교직원 구역 모두 접근 가능
  - 남자 교직원: MALE + STAFF 구역
  - 여자 교직원: FEMALE + STAFF 구역

### 👤 일반회원 (General)  
- **대상**: 학부, 석사, 박사, 기타
- **권한**: 성별에 따른 구역만 접근 가능
  - 남자 일반회원: MALE 구역만
  - 여자 일반회원: FEMALE 구역만

## 🔧 시스템 구현

### 📊 데이터베이스 스키마 변경

```sql
-- members 테이블에 추가된 컬럼들
ALTER TABLE members ADD COLUMN gender TEXT DEFAULT 'male';          -- 성별 (male, female)
ALTER TABLE members ADD COLUMN member_category TEXT DEFAULT 'general'; -- 회원 구분 (general, staff)
ALTER TABLE members ADD COLUMN customer_type TEXT DEFAULT '학부';    -- 고객구분 (학부, 대학교수, 대학직원, 기타 등)
```

### 🏗️ 회원 모델 업데이트

```python
class Member:
    def __init__(self, ..., gender='male', member_category='general', customer_type='학부'):
        self.gender = gender
        self.member_category = member_category
        self.customer_type = customer_type
    
    @property
    def allowed_zones(self):
        """접근 가능한 락커 구역 목록"""
        zones = []
        
        # 교직원은 성별 구역 + 교직원 구역 모두 접근 가능
        if self.member_category == 'staff':
            if self.gender == 'male':
                zones.extend(['MALE', 'STAFF'])
            else:  # female
                zones.extend(['FEMALE', 'STAFF'])
        else:
            # 일반 회원은 성별 구역만 접근 가능
            if self.gender == 'male':
                zones.append('MALE')
            else:  # female
                zones.append('FEMALE')
        
        return zones
    
    def can_access_zone(self, zone: str) -> bool:
        """특정 구역 접근 가능 여부"""
        return zone in self.allowed_zones
```

### 🔒 락커 서비스 권한 체크

```python
async def rent_locker(self, locker_id: str, member_id: str) -> Dict:
    # 1. 회원 검증
    member = validation_result['member']
    
    # 2. 락카 상태 확인
    locker = self.get_locker_by_id(locker_id)
    
    # 3. 락카 구역 접근 권한 확인
    if not member.can_access_zone(locker.zone):
        return {
            'success': False,
            'error': f'{member.name}님은 {zone_names.get(locker.zone)} 구역 락카를 사용할 수 없습니다.',
            'step': 'zone_access_denied'
        }
    
    # 4. 트랜잭션 진행...
```

## 🌐 API 엔드포인트

### 회원 구역 조회
```http
GET /api/members/{member_id}/zones

Response:
{
  "success": true,
  "member_id": "20156111",
  "member_name": "김현",
  "member_category": "staff",
  "customer_type": "대학교수",
  "gender": "male",
  "allowed_zones": [
    {"zone": "MALE", "name": "남자", "accessible": true},
    {"zone": "STAFF", "name": "교직원", "accessible": true}
  ]
}
```

### 락커 목록 조회 (권한 적용)
```http
GET /api/lockers?zone=MALE&member_id=20156111

Response:
{
  "success": true,
  "lockers": [...],
  "zone": "MALE",
  "count": 70
}
```

권한이 없는 구역 접근 시:
```http
GET /api/lockers?zone=STAFF&member_id=20240838

Response (403):
{
  "success": false,
  "error": "해당 구역에 접근할 수 없습니다.",
  "allowed_zones": ["MALE"]
}
```

## 🚀 설정 및 운영

### 1. 데이터베이스 마이그레이션
```bash
# 기존 데이터베이스에 새 컬럼 추가
python3 scripts/migrate_member_permissions.py

# 또는 새로 생성
sqlite3 instance/gym_system.db < database/schema.sql
```

### 2. 회원 권한 데이터 가져오기
```bash
# CSV 파일에서 회원 권한 정보 업데이트
python3 scripts/update_member_permissions.py "회원목록.csv"
```

### 3. 시스템 테스트
```bash
# 권한 시스템 테스트
python3 scripts/test_locker_permissions.py
```

## 📈 통계 정보

현재 시스템 현황:
- **총 회원**: 350명
- **교직원**: 23명 (대학교수 + 대학직원)
- **일반회원**: 327명
- **남자**: 270명
- **여자**: 80명

## 🔍 테스트 시나리오

### ✅ 성공 케이스
1. **남자 교직원 (김현 교수)**: MALE, STAFF 구역 모두 접근 가능
2. **여자 교직원 (김진서 직원)**: FEMALE, STAFF 구역 모두 접근 가능
3. **남자 일반회원 (손준표 학생)**: MALE 구역만 접근 가능
4. **여자 일반회원 (엘레나 학생)**: FEMALE 구역만 접근 가능

### ❌ 실패 케이스
1. 남자 일반회원이 FEMALE 구역 접근 시도
2. 여자 일반회원이 MALE 구역 접근 시도
3. 일반회원이 STAFF 구역 접근 시도

## 🛠️ 문제 해결

### 회원 권한이 올바르지 않은 경우
```bash
# 특정 회원 권한 재설정
python3 scripts/update_member_permissions.py "새로운_회원목록.csv"
```

### 락커 구역 설정 확인
```sql
-- 락커 구역별 개수 확인
SELECT zone, COUNT(*) as count FROM locker_status GROUP BY zone;

-- 회원 구분별 통계
SELECT member_category, gender, COUNT(*) as count 
FROM members 
GROUP BY member_category, gender;
```

## 📝 주의사항

1. **여자 교직원 전용 락커 없음**: 여자 교직원은 일반 여자 구역 + 교직원 구역 사용
2. **남자 교직원**: 남자 구역과 교직원 구역 모두 사용 가능
3. **권한 체크**: 모든 락커 대여 시 구역 접근 권한 자동 확인
4. **실시간 적용**: 회원 정보 변경 시 즉시 권한 반영

## 🔄 업데이트 내역

- **2025-10-13**: 초기 락커 권한 시스템 구현
  - 3개 구역 시스템 도입
  - 회원 구분별 접근 권한 설정
  - API 권한 체크 로직 추가
  - CSV 데이터 가져오기 기능
  - 테스트 시스템 구축
