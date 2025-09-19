"""
메인 페이지 라우트 블루프린트
"""

from flask import Blueprint

bp = Blueprint('main', __name__)

# 라우트 임포트 (순환 임포트 방지를 위해 마지막에)
from app.main import routes