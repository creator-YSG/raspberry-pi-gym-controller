# 락카키 대여기 ↔ 운동복 대여기 통합 API 명세서

## 📋 개요

운동복/수건 대여기가 **NFC 태그를 인식**하면, 락카키 대여기 API를 호출하여 **현재 해당 락카를 빌리고 있는 회원 정보**를 실시간으로 조회할 수 있습니다.

### 시스템 구성

```
┌──────────────────────┐                    ┌──────────────────┐
│  운동복/수건 대여기   │                    │  락카키 대여기    │
│                      │                    │                  │
│  1. NFC 태그 인식    │                    │  - 락카 배정     │
│     (5A41B914524189) │ ──HTTP GET──>      │  - 회원 관리     │
│                      │                    │  - API 제공      │
│  2. 회원 정보 수신   │ <────응답────      │  - NFC 매핑 관리 │
│     (ID, 이름)       │                    │                  │
└──────────────────────┘                    └──────────────────┘
```

---

## 🔌 API 엔드포인트

### 주 API: NFC UID로 회원 정보 조회 ⭐ **필수**

운동복 대여기가 NFC 태그를 인식했을 때 호출하는 메인 API입니다.

#### 엔드포인트

```
GET /api/member/by-nfc/{nfc_uid}
```

#### 요청 예시

```bash
GET http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189
```

#### 응답 예시

**✅ 성공 (200 OK) - 대여 중인 락카**
```json
{
  "status": "ok",
  "locker_number": "M01",
  "member_id": "20240861",
  "name": "쩐부테쑤안",
  "assigned_at": "2025-12-09 10:33:52"
}
```

**❌ 락카 미배정 (404 Not Found) - 빈 락카**
```json
{
  "status": "error",
  "locker_number": "S01",
  "nfc_uid": "5AE17DD3514189",
  "message": "해당 락카가 배정되어 있지 않습니다"
}
```

**❌ 등록되지 않은 NFC (404 Not Found)**
```json
{
  "status": "error",
  "nfc_uid": "UNKNOWN123456",
  "message": "해당 락카가 배정되어 있지 않습니다"
}
```

**❌ 회원 정보 없음 (404 Not Found)**
```json
{
  "status": "error",
  "locker_number": "M01",
  "member_id": "20240861",
  "message": "회원 정보를 찾을 수 없습니다"
}
```

**❌ 서버 오류 (500 Internal Server Error)**
```json
{
  "status": "error",
  "message": "서버 오류"
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `status` | string | ✅ | 응답 상태 (`ok` 또는 `error`) |
| `locker_number` | string | ✅ | 락카 번호 (예: M01, F05, S10) |
| `member_id` | string | ✅ | 회원 ID (바코드 번호) |
| `name` | string | ✅ | 회원 이름 |
| `assigned_at` | string | ⚪ | 락카 배정 시각 (YYYY-MM-DD HH:MM:SS) |
| `nfc_uid` | string | ⚪ | NFC UID (에러 시에만 포함) |
| `message` | string | ⚪ | 에러 메시지 (에러 시에만 포함) |

**⚠️ 중요 사항:**
- **금액권/구독권 정보는 포함하지 않음** (운동복 대여기 로컬 DB에서 조회)
- **회원 ID와 이름만 전달** (개인정보 최소화)
- **NFC UID → 락카 번호 매핑은 락카키 대여기에서 자동 처리**

---

## 📝 NFC UID 샘플 데이터

현재 등록된 NFC 태그 예시:

| NFC UID | 락카 번호 | 구역 | 상태 |
|---------|----------|------|------|
| `5A41B914524189` | M01 | 남성 | 대여 중 |
| `5AE17DD3514189` | S01 | 교직원 | 비어있음 |

> **참고**: 실제 운영 환경에서는 60개의 락카에 각각 고유한 NFC UID가 할당됩니다.

---

## 💻 운동복 대여기 구현 예시

### Python (Flask/Django)

```python
import requests

LOCKER_API_URL = "http://192.168.0.23:5000"  # 락카키 대여기 IP
TIMEOUT = 2.0  # 2초 타임아웃

def get_member_by_nfc(nfc_uid: str):
    """
    NFC UID로 회원 정보 조회
    
    Args:
        nfc_uid: NFC 태그 UID (예: "5A41B914524189")
    
    Returns:
        dict: 회원 정보 또는 None
    """
    try:
        response = requests.get(
            f"{LOCKER_API_URL}/api/member/by-nfc/{nfc_uid}",
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'member_id': data['member_id'],
                'name': data['name'],
                'locker_number': data['locker_number'],
                'assigned_at': data.get('assigned_at', '')
            }
        elif response.status_code == 404:
            print(f"[API] 락카 미배정: NFC {nfc_uid}")
            return None
        else:
            print(f"[API] 오류: {response.status_code}")
            return None
            
    except requests.Timeout:
        print(f"[API] 타임아웃: 락카키 대여기 응답 없음")
        return None
    except requests.ConnectionError:
        print(f"[API] 연결 실패: 락카키 대여기 서버 다운")
        return None
    except Exception as e:
        print(f"[API] 예외 발생: {e}")
        return None


# 사용 예시
nfc_uid = "5A41B914524189"  # NFC 리더에서 읽은 UID
member = get_member_by_nfc(nfc_uid)

if member:
    print(f"회원 확인: {member['name']} ({member['member_id']})")
    print(f"락카 번호: {member['locker_number']}")
    # 운동복 대여 처리...
else:
    print("회원 정보를 찾을 수 없습니다")
```

### JavaScript (Node.js/Express)

```javascript
const axios = require('axios');

const LOCKER_API_URL = "http://192.168.0.23:5000";
const TIMEOUT = 2000; // 2초 타임아웃

async function getMemberByNFC(nfcUid) {
  try {
    const response = await axios.get(
      `${LOCKER_API_URL}/api/member/by-nfc/${nfcUid}`,
      { timeout: TIMEOUT }
    );
    
    if (response.status === 200 && response.data.status === 'ok') {
      return {
        memberId: response.data.member_id,
        name: response.data.name,
        lockerNumber: response.data.locker_number,
        assignedAt: response.data.assigned_at
      };
    }
    
    return null;
  } catch (error) {
    if (error.response?.status === 404) {
      console.log(`[API] 락카 미배정: NFC ${nfcUid}`);
    } else if (error.code === 'ECONNABORTED') {
      console.log('[API] 타임아웃');
    } else {
      console.log(`[API] 오류: ${error.message}`);
    }
    return null;
  }
}

// 사용 예시
(async () => {
  const nfcUid = "5A41B914524189"; // NFC 리더에서 읽은 UID
  const member = await getMemberByNFC(nfcUid);
  
  if (member) {
    console.log(`회원 확인: ${member.name} (${member.memberId})`);
    console.log(`락카 번호: ${member.lockerNumber}`);
    // 운동복 대여 처리...
  } else {
    console.log("회원 정보를 찾을 수 없습니다");
  }
})();
```

---

## 🧪 테스트 방법

### 1. 로컬 테스트 (curl)

```bash
# 성공 케이스 (대여 중인 락카)
curl http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189

# 실패 케이스 (빈 락카)
curl http://192.168.0.23:5000/api/member/by-nfc/5AE17DD3514189

# 헬스 체크
curl http://192.168.0.23:5000/api/health
```

### 2. Python 테스트 스크립트

```python
import requests
import json

def test_nfc_api():
    """NFC API 테스트"""
    test_cases = [
        ("5A41B914524189", "M01 대여중 - 성공 예상"),
        ("5AE17DD3514189", "S01 비어있음 - 404 예상"),
        ("INVALID_UID", "잘못된 UID - 404 예상")
    ]
    
    for nfc_uid, description in test_cases:
        print(f"\n테스트: {description}")
        print(f"NFC UID: {nfc_uid}")
        
        response = requests.get(
            f"http://192.168.0.23:5000/api/member/by-nfc/{nfc_uid}"
        )
        
        print(f"응답 코드: {response.status_code}")
        print(f"응답 데이터:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    test_nfc_api()
```

---

## 🔧 트러블슈팅

### 문제 1: 연결 실패 (Connection Refused)

**원인:**
- 락카키 대여기 API 서버 미실행
- 방화벽 차단
- 잘못된 IP 주소

**해결:**
```bash
# 1. 락카키 대여기에서 서버 실행 확인
ssh pi@192.168.0.23 'ps aux | grep "python3 run.py"'

# 2. 포트 리스닝 확인
ssh pi@192.168.0.23 'netstat -tlnp | grep 5000'

# 3. 헬스 체크로 연결 확인
curl http://192.168.0.23:5000/api/health
```

### 문제 2: 타임아웃

**원인:**
- 네트워크 지연
- 서버 과부하

**해결:**
- 타임아웃 시간을 늘림 (2초 → 5초)
- 네트워크 상태 확인 (ping 테스트)

### 문제 3: 404 Not Found (락카 미배정)

**원인:**
- NFC UID가 DB에 등록되지 않음
- 락카가 비어있음 (대여 중이 아님)

**해결:**
- 락카키 대여기 관리자에게 문의
- NFC UID가 올바른지 확인
- 테스트용 NFC UID 사용: `5A41B914524189` (M01 대여중)

---

## 📊 API 흐름도

```
[운동복 대여기]
     ↓
1. NFC 리더로 태그 인식
   NFC UID: "5A41B914524189"
     ↓
2. HTTP GET 요청
   → http://192.168.0.23:5000/api/member/by-nfc/5A41B914524189
     ↓
[락카키 대여기]
     ↓
3. NFC UID → 락카 번호 매핑
   "5A41B914524189" → "M01"
     ↓
4. 락카 번호 → 대여 정보 조회
   "M01" → 회원 "20240861" (쩐부테쑤안)
     ↓
5. 회원 정보 응답
   {"status": "ok", "member_id": "20240861", "name": "쩐부테쑤안", ...}
     ↓
[운동복 대여기]
     ↓
6. 회원 정보 수신
   - 운동복 대여기 로컬 DB에서 금액권/구독권 조회
   - 운동복 대여 처리
```

---

## 🔐 보안 고려사항

### 현재 (개발 단계)
- ✅ 인증 없음 (같은 LAN 내부 통신)
- ✅ 평문 HTTP

### 향후 (프로덕션)
- 🔒 API Key 인증 (헤더)
- 🔒 HTTPS (TLS/SSL)
- 🔒 IP 화이트리스트
- 🔒 Rate Limiting (DDoS 방지)

---

## 📞 문의 및 지원

- **락카키 대여기 시스템**: `/Users/yunseong-geun/Projects/raspberry-pi-gym-controller`
- **운동복 대여기 시스템**: `/Users/yunseong-geun/Projects/gym-rental-system`
- **API 서버 주소**: `http://192.168.0.23:5000`
- **헬스 체크**: `GET /api/health`

---

## 📅 버전 이력

- **v1.0.0** (2025-12-09): NFC UID 기반 회원 조회 API 구현
  - `/api/member/by-nfc/{nfc_uid}` 엔드포인트 추가
  - NFC UID → 락카 번호 자동 매핑
  - 회원 정보 실시간 조회
  - 에러 처리 및 응답 형식 표준화

