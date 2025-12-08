# 🕐 반납 바코드/센서 시간 기록 오류 수정

## 📋 문제 발견

사용자가 반납 데이터를 확인하던 중, **반납 바코드 시간과 반납 센서 시간이 동일**한 것을 발견했습니다.

### 잘못된 데이터 예시
```
rental_id: 21
  반납 바코드: 2025-10-19T14:43:20.913123
  반납 센서:   2025-10-19T14:43:20.913123  ← 동일! ⚠️

rental_id: 20
  반납 바코드: 2025-10-19T14:41:53.235430
  반납 센서:   2025-10-19T14:41:53.235430  ← 동일! ⚠️
```

정상적으로는 **몇 초 차이**가 있어야 합니다:
- 바코드 스캔 (회원 확인 화면 진입)
- 센서 감지 (락커 키 삽입) ← 이 사이 시간 차이

---

## 🔍 원인 분석

### 잘못된 코드 (`app/api/routes.py`)

```python
# 반납 프로세스에서 센서 감지 시점에 호출됨
def process_rental():
    # 반납 시간 기록
    return_time = datetime.now().isoformat()  # ← 센서 감지 시점에만 기록
    
    # 정상 반납 처리
    locker_service.db.execute_query("""
        UPDATE rentals 
        SET return_barcode_time = ?,  # ← return_time 사용
            return_sensor_time = ?,    # ← 같은 return_time 사용! ⚠️
            ...
    """, (return_time, ..., return_time, ...))  # 둘 다 같은 값!
```

**문제:**
- 센서 감지 시점에 한 번만 시간을 기록
- `return_barcode_time`과 `return_sensor_time`에 똑같은 값 저장
- 바코드 스캔 시점은 전혀 기록하지 않음!

### 대여 프로세스는 올바름

대여는 **두 단계**로 나누어 시간을 기록합니다:

```python
# 1단계: 바코드 스캔 (app/main/routes.py)
def member_check():
    rental_time = datetime.now().isoformat()
    INSERT INTO rentals (..., rental_barcode_time, ...)
    VALUES (..., rental_time, ...)  # ← 바코드 시점 기록

# 2단계: 센서 감지 (app/api/routes.py)
def process_rental():
    sensor_time = datetime.now().isoformat()
    UPDATE rentals 
    SET rental_sensor_time = ?  # ← 센서 시점 기록 (다른 시간!)
    WHERE member_id = ? AND status = 'pending'
```

**결과:**
```
rental_barcode_time: 2025-10-19T14:41:36  ← 바코드 스캔
rental_sensor_time:  2025-10-19T14:41:40  ← 센서 감지 (4초 차이) ✅
```

---

## ✅ 수정 내용

### 1. `app/main/routes.py` - 반납 바코드 시간 기록 추가

```python
def member_check():
    # 기존: 대여만 처리
    if action == 'rental':
        # Pending 레코드 생성 + rental_barcode_time 기록
        ...
    
    # 🆕 추가: 반납도 처리
    elif action == 'return':
        try:
            return_barcode_time = datetime.now().isoformat()
            
            # 활성 대여 레코드에 return_barcode_time 업데이트
            locker_service.db.execute_query("""
                UPDATE rentals 
                SET return_barcode_time = ?, updated_at = ?
                WHERE member_id = ? AND status = 'active'
            """, (return_barcode_time, return_barcode_time, member_id))
            
            locker_service.db.conn.commit()
            
            current_app.logger.info(f'📝 반납 바코드 시간 기록: member={member_id}')
        except Exception as e:
            current_app.logger.error(f'❌ 반납 바코드 시간 기록 오류: {e}')
```

### 2. `app/api/routes.py` - 센서 시간만 업데이트하도록 수정

```python
def process_rental():
    # 센서 감지 시점
    return_time = datetime.now().isoformat()
    
    # 정상 반납 처리
    locker_service.db.execute_query("""
        UPDATE rentals 
        SET return_target_locker = ?,    # ← return_barcode_time 제거!
            return_sensor_time = ?,       # ← 센서 시간만 기록
            return_actual_locker = ?, 
            return_verified = ?, status = 'returned', 
            updated_at = ?
        WHERE member_id = ? AND status = 'active'
    """, (target_locker, return_time, actual_locker,  # ← return_time은 한 번만 사용
          1, return_time, member_id))
```

---

## 📊 수정 전/후 비교

### 수정 전 (잘못됨)
```
프로세스:
  1. 바코드 스캔 → (기록 안함) ❌
  2. 센서 감지 → return_barcode_time, return_sensor_time (동시 기록) ❌

결과:
  return_barcode_time: 2025-10-19T14:43:20.913123
  return_sensor_time:  2025-10-19T14:43:20.913123  ← 동일!
```

### 수정 후 (정상)
```
프로세스:
  1. 바코드 스캔 → return_barcode_time 기록 ✅
  2. 센서 감지 → return_sensor_time 기록 ✅

결과 (예상):
  return_barcode_time: 2025-10-19T14:43:18.123456  ← 바코드 스캔
  return_sensor_time:  2025-10-19T14:43:20.913123  ← 센서 감지 (2초 차이)
```

---

## 📝 기존 데이터 처리

### 문제
- 기존에 저장된 모든 반납 기록은 `return_barcode_time == return_sensor_time`
- 총 12건의 반납 기록이 잘못된 데이터

### 해결
- **기존 데이터는 수정하지 않음** (이력 보존)
- 새로운 반납부터 올바른 시간 기록
- 문서에 명시하여 데이터 분석 시 참고

### 데이터 구분 방법
```sql
-- 잘못된 데이터 (수정 전)
SELECT * FROM rentals 
WHERE return_barcode_time = return_sensor_time
  AND return_barcode_time IS NOT NULL;

-- 올바른 데이터 (수정 후)
SELECT * FROM rentals 
WHERE return_barcode_time != return_sensor_time
  AND return_barcode_time IS NOT NULL;
```

---

## 🧪 테스트 계획

1. **반납 프로세스 테스트**
   - 바코드 스캔 → 시간 T1 기록 확인
   - 센서 감지 → 시간 T2 기록 확인
   - T1 < T2 확인 (시간 차이 존재)

2. **DB 검증**
   ```sql
   SELECT rental_id, member_id,
          return_barcode_time,
          return_sensor_time,
          (julianday(return_sensor_time) - julianday(return_barcode_time)) * 86400 as diff_seconds
   FROM rentals
   WHERE status = 'returned'
     AND return_barcode_time IS NOT NULL
   ORDER BY created_at DESC;
   ```

3. **로그 확인**
   - 바코드 스캔 시: "반납 바코드 시간 기록" 로그 확인
   - 센서 감지 시: "반납 완료" 로그 확인

---

## 📈 영향 범위

### 긍정적 영향
- ✅ 정확한 시간 기록 (데이터 무결성)
- ✅ 프로세스 분석 가능 (바코드 → 센서 소요 시간)
- ✅ 사용자 행동 패턴 분석 가능

### 주의사항
- ⚠️ 기존 데이터는 부정확 (2025-10-19 이전)
- ⚠️ 통계 계산 시 날짜 필터링 필요

---

## 🔄 관련 이슈

### 대여 프로세스
- ✅ 이미 올바르게 구현됨
- `rental_barcode_time`과 `rental_sensor_time` 분리 기록

### 타임아웃 처리
- ✅ 정상 동작 (영향 없음)
- Pending/Active 레코드에 타임아웃 시간 기록

### 잘못된 락커 반납
- ✅ 정상 동작 (영향 없음)
- `return_barcode_time`은 유지, 재시도 시 `return_sensor_time`만 업데이트

---

## 📚 참고 자료

### 관련 파일
- `app/main/routes.py` - 바코드 스캔 처리
- `app/api/routes.py` - 센서 이벤트 처리
- `database/schema.sql` - rentals 테이블 스키마

### 관련 문서
- `docs/DATABASE_SCHEMA_GUIDE.md` - 데이터베이스 스키마 가이드
- `SYSTEM_VERIFICATION_REPORT.md` - 시스템 검증 보고서

---

**수정일**: 2025-10-19  
**발견자**: 사용자  
**수정자**: AI Assistant  
**버전**: v1.0
