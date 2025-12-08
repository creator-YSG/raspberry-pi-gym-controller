# 🔧 3단계: 서비스 로직 통합 - 상세 작업 계획

> **목표**: 기존 Google Sheets 기반 서비스를 SQLite + 트랜잭션 시스템으로 통합

---

## 📋 **현재 문제점 분석**

### 🔴 **기존 시스템의 한계**
```python
# LockerService.rent_locker() - 현재 코드
def rent_locker(self, locker_id: str, member_id: str) -> Dict:
    # ❌ 문제점들:
    # 1. Google Sheets 기반 (TODO 주석만 있음)
    # 2. 트랜잭션 없음 (동시성 문제)
    # 3. 센서 검증 없음 (물리적 상태 무시)
    # 4. 하드코딩된 임시 데이터
    # 5. 에러 처리 부족
```

### 🟢 **새로운 시스템의 장점**
```python
# TransactionManager - 새로운 시스템
async def start_transaction(member_id, transaction_type):
    # ✅ 장점들:
    # 1. SQLite 기반 (안정적 데이터 저장)
    # 2. 동시성 제어 (1회원/1트랜잭션)
    # 3. 자동 타임아웃 (30초)
    # 4. 센서 이벤트 기록
    # 5. 완전한 에러 처리
```

---

## 🎯 **3단계 목표**

### 1️⃣ **서비스 통합**
- 기존 LockerService → SQLite + TransactionManager 사용
- 기존 MemberService → SQLite + 확장된 Member 모델 사용
- API 엔드포인트 → 새로운 서비스 로직 사용

### 2️⃣ **센서 검증 시스템**
- ESP32 센서 이벤트 → TransactionManager 연동
- 물리적 상태 → 데이터베이스 상태 동기화
- 실시간 검증 로직 구현

### 3️⃣ **완전한 대여/반납 플로우**
```
바코드 스캔 → 회원 검증 → 트랜잭션 시작 → 락카 선택 → 
하드웨어 제어 → 센서 검증 → 트랜잭션 완료 → DB 업데이트
```

---

## 🛠️ **상세 작업 목록**

### **Task 3.1: MemberService SQLite 통합** (1-2시간)

**현재 문제:**
```python
# app/services/member_service.py - 현재
def get_member(self, member_id: str) -> Optional[Member]:
    # TODO: 구글시트에서 실제 데이터 조회
    # 임시 테스트 데이터 (하드코딩)
    test_members = {'12345': Member(...)}  # ❌
```

**해결 방법:**
```python
# 새로운 MemberService
def __init__(self):
    self.db = DatabaseManager('locker.db')
    self.db.connect()

def get_member(self, member_id: str) -> Optional[Member]:
    # ✅ SQLite에서 실제 데이터 조회
    row = self.db.fetch_one("SELECT * FROM members WHERE member_id = ?", (member_id,))
    if row:
        return Member.from_db_row(row)
    return None
```

**작업 내용:**
- [ ] MemberService 생성자에 DatabaseManager 추가
- [ ] get_member() 메서드를 SQLite 기반으로 변경
- [ ] validate_member() 메서드 개선
- [ ] 새로운 메서드 추가: create_member(), update_member()
- [ ] 테스트 작성 및 검증

---

### **Task 3.2: LockerService 트랜잭션 통합** (2-3시간)

**현재 문제:**
```python
# app/services/locker_service.py - 현재
def rent_locker(self, locker_id: str, member_id: str) -> Dict:
    # ❌ 문제점들:
    # 1. 트랜잭션 없음
    # 2. 센서 검증 없음  
    # 3. Google Sheets TODO만 있음
    # 4. 동시성 제어 없음
```

**해결 방법:**
```python
# 새로운 LockerService
async def rent_locker(self, locker_id: str, member_id: str) -> Dict:
    # ✅ 트랜잭션 기반 안전한 처리
    
    # 1. 트랜잭션 시작
    tx_result = await self.tx_manager.start_transaction(member_id, TransactionType.RENTAL)
    if not tx_result['success']:
        return {'success': False, 'error': tx_result['error']}
    
    tx_id = tx_result['transaction_id']
    
    try:
        # 2. 회원 검증
        await self.tx_manager.update_transaction_step(tx_id, TransactionStep.MEMBER_VERIFIED)
        
        # 3. 락카 선택
        await self.tx_manager.update_transaction_step(tx_id, TransactionStep.LOCKER_SELECTED)
        
        # 4. 하드웨어 제어
        success = await self._open_locker_hardware(locker_id)
        if not success:
            await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
            return {'success': False, 'error': '락카 열기 실패'}
        
        await self.tx_manager.update_transaction_step(tx_id, TransactionStep.HARDWARE_SENT)
        
        # 5. 센서 검증 대기 (30초 타임아웃)
        await self.tx_manager.update_transaction_step(tx_id, TransactionStep.SENSOR_WAIT)
        
        # 6. 센서 이벤트 확인 (별도 핸들러에서 처리)
        # 센서가 감지되면 자동으로 SENSOR_VERIFIED로 변경됨
        
        # 7. 트랜잭션 완료
        await self.tx_manager.end_transaction(tx_id, TransactionStatus.COMPLETED)
        
        return {'success': True, 'transaction_id': tx_id}
        
    except Exception as e:
        await self.tx_manager.end_transaction(tx_id, TransactionStatus.FAILED)
        return {'success': False, 'error': str(e)}
```

**작업 내용:**
- [ ] LockerService 생성자에 DatabaseManager, TransactionManager 추가
- [ ] rent_locker() 메서드를 트랜잭션 기반으로 완전 재작성
- [ ] return_locker() 메서드를 트랜잭션 기반으로 완전 재작성
- [ ] get_available_lockers() → SQLite locker_status 테이블 사용
- [ ] get_occupied_lockers() → SQLite 기반으로 변경
- [ ] 센서 검증 로직 추가
- [ ] 테스트 작성 및 검증

---

### **Task 3.3: ESP32 센서 이벤트 통합** (2-3시간)

**현재 문제:**
```python
# app/api/routes.py - 현재
# 센서 이벤트가 단순히 저장만 됨
def add_sensor_event(sensor_num, state, timestamp=None):
    current_sensor_states[sensor_num] = state  # ❌ 단순 저장만
```

**해결 방법:**
```python
# 새로운 센서 이벤트 핸들러
async def handle_sensor_event(event_data):
    """ESP32 센서 이벤트를 트랜잭션 시스템과 연동"""
    
    sensor_num = event_data.get('sensor_num')
    state = event_data.get('state')
    locker_id = f"A{sensor_num:02d}"  # 센서 번호 → 락카 ID 매핑
    
    # 1. 활성 트랜잭션 확인
    active_txs = await tx_manager.get_active_transactions()
    
    for tx in active_txs:
        if (tx['step'] == TransactionStep.SENSOR_WAIT and 
            tx['locker_id'] == locker_id):
            
            # 2. 센서 이벤트 기록
            await tx_manager.record_sensor_event(
                tx['transaction_id'], locker_id, 
                {'sensor_num': sensor_num, 'state': state, 'active': state == 'LOW'}
            )
            
            # 3. 센서 검증 완료
            if state == 'LOW':  # 키 제거 감지
                await tx_manager.update_transaction_step(
                    tx['transaction_id'], TransactionStep.SENSOR_VERIFIED
                )
                
                # 4. 트랜잭션 완료 처리
                await tx_manager.end_transaction(
                    tx['transaction_id'], TransactionStatus.COMPLETED
                )
                
                logger.info(f"✅ 센서 검증 완료: {locker_id}")
            
            break
```

**작업 내용:**
- [ ] ESP32Manager에 센서 이벤트 핸들러 등록
- [ ] 센서 번호 → 락카 ID 매핑 로직 구현
- [ ] 트랜잭션과 센서 이벤트 연동 로직
- [ ] 실시간 센서 검증 시스템 구현
- [ ] WebSocket을 통한 실시간 UI 업데이트
- [ ] 테스트 및 검증

---

### **Task 3.4: API 엔드포인트 업데이트** (1-2시간)

**현재 문제:**
```python
# app/api/routes.py - 현재
@bp.route('/lockers/<locker_id>/rent', methods=['POST'])
def rent_locker(locker_id):
    locker_service = LockerService()  # ❌ 기존 서비스
    result = locker_service.rent_locker(locker_id, member_id)  # ❌ 동기 호출
```

**해결 방법:**
```python
# 새로운 API 엔드포인트
@bp.route('/lockers/<locker_id>/rent', methods=['POST'])
async def rent_locker(locker_id):  # ✅ 비동기
    locker_service = LockerService()  # ✅ 새로운 서비스
    result = await locker_service.rent_locker(locker_id, member_id)  # ✅ 비동기 호출
    
    if result['success']:
        # ✅ WebSocket으로 실시간 업데이트
        socketio.emit('transaction_started', {
            'transaction_id': result['transaction_id'],
            'locker_id': locker_id,
            'member_id': member_id
        })
```

**작업 내용:**
- [ ] API 엔드포인트를 비동기로 변경
- [ ] 새로운 서비스 로직 사용
- [ ] WebSocket 실시간 업데이트 추가
- [ ] 에러 처리 개선
- [ ] API 응답 형식 표준화

---

### **Task 3.5: 웹 UI 실시간 업데이트** (2-3시간)

**현재 문제:**
- 트랜잭션 진행 상황이 UI에 표시되지 않음
- 센서 검증 과정이 사용자에게 보이지 않음
- 실시간 피드백 부족

**해결 방법:**
```javascript
// 새로운 실시간 UI
socket.on('transaction_started', function(data) {
    showTransactionProgress(data.transaction_id);
});

socket.on('transaction_step_updated', function(data) {
    updateProgressBar(data.step);
    showStepMessage(data.step);
});

socket.on('sensor_verification_waiting', function(data) {
    showSensorWaitingMessage(data.locker_id);
    startSensorAnimation();
});

socket.on('transaction_completed', function(data) {
    showSuccessMessage();
    redirectToComplete();
});
```

**작업 내용:**
- [ ] WebSocket 이벤트 핸들러 추가
- [ ] 트랜잭션 진행 상황 UI 구현
- [ ] 센서 검증 대기 애니메이션
- [ ] 실시간 피드백 메시지
- [ ] 에러 상황 UI 처리

---

### **Task 3.6: 통합 테스트** (1-2시간)

**테스트 시나리오:**
1. **정상 대여 플로우**
   - 바코드 스캔 → 회원 검증 → 락카 선택 → 센서 검증 → 완료
2. **동시성 테스트**
   - 여러 사용자가 동시에 대여 시도
3. **센서 검증 테스트**
   - 센서 이벤트와 트랜잭션 연동
4. **타임아웃 테스트**
   - 30초 후 자동 정리
5. **에러 처리 테스트**
   - ESP32 연결 실패, 센서 오류 등

**작업 내용:**
- [ ] 통합 테스트 스크립트 작성
- [ ] 실제 ESP32와 연동 테스트
- [ ] 성능 테스트 (응답 시간, 메모리 사용량)
- [ ] 에러 시나리오 테스트
- [ ] 사용자 시나리오 테스트

---

## 📊 **예상 일정**

| 작업 | 예상 시간 | 우선순위 | 의존성 |
|------|-----------|----------|--------|
| **Task 3.1**: MemberService 통합 | 1-2시간 | 높음 | 없음 |
| **Task 3.2**: LockerService 통합 | 2-3시간 | 높음 | Task 3.1 |
| **Task 3.3**: 센서 이벤트 통합 | 2-3시간 | 높음 | Task 3.2 |
| **Task 3.4**: API 업데이트 | 1-2시간 | 중간 | Task 3.2, 3.3 |
| **Task 3.5**: UI 실시간 업데이트 | 2-3시간 | 중간 | Task 3.4 |
| **Task 3.6**: 통합 테스트 | 1-2시간 | 높음 | 모든 작업 |

**총 예상 시간**: 9-15시간 (1-2일)

---

## 🎯 **성공 기준**

### ✅ **완료 조건**
1. **기능적 완성도**
   - [ ] 바코드 스캔부터 완료까지 전체 플로우 작동
   - [ ] 센서 검증 시스템 정상 작동
   - [ ] 동시성 제어 정상 작동
   - [ ] 실시간 UI 업데이트 정상 작동

2. **기술적 품질**
   - [ ] 모든 기존 테스트 통과 (24개)
   - [ ] 새로운 통합 테스트 통과
   - [ ] 응답 시간 < 2초 (대여/반납)
   - [ ] 메모리 사용량 < 100MB

3. **사용자 경험**
   - [ ] 직관적인 UI 플로우
   - [ ] 명확한 피드백 메시지
   - [ ] 에러 상황 적절한 처리
   - [ ] 30초 이내 트랜잭션 완료

---

## 🚨 **위험 요소 및 대응**

### ⚠️ **기술적 위험**
1. **비동기 처리 복잡성**
   - 대응: 단계별 테스트, 로깅 강화
2. **ESP32 통신 불안정**
   - 대응: 재시도 로직, 폴백 메커니즘
3. **센서 이벤트 타이밍 이슈**
   - 대응: 버퍼링, 중복 제거 로직

### ⚠️ **일정 위험**
1. **예상보다 복잡한 통합**
   - 대응: 우선순위 조정, 단계별 완성
2. **테스트 시간 부족**
   - 대응: 핵심 기능 우선 테스트

---

## 📋 **다음 단계 (4단계) 미리보기**

3단계 완료 후 4단계에서 할 일:
- **성능 최적화**: 응답 시간 개선, 메모리 최적화
- **고급 기능**: 관리자 대시보드, 통계 리포트
- **안정성 강화**: 로그 시스템, 모니터링
- **배포 준비**: 프로덕션 설정, 백업 시스템

---

**📝 작성일**: 2025년 10월 1일  
**🎯 목표**: 완전히 작동하는 트랜잭션 기반 락카키 대여 시스템  
**⏰ 예상 완료**: 1-2일 후
