# __init__.py
from flask import Flask, request
from flask_cors import CORS
from .extensions import jwt, socketio
from .errors import abort_msg
from .database import PostgresDBManager

def create_app(config_class=None):
    app = Flask(__name__)
    
    # 配置 CORS
    CORS(app, 
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"])
    
    # 🎯 重要：必須加載配置！
    if config_class is None:
        config_class = 'config.DevelopmentConfig'
    
    if isinstance(config_class, str):
        app.config.from_object(config_class)
    else:
        app.config.from_object(config_class)
    
    # 确保 SECRET_KEY 存在
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-secret-key-2024-change-in-production'
    
    # 初始化扩展
    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", manage_session=False)
    PostgresDBManager.init_app(app)
    
    # 🎯 添加 JWT 專用調試中間件
    # @app.before_request
    # def debug_jwt_info():
    #     # 只針對 API 路由調試
    #     if request.path.startswith('/api/'):
    #         print("🔐 [JWT DEBUG] ==================================")
    #         print(f"   Path: {request.path}")
    #         print(f"   Method: {request.method}")
    #         print(f"   JWT_TOKEN_LOCATION: {app.config.get('JWT_TOKEN_LOCATION')}")
    #         print(f"   JWT_ACCESS_COOKIE_NAME: {app.config.get('JWT_ACCESS_COOKIE_NAME')}")
    #         print(f"   Cookies: {dict(request.cookies)}")
    #         print(f"   Authorization Header: {request.headers.get('Authorization')}")
    #         print("🔐 [JWT DEBUG] ==================================")
    
    # 注册蓝图
    from .routes.auth import auth_bp
    from .routes.users import users_bp
    from .routes.Synology import synology_bp
    from .routes.schedules import schedules_bp
    from .routes.shift_types import shift_types_bp
    from .socket.websocker import websocket_bp
    from .routes.leave import leave_bp
    
    # app.register_blueprint(db_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(synology_bp)
    app.register_blueprint(websocket_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(shift_types_bp)
    app.register_blueprint(leave_bp)
    
    # 错误处理
    app.errorhandler(Exception)(abort_msg)
    
    return app