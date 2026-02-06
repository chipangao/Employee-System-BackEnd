import os
from app import create_app, socketio
import eventlet

eventlet.monkey_patch()
# 创建应用实例
app = create_app()

def main():
    # 获取环境配置
    flask_env = os.environ.get('FLASK_ENV', 'production')
    debug = flask_env == 'development'
    
    # 配置主机和端口
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    
    print(f"Starting server in {flask_env} mode")
    print(f"Server running on http://{host}:{port}")
    
    try:
        # 运行 SocketIO 服务器
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=debug,
            allow_unsafe_werkzeug=debug,
            # cors_allowed_origins="*",  # 开发环境可用 *
        )
    except OSError as e:
        print(f"无法启动服务器: {e}")
        print("\n尝试以下解决方案:")
        print("1. 使用不同的端口 (如: 5001) - 设置环境变量 FLASK_PORT=5001")
        print("2. 检查端口是否已被占用:")
        print(f"   Linux/Mac: lsof -i :{port}")
        print(f"   Windows: netstat -ano | findstr :{port}")
        print("3. 确保有足够的权限 (Linux/Mac 可能需要 sudo)")
        print("4. 如果是生产环境，考虑使用 Gunicorn:")
        print("   gunicorn --worker-class eventlet -w 1 -b :5000 wsgi:app")

if __name__ == '__main__':
    main()