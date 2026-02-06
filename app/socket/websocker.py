from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_socketio import disconnect, emit, join_room, leave_room
from app.extensions import socketio
import datetime

from app.routes.auth import logout_with_cookies

# 注意：WebSocket 不需要傳統的 Flask 藍圖路由
# 這裡創建藍圖主要是為了組織代碼結構
websocket_bp = Blueprint('websocket', __name__)

# 用於存儲用戶與其對應的 socket ID
user_connections = {}

def disconnect_user(user_id):
    """斷開指定用戶的現有連線"""
    if user_id in user_connections:
        old_sid = user_connections[user_id]
        try:
            emit('server_message', 
                {'data': '你已在其他地方登入，此連線將被斷開'}, 
                room=old_sid)
            disconnect(sid=old_sid)
        except:
            pass  # 如果舊連線已失效則忽略
        finally:
            del user_connections[user_id]

@socketio.on('connect')
@jwt_required(optional=True)  # 改為 optional 以處理初始連接
def handle_connect(auth=None):
    try:
        current_user = get_jwt_identity()
        if not current_user:
            raise disconnect()  # 如果沒有有效的 JWT，直接斷開連接
            
        # 斷開該用戶的現有連線
        if current_user in user_connections:
            disconnect_user(current_user)
        
        # 記錄新連線
        user_connections[current_user] = request.sid
        
        print(f'✅ {current_user} connected | SID: {request.sid}')
        emit('server_message', {
            'data': '連線成功',
            'is_new_connection': True
        })
    except Exception as e:
        print(f'⚠️ Connection error: {str(e)}')
        disconnect()

# 监听客户端发送的 'client_message' 事件
@socketio.on('client_message')
@jwt_required()
def handle_client_message(data):
    current_user = get_jwt_identity()
    print(f'📩 Message from {current_user} | SID: {request.sid} | Data: {data}')
    
    # Broadcast to all clients
    emit('broadcast_message', {
        'from': current_user,
        'message': data.get('text'),
        'timestamp': datetime.datetime.now().isoformat()
    }, broadcast=True)
    
    # Send private response to sender
    emit('private_message', {
        'type': 'response',
        'message': f'Received your message: "{data.get("text")}"',
        'timestamp': datetime.datetime.now().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    try:
        current_user = get_jwt_identity()
        if current_user and current_user in user_connections and user_connections[current_user] == request.sid:
            del user_connections[current_user]
        print(f'❌ Client disconnected | SID: {request.sid}')
    except Exception as e:
        # 靜默處理所有斷開錯誤
        pass

@socketio.on('join_room')
@jwt_required()
def handle_join_room(data):
    current_user = get_jwt_identity()
    room = data.get('room')
    if room:
        join_room(room)
        emit('room_message', {
            'type': 'notification',
            'message': f'{current_user} has joined room {room}',
            'timestamp': datetime.datetime.now().isoformat()
        }, room=room)
        print(f'🚪 {current_user} joined room {room}')

@socketio.on('leave_room')
@jwt_required()
def handle_leave_room(data):
    current_user = get_jwt_identity()
    room = data.get('room')
    if room:
        leave_room(room)
        emit('room_message', {
            'type': 'notification',
            'message': f'{current_user} has left room {room}',
            'timestamp': datetime.datetime.now().isoformat()
        }, room=room)
        print(f'🚪 {current_user} left room {room}')

@socketio.on('private_chat')
@jwt_required()
def handle_private_chat(data):
    current_user = get_jwt_identity()
    target_user = data.get('to')
    message = data.get('message')
    
    if target_user and message:
        # In a real app, you'd look up the target user's SID from a user connection mapping
        emit('private_message', {
            'from': current_user,
            'message': message,
            'timestamp': datetime.datetime.now().isoformat()
        }, room=request.sid)  # Just echoing back for demo
        print(f'💌 {current_user} sent private message to {target_user}')