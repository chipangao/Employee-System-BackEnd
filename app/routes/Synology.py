import os
from flask import Blueprint, jsonify, request, session
from datetime import datetime, timedelta
import secrets
from flask_jwt_extended import set_access_cookies
import jwt

from app.utils.auth_utils import authenticate_and_login_user

synology_bp = Blueprint('test', __name__, 
                        url_prefix='/api/synology'
                        )
url = 'http://localhost:5173'

# 🎯 配置
TOKEN_EXPIRY_MINUTES = int(os.getenv('TOKEN_EXPIRY_MINUTES', 15))
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-very-secret-key-change-in-production')
print(f"🔧 Token 過期時間設定: {TOKEN_EXPIRY_MINUTES} 分鐘")

# 🛡️ JWT Session 管理器
class JWTSessionManager:
    def __init__(self):
        self.secret_key = JWT_SECRET_KEY
        self.used_tokens = set()
        print("🆕 JWT Session 管理器初始化完成")
    
    def create_session(self, user_data):
        """創建 JWT session token"""
        jti = secrets.token_urlsafe(16)
        
        payload = {
            'user_id': user_data['user_id'],
            'username': user_data['username'],
            'display_name': user_data.get('display_name', ''),
            'email': user_data.get('email', ''),
            'jti': jti,
            'exp': datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY_MINUTES),
            'iat': datetime.utcnow(),
            'type': 'one_time'
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        
        print(f"🔒 建立 JWT session for {user_data['display_name']}")
        print(f"   - JTI: {jti}")
        
        return token
    
    def verify_for_head(self, token):
        """HEAD 請求驗證"""
        if not token:
            return False, "未提供 token"
        
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            if decoded.get('jti') in self.used_tokens:
                return False, "Token 已被使用"
            
            exp_timestamp = decoded.get('exp')
            if exp_timestamp and datetime.utcnow() > datetime.utcfromtimestamp(exp_timestamp):
                return False, "Token 已過期"
            
            return True, "有效"
            
        except jwt.DecodeError:
            return False, "無效的 token 格式"
        except Exception as e:
            return False, f"驗證錯誤: {str(e)}"
    
    def verify_and_destroy(self, token):
        """GET 請求驗證"""
        if not token:
            return None, "未提供 token"
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            jti = payload.get('jti')
            user_display_name = payload.get('display_name', '未知用戶')
            
            if jti in self.used_tokens:
                return None, "Token 已被使用"
            
            self.used_tokens.add(jti)
            
            if len(self.used_tokens) > 1000:
                self.used_tokens.clear()
            
            user_data = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'display_name': payload.get('display_name', ''),
                'email': payload.get('email', '')
            }
            
            print(f"✅ GET 驗證成功 for {user_display_name}")
            return user_data, "登入成功"
            
        except jwt.ExpiredSignatureError:
            return None, "Token 已過期"
        except jwt.InvalidTokenError as e:
            return None, "無效的 token"
        except Exception as e:
            return None, f"驗證錯誤: {str(e)}"

# 🛡️ 簡化的 Webhook Token 管理器 - 先跳過驗證進行測試
class OneTimeTokenManager:
    def __init__(self):
        self.known_tokens = set()
        # 添加一些測試 token 或從環境變數載入
        test_tokens = [
            "test_token_123",
            "synology_webhook_token"
        ]
        for token in test_tokens:
            self.known_tokens.add(token)
        print(f"🔧 載入 {len(self.known_tokens)} 個測試 token")
    
    def learn_token(self, token):
        if token:
            self.known_tokens.add(token)
            print(f"📝 學習新 token: {token}")
            return True
        return False
    
    def is_valid(self, token):
        # 暫時跳過驗證進行測試
        if token:
            print(f"🔑 收到 token: {token}")
            return True
        return False

# 初始化管理器
token_manager = OneTimeTokenManager()
session_manager = JWTSessionManager()

def parse_request_data(req):
    """解析請求數據 - 增強版"""
    print(f"📨 請求方法: {req.method}")
    print(f"📨 內容類型: {req.content_type}")
    print(f"📨 表單數據: {req.form}")
    print(f"📨 JSON 數據: {req.get_json(silent=True)}")
    print(f"📨 原始數據: {req.data}")
    
    content_type = req.content_type or ''
    
    # 嘗試多種解析方式
    if 'application/json' in content_type:
        try:
            data = req.get_json()
            print(f"✅ 解析為 JSON: {data}")
            return data
        except Exception as e:
            print(f"❌ JSON 解析失敗: {e}")
            return None
    elif 'application/x-www-form-urlencoded' in content_type:
        try:
            data = req.form.to_dict()
            print(f"✅ 解析為 Form: {data}")
            return data
        except Exception as e:
            print(f"❌ Form 解析失敗: {e}")
            return None
    else:
        # 嘗試強制解析
        try:
            data = req.get_json(force=True, silent=True)
            if data:
                print(f"✅ 強制解析為 JSON: {data}")
                return data
        except:
            pass
        
        try:
            data = req.form.to_dict()
            if data:
                print(f"✅ 解析為 Form (回退): {data}")
                return data
        except:
            pass
    
    print("❌ 所有解析方式都失敗")
    return None

# 🎯 主要路由 - 添加測試端點
@synology_bp.route("/", methods=['POST', 'GET'])
def handle_chat_webhook():
    try:
        print("=" * 50)
        print("📨 收到 Synology Chat 請求")
        
        # 如果是 GET 請求，返回測試頁面
        if request.method == 'GET':
            return jsonify({
                'status': 'online',
                'message': 'Synology Chat Webhook 服務運行中',
                'timestamp': datetime.now().isoformat()
            })
        
        data = parse_request_data(request)
        
        if not data:
            print("❌ 無法解析請求數據")
            return jsonify({
                'text': '❌ 未收到有效數據，請檢查請求格式',
                'response_type': 'ephemeral'
            }), 400
        
        print(f"📊 解析後的數據: {data}")
        
        # 驗證 webhook token (暫時跳過)
        webhook_token = data.get('token')
        print(f"🔑 Webhook Token: {webhook_token}")
        
        # 暫時跳過 token 驗證進行測試
        if not webhook_token or not token_manager.is_valid(webhook_token):
            if not token_manager.learn_token(webhook_token):
                return jsonify({
                    'text': '❌ 無效的 token',
                    'response_type': 'ephemeral'
                }), 403
        
        print("✅ Token 驗證通過")
        
        # 提取用戶資訊
        user_id = data.get('user_id')
        username = data.get('username')
        display_name = data.get('display_name', username)
        text = data.get('text', '').strip()
        
        print(f"👤 用戶: {display_name} (ID: {user_id})")
        print(f"💬 指令: {text}")
        
        # 檢查是否為登入指令
        if text and text.startswith('/login'):
            return handle_login_command(user_id, username, display_name)
        else:
            return jsonify({
                'text': '❌ 未知指令。',
                'response_type': 'ephemeral'
            })
            
    except Exception as e:
        print(f"❌ 處理錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'text': '❌ 伺服器錯誤，請聯繫管理員',
            'response_type': 'ephemeral'
        }), 500

def handle_login_command(user_id, username, display_name):
    """處理登入指令"""
    try:
        user_data = {
            'user_id': user_id,
            'username': username,
            'display_name': display_name
        }
        
        # 建立一次性 JWT session
        session_token = session_manager.create_session(user_data)
        login_url = f"{url}/auth/sso?token={session_token}"
        
        response_text = f"""🔐 **員工系統登入 - 一次性連結**

        👤 用戶：{display_name}

        請點擊下方連結登入員工管理系統：
        {login_url}

        ⚠️ **重要安全提示** :
        • 此連結只能使用一次
        • 使用後立即失效
        • 有效時間：{TOKEN_EXPIRY_MINUTES} 分鐘
        • 每次登入都需要重新獲取新連結"""

        print(f"✅ 為 {display_name} 生成登入連結: {login_url}")

        return jsonify({
            'text': response_text,
            'buttons': [{
                'action': {
                    'type': 'url',
                    'value': login_url
                },
                'title': '🚀 點此一次性登入'
            }],
            'response_type': 'ephemeral'
        })
        
    except Exception as e:
        print(f"❌ 生成登入連結失敗: {e}")
        return jsonify({
            'text': '❌ 生成登入連結失敗，請聯繫管理員',
            'response_type': 'ephemeral'
        })

# @synology_bp.route("/debug", methods=['POST'])
# def debug_webhook():
#     """調試 webhook 數據"""
#     print("=" * 50)
#     print("🐛 DEBUG 請求數據:")
#     print(f"方法: {request.method}")
#     print(f"表頭: {dict(request.headers)}")
#     print(f"表單: {request.form}")
#     print(f"JSON: {request.get_json(silent=True)}")
#     print(f"數據: {request.data}")
    
#     return jsonify({
#         'method': request.method,
#         'headers': dict(request.headers),
#         'form': request.form.to_dict(),
#         'json': request.get_json(silent=True),
#         'data': request.data.decode('utf-8') if request.data else None
#     })

@synology_bp.route('/auth/sso', methods=['GET'])
def sso_login():
    try:
        token = request.args.get('token')
        
        if not token:
            return jsonify({'success': False, 'error': '無效的登入連結'}), 400
        
        # 驗證一次性 token
        sso_user_data, message = session_manager.verify_and_destroy(token)
        
        if not sso_user_data:
            return jsonify({'success': False, 'error': message}), 400
        
        # 🎯 使用共享的認證邏輯
        result, error = authenticate_and_login_user(
            sso_user_data['username'], 
            is_sso=True
        )
        
        if error:
            return jsonify({'success': False, 'error': error}), 401
        
        response = jsonify({
            'success': True,
            'msg': 'SSO 登入成功',
            'user': result['user_info'],
            'redirect_url': '/dashboard'
        })
        
        set_access_cookies(response, result['access_token'])
        print(f"✅ 用戶 {result['user_info']['nickname']} SSO 登入成功")
        return response, 200
        
    except Exception as e:
        print(f"❌ SSO 登入錯誤: {e}")
        return jsonify({'success': False, 'error': '登入處理失敗'}), 500