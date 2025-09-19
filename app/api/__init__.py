"""
API 라우트 블루프린트
"""

from flask import Blueprint

bp = Blueprint('api', __name__)

# 라우트 임포트 (순환 임포트 방지를 위해 마지막에)
from app.api import routes