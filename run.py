import os

# from flask import config
from app import create_app, socketio
from socket import SO_REUSEADDR, SOL_SOCKET

import config

app = create_app()

if __name__ == '__main__':
    print(os.environ.get('FLASK_ENV'))
    try:
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=5000, 
                    debug=True)
    except OSError as e:
        print(f"無法啟動服務器: {e}")
        print("嘗試以下解決方案:")
        print("1. 使用不同的端口 (如5001)")
        print("2. 檢查端口是否已被佔用")
        print("3. 確保有足夠的權限")