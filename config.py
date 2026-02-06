# config.py
import os
from datetime import timedelta

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-2026-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-2026-change-in-production'
    
    # 🎯 明確使用 Cookie - 統一 Cookie 名稱
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_ACCESS_COOKIE_NAME = 'access_token_cookie'  # 統一使用這個名稱
    
    # 🚫 禁用 CSRF
    JWT_COOKIE_CSRF_PROTECT = False
    
    # Token 過期時間
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Cookie 安全配置
    JWT_COOKIE_SECURE = False  # 開發環境
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_COOKIE_HTTPONLY = True  # 防止 XSS
    
    # 禁用 WTF CSRF
    WTF_CSRF_ENABLED = False
    
    # 數據庫配置
    POSTGRES_DB = os.environ.get('POSTGRES_DB') or 'creation'
    POSTGRES_USER = os.environ.get('POSTGRES_USER') or 'chipang'
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD') or 'root'
    POSTGRES_HOST = os.environ.get('POSTGRES_HOST') or 'localhost'
    POSTGRES_PORT = os.environ.get('POSTGRES_PORT') or '5432'
    POSTGRES_MIN_CONN = os.environ.get('POSTGRES_MIN_CONN') or 1
    POSTGRES_MAX_CONN = os.environ.get('POSTGRES_MAX_CONN') or 20

    # 提前天數：在目標周一前幾天鎖定（默認 3 天）
    SCHEDULE_DAYS_BEFORE_LOCK = int(os.environ.get('SCHEDULE_DAYS_BEFORE_LOCK') or 3)
    
    # 鎖定時間：每天的具体鎖定時間點（默認 '18:00:00'）
    SCHEDULE_LOCK_TIME = os.environ.get('SCHEDULE_LOCK_TIME') or '18:00:00'
    
    # 提前周數：提前多少周開始檢查鎖定狀態（默認 2 周）
    SCHEDULE_WEEKS_AHEAD = int(os.environ.get('SCHEDULE_WEEKS_AHEAD') or 1)

    # Synology Chat 配置
    Synology_Chat_URL = os.environ.get('Synology_Chat_URL') or 'https://creationnas.com:2053/webapi/entry.cgi'
    Synology_Chat_PARAMS = os.environ.get('Synology_Chat_PARAMS') or {
            "api": "SYNO.Chat.External",
            "method": "incoming",
            "version": "2",
            "token": "BW9cvfuU4vz6kmnpBEAy8av3wDOP9WVE09lWZYxldQPnsDH2pKnqxT8j9U79NT7R"
        }
    
     
class ProductionConfig(Config):
    JWT_COOKIE_SECURE = True
    DEBUG = False
    
class DevelopmentConfig(Config):
    JWT_COOKIE_SECURE = False
    DEBUG = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}