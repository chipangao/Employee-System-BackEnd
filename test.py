from flask import Flask, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # 允许跨域

# 监听连接事件
@socketio.on('connect')
def handle_connect():
    print(f'✅ 客户端连接成功 | SID: {request.sid}')
    emit('server_message', {'data': '欢迎连接!你的SID: ' + request.sid})

# 监听客户端发送的 'client_message' 事件
@socketio.on('client_message')
def handle_client_message(json):
    print(f'📩 收到客户端消息 | SID: {request.sid} | 数据: {json}')
    emit('server_response', {'data': f'已收到你的消息: "{json["text"]}"'})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)