/**
 * 라즈베리파이 락카키 대여기 메인 JavaScript
 * 600x1024 세로 모드 터치스크린 최적화
 */

// 전역 설정
const CONFIG = {
    FULLSCREEN_ENABLED: true,
    AUTO_EXIT_TIMEOUT: 300000, // 5분 (밀리초)
    ADMIN_PASSWORD: '1234'
};

// 앱 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 락카키 대여기 앱 시작');
    initializeApp();
});

/**
 * 앱 초기화
 */
function initializeApp() {
    // 터치 최적화 설정
    setupTouchOptimization();
    
    // 키보드 단축키 설정
    setupKeyboardShortcuts();
    
    // 시스템 상태 업데이트
    updateSystemStatus();
    
    console.log('✅ 앱 초기화 완료');
}

/**
 * 터치 최적화 설정
 */
function setupTouchOptimization() {
    // 더블탭 줌 비활성화
    document.addEventListener('touchstart', function(e) {
        if (e.touches.length > 1) {
            e.preventDefault();
        }
    }, { passive: false });
    
    // 컨텍스트 메뉴 비활성화
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    });
    
    // 드래그 비활성화
    document.addEventListener('dragstart', function(e) {
        e.preventDefault();
    });
}

/**
 * 키보드 단축키 설정
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // F11: 풀스크린 토글
        if (e.key === 'F11') {
            e.preventDefault();
            toggleFullscreen();
        }
        
        // ESC: 풀스크린 해제 방지 (키오스크 모드)
        if (e.key === 'Escape') {
            e.preventDefault();
        }
        
        // Ctrl+Alt+E: 응급 종료
        if (e.ctrlKey && e.altKey && e.key === 'e') {
            emergencyExit();
        }
    });
}

/**
 * 풀스크린 토글
 */
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        enterFullscreen();
    } else {
        exitFullscreen();
    }
}

/**
 * 풀스크린 진입
 */
function enterFullscreen() {
    const element = document.documentElement;
    
    if (element.requestFullscreen) {
        element.requestFullscreen();
    } else if (element.mozRequestFullScreen) {
        element.mozRequestFullScreen();
    } else if (element.webkitRequestFullscreen) {
        element.webkitRequestFullscreen();
    } else if (element.msRequestFullscreen) {
        element.msRequestFullscreen();
    }
}

/**
 * 풀스크린 해제
 */
function exitFullscreen() {
    if (document.exitFullscreen) {
        document.exitFullscreen();
    } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen();
    } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
    } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
    }
}

/**
 * 시스템 상태 업데이트
 */
function updateSystemStatus() {
    // API에서 시스템 상태 조회 (나중에 구현)
    // fetch('/api/system/status')
    //     .then(response => response.json())
    //     .then(data => {
    //         updateStatusDisplay(data);
    //     })
    //     .catch(error => {
    //         console.error('시스템 상태 조회 오류:', error);
    //     });
    
    // 임시 데이터로 업데이트
    const availableLockers = Math.floor(Math.random() * 10) + 20; // 20-29
    const element = document.getElementById('availableLockers');
    if (element) {
        element.textContent = `${availableLockers}개`;
    }
}

/**
 * 상태 표시 업데이트
 */
function updateStatusDisplay(statusData) {
    // 사용 가능한 락카 수
    const availableElement = document.getElementById('availableLockers');
    if (availableElement && statusData.lockers) {
        availableElement.textContent = `${statusData.lockers.available}개`;
    }
    
    // 시스템 상태
    const systemStatusElements = document.querySelectorAll('.status-value');
    systemStatusElements.forEach(element => {
        if (element.textContent.includes('상태')) {
            element.className = statusData.system_ok ? 'status-value status-ok' : 'status-value status-error';
            element.textContent = statusData.system_ok ? '정상' : '오류';
        }
    });
}

/**
 * 응급 종료
 */
function emergencyExit() {
    console.log('🚨 응급 종료 실행');
    
    // 즉시 종료 화면 표시
    document.body.innerHTML = `
        <div class="shutdown-message">
            <h1>응급 종료</h1>
            <p>프로그램이 종료되었습니다</p>
        </div>
    `;
    
    // Flask 서버에 종료 신호 전송
    fetch('/api/system/emergency-exit', { method: 'POST' })
        .catch(() => {
            // 오류 무시 (서버가 이미 종료되었을 수 있음)
        });
}

/**
 * 버튼 클릭 효과
 */
function addClickEffect(element) {
    element.style.transform = 'scale(0.95)';
    setTimeout(() => {
        element.style.transform = '';
    }, 150);
}

/**
 * 안전한 API 호출
 */
async function safeApiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            timeout: 5000,
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API 호출 오류 (${url}):`, error);
        return { success: false, error: error.message };
    }
}

// 전역 함수들 (HTML에서 직접 호출됨)
window.startLockerRental = function() {
    console.log('🗝️ 락카키 대여 시작');
    
    if (CONFIG.FULLSCREEN_ENABLED) {
        enterFullscreen();
    }
    
    // TODO: 실제 대여 화면으로 이동
    alert('락카키 대여 기능은 곧 구현됩니다!\n바코드를 스캔하여 시작하세요.');
};

window.openAdmin = function() {
    const password = prompt('관리자 비밀번호를 입력하세요:');
    
    if (password === CONFIG.ADMIN_PASSWORD) {
        console.log('👨‍💼 관리자 모드 접근');
        alert('관리자 기능은 곧 구현됩니다!');
        // TODO: 관리자 화면으로 이동
    } else if (password !== null) {
        alert('비밀번호가 틀렸습니다.');
    }
};

window.exitApplication = function() {
    console.log('❌ 종료 요청');
    document.getElementById('exitModal').classList.remove('hidden');
};

window.closeExitModal = function() {
    document.getElementById('exitModal').classList.add('hidden');
};

window.confirmExit = function() {
    console.log('✅ 종료 확인');
    
    // 풀스크린 해제
    exitFullscreen();
    
    // 종료 화면 표시
    document.body.innerHTML = `
        <div class="shutdown-message">
            <h1>프로그램 종료</h1>
            <p>잠시만 기다려주세요...</p>
        </div>
    `;
    
    // Flask 서버에 종료 신호 전송
    fetch('/api/system/shutdown', { method: 'POST' })
        .then(() => {
            setTimeout(() => {
                document.querySelector('.shutdown-message p').textContent = '화면을 닫아주세요';
                // 브라우저 닫기 시도 (키오스크 모드에서만 작동)
                window.close();
            }, 2000);
        })
        .catch(() => {
            document.querySelector('.shutdown-message').innerHTML = `
                <h1>프로그램이 종료되었습니다</h1>
                <p>화면을 닫아주세요</p>
            `;
        });
};

// 주기적 상태 업데이트 (30초마다)
setInterval(updateSystemStatus, 30000);
