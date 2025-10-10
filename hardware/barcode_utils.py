"""
라즈베리파이용 바코드 유틸리티

기존 바코드 생성기를 라즈베리파이 환경에 맞게 포팅
회원 바코드 생성, 이미지 처리, 검증 기능
"""

import hashlib
import io
from datetime import datetime
from typing import Optional, Tuple

try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("[BARCODE] python-barcode 라이브러리 없음, 스텁 모드")

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    print("[QR] qrcode 라이브러리 없음, 스텁 모드")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[PIL] Pillow 라이브러리 없음, 스텁 모드")


def generate_member_barcode(member_id: str) -> str:
    """회원 ID로 바코드 문자열 생성
    
    Args:
        member_id: 회원 식별자
        
    Returns:
        9자리 바코드 문자열
    """
    if not member_id:
        return "000000000"

    # 회원 ID를 해시하여 일관된 9자리 바코드 생성
    hash_obj = hashlib.md5(member_id.encode())
    hash_hex = hash_obj.hexdigest()

    # 16진수를 10진수로 변환하고 9자리로 맞춤
    barcode_num = int(hash_hex[:8], 16) % 1000000000
    barcode_str = f"{barcode_num:09d}"

    print(f"[BARCODE] 회원 {member_id}용 바코드 생성: {barcode_str}")
    return barcode_str


def generate_barcode_image(barcode_str: str, format: str = "PNG") -> Optional[bytes]:
    """Code128 바코드 이미지 생성
    
    Args:
        barcode_str: 바코드 문자열 (9자리)
        format: 이미지 형식 ('PNG', 'JPEG')
        
    Returns:
        이미지 바이트 데이터 또는 None
    """
    if not BARCODE_AVAILABLE:
        print("[BARCODE] 바코드 라이브러리 없음, 플레이스홀더 반환")
        return _create_stub_barcode_image(barcode_str)

    if not barcode_str or len(barcode_str) != 9 or not barcode_str.isdigit():
        print(f"[BARCODE] 잘못된 바코드 형식: {barcode_str}")
        return None

    try:
        # Code128 바코드 생성
        writer = ImageWriter()
        writer.format = format.lower()

        # 바코드 옵션 설정
        options = {
            "module_width": 0.2,        # 바 너비
            "module_height": 15.0,      # 바 높이
            "quiet_zone": 6.5,          # 여백
            "font_size": 10,            # 텍스트 크기
            "text_distance": 5.0,       # 텍스트와 바코드 간격
            "background": "white",
            "foreground": "black",
        }

        code128 = Code128(barcode_str, writer=writer)

        # 바이트 스트림으로 저장
        buffer = io.BytesIO()
        code128.write(buffer, options=options)

        image_bytes = buffer.getvalue()
        buffer.close()

        print(f"[BARCODE] Code128 이미지 생성: {barcode_str} ({len(image_bytes)} bytes)")
        return image_bytes

    except Exception as e:
        print(f"[BARCODE] 바코드 이미지 생성 실패: {e}")
        return None


def generate_qr_code_image(qr_data: str, size: int = 150) -> Optional[bytes]:
    """QR 코드 이미지 생성
    
    Args:
        qr_data: QR 코드 데이터 문자열
        size: 이미지 크기 (픽셀)
        
    Returns:
        PNG 이미지 바이트 데이터 또는 None
    """
    if not QR_AVAILABLE:
        print("[QR] QR 코드 라이브러리 없음, 플레이스홀더 반환")
        return _create_stub_qr_image(qr_data)

    if not qr_data:
        print("[QR] 빈 QR 데이터 제공됨")
        return None

    try:
        # QR 코드 생성
        qr = qrcode.QRCode(
            version=1,  # 자동 크기 조정
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        qr.add_data(qr_data)
        qr.make(fit=True)

        # 이미지 생성
        img = qr.make_image(fill_color="black", back_color="white")

        # 크기 조정
        if size != 150:  # 기본 크기가 아니면 리사이즈
            resample = Image.Resampling.LANCZOS if PIL_AVAILABLE else Image.ANTIALIAS
            img = img.resize((size, size), resample)

        # 바이트 스트림으로 변환
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")

        image_bytes = buffer.getvalue()
        buffer.close()

        print(f"[QR] QR 코드 이미지 생성: {len(qr_data)}자 -> {len(image_bytes)} bytes")
        return image_bytes

    except Exception as e:
        print(f"[QR] QR 코드 이미지 생성 실패: {e}")
        return None


def create_member_card_images(
    member_id: str, member_name: str, barcode: str, qr_token: str
) -> Tuple[Optional[bytes], Optional[bytes]]:
    """회원 카드 이미지 생성 (바코드 + QR)
    
    Args:
        member_id: 회원 식별자
        member_name: 회원 이름
        barcode: 바코드 문자열
        qr_token: QR 토큰 문자열
        
    Returns:
        (barcode_image_bytes, qr_image_bytes) 튜플
    """
    print(f"[CARD] {member_name}({member_id})용 카드 이미지 생성")

    # 바코드 이미지 생성
    barcode_image = generate_barcode_image(barcode)

    # QR 코드 이미지 생성
    qr_image = generate_qr_code_image(qr_token)

    if barcode_image and qr_image:
        print(f"[CARD] {member_id}용 이미지 모두 생성 성공")
    elif barcode_image:
        print(f"[CARD] {member_id}용 바코드 이미지만 생성")
    elif qr_image:
        print(f"[CARD] {member_id}용 QR 이미지만 생성")
    else:
        print(f"[CARD] {member_id}용 이미지 생성 실패")

    return barcode_image, qr_image


def save_card_images(
    member_id: str, 
    barcode_image: bytes, 
    qr_image: bytes, 
    output_dir: str = "cards"
) -> Tuple[str, str]:
    """카드 이미지를 파일로 저장
    
    Args:
        member_id: 회원 식별자
        barcode_image: 바코드 이미지 바이트
        qr_image: QR 이미지 바이트
        output_dir: 출력 디렉토리
        
    Returns:
        (barcode_file_path, qr_file_path) 튜플
    """
    from pathlib import Path

    # 출력 디렉토리 생성
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 파일 경로 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    barcode_file = output_path / f"{member_id}_barcode_{timestamp}.png"
    qr_file = output_path / f"{member_id}_qr_{timestamp}.png"

    try:
        # 바코드 이미지 저장
        if barcode_image:
            with open(barcode_file, "wb") as f:
                f.write(barcode_image)
            print(f"[CARD] 바코드 저장: {barcode_file}")

        # QR 이미지 저장
        if qr_image:
            with open(qr_file, "wb") as f:
                f.write(qr_image)
            print(f"[CARD] QR 코드 저장: {qr_file}")

        return str(barcode_file), str(qr_file)

    except Exception as e:
        print(f"[CARD] 이미지 저장 실패: {e}")
        return "", ""


def validate_barcode_format(barcode: str) -> bool:
    """바코드 형식 검증
    
    Args:
        barcode: 검증할 바코드 문자열
        
    Returns:
        True if 유효한 Code128 형식
    """
    if not barcode or not isinstance(barcode, str):
        return False

    barcode = barcode.strip()

    # 8-9자리 숫자 형식 확인
    if 8 <= len(barcode) <= 9 and barcode.isdigit():
        return True

    # 6-15자리 영숫자 형식도 허용
    if 6 <= len(barcode) <= 15 and barcode.isalnum():
        return True

    return False


def get_system_barcode_capabilities() -> dict:
    """시스템의 바코드 처리 능력 확인
    
    Returns:
        능력 정보 딕셔너리
    """
    return {
        "barcode_generation": BARCODE_AVAILABLE,
        "qr_generation": QR_AVAILABLE,
        "image_processing": PIL_AVAILABLE,
        "stub_mode": not (BARCODE_AVAILABLE and QR_AVAILABLE and PIL_AVAILABLE)
    }


# 스텁 함수들 (라이브러리가 없을 때 사용)

def _create_stub_barcode_image(barcode_str: str) -> bytes:
    """스텁 바코드 이미지 생성 (최소 PNG)
    
    Args:
        barcode_str: 바코드 문자열
        
    Returns:
        최소한의 이미지 데이터
    """
    # 1x1 픽셀 투명 PNG
    stub_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a"
        b"\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01"
        b"\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    print(f"[BARCODE_STUB] {barcode_str}용 플레이스홀더 생성")
    return stub_png


def _create_stub_qr_image(qr_data: str) -> bytes:
    """스텁 QR 이미지 생성 (최소 PNG)
    
    Args:
        qr_data: QR 데이터 문자열
        
    Returns:
        최소한의 이미지 데이터
    """
    # 1x1 픽셀 투명 PNG
    stub_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a"
        b"\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01"
        b"\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    print(f"[QR_STUB] {len(qr_data)}자 데이터용 플레이스홀더 생성")
    return stub_png


# 라이브러리가 없을 때 함수 오버라이드

if not BARCODE_AVAILABLE:
    def generate_barcode_image(barcode_str: str, format: str = "PNG") -> Optional[bytes]:  # noqa: F811
        print(f"[BARCODE_STUB] {barcode_str}용 플레이스홀더 모드")
        return _create_stub_barcode_image(barcode_str)


if not QR_AVAILABLE:
    def generate_qr_code_image(qr_data: str, size: int = 150) -> Optional[bytes]:  # noqa: F811
        print(f"[QR_STUB] QR 데이터용 플레이스홀더 모드")
        return _create_stub_qr_image(qr_data)

