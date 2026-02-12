from flask import Blueprint, json, request, jsonify
from flask_jwt_extended import (
    create_access_token, 
    get_jwt_identity, jwt_required, 
    set_access_cookies, get_jwt, 
    unset_jwt_cookies
)
from datetime import timedelta ,timedelta , timezone ,datetime
import pyotp
import os

from app.database import PostgresDBManager
from app.errors import abort_msg
from app.utils.auth_utils import authenticate_and_login_user, reset_user_password, validate_password_strength

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route("/generateOtp", methods=['GET'])
def generateOtp():
    try:
        secret_key = pyotp.random_base32()
        return jsonify({  # 使用 jsonify 而不是 json.dumps
            'status': 200,
            'otp': secret_key,
        })
    except Exception as e:
        abort_msg(e)
        
@auth_bp.route("/login_with_cookies", methods=["POST"])
def login_with_cookies():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    
    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400
    
    result, error = authenticate_and_login_user(username, password, is_sso=False)
    
    if error:
        return jsonify({"msg": error}), 401
    
    response = jsonify({
        "msg": "login successful",
        "user": result['user_info']
    })
    set_access_cookies(response, result['access_token'])
    return response, 200

@auth_bp.route("/logout_with_cookies", methods=["POST"])
def logout_with_cookies():
    try:
        response = jsonify({"msg": "logout successful"})
        unset_jwt_cookies(response)
        return response, 200
    except Exception as e:
        abort_msg(e)

@auth_bp.after_request
def refresh_expiring_jwts(response):
    # 1. 定义不刷新的端点列表（建议用集合提升查找性能）
    EXCLUDED_ENDPOINTS = {'auth.protected', 'auth.logout_with_cookies'}  # 集合查找效率更高
    
    # 2. 先检查是否在排除列表中
    if request.endpoint in EXCLUDED_ENDPOINTS:
        return response
    
    # 3. 尝试JWT刷新逻辑
    try:
        jwt_data = get_jwt()  # 只调用一次
        
        # 4. 检查JWT是否即将过期（提前5分钟刷新）
        exp_timestamp = jwt_data["exp"]
        now = datetime.now(timezone.utc)
        refresh_threshold = datetime.timestamp(now + timedelta(seconds=30))  # 更合理的阈值
        
        if refresh_threshold > exp_timestamp:
            # 5. 刷新Token
            access_token = create_access_token(
                identity=get_jwt_identity(),
                additional_claims=jwt_data.get("user_claims", {})  # 保留原claims
            )
            set_access_cookies(response, access_token)
            
    except (RuntimeError, KeyError):
        # 6. 捕获所有可能的JWT异常
        pass
    
    return response

def get_user_dict(user_data):
    """將數據庫結果轉換為字典"""
    if isinstance(user_data, dict):
        return user_data
    elif isinstance(user_data, (tuple, list)):
        # 根據查詢的字段順序映射
        return {
            'userID': user_data[0],
            'username': user_data[1],
            'nickname': user_data[2],
            'email': user_data[3],
            'role_level': user_data[4],
            'status': user_data[5],
            'last_login': user_data[6]
        }
    return {}

@auth_bp.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    try:
        current_user_identity = get_jwt_identity()
        
        # 🎯 重要：解析 JWT identity（根據您的登錄實現）
        import json
        current_username = None
        
        if isinstance(current_user_identity, str):
            try:
                # 嘗試解析 JSON 字符串
                user_data_from_jwt = json.loads(current_user_identity)
                current_username = user_data_from_jwt.get('username')
            except json.JSONDecodeError:
                # 如果不是 JSON，直接當作用戶名
                current_username = current_user_identity
        elif isinstance(current_user_identity, dict):
            # 如果已經是字典
            current_username = current_user_identity.get('username')
        
        if not current_username:
            return jsonify({
                'success': False,
                'msg': '無效的 token 內容',
                'error': 'Invalid token identity'
            }), 401
        
        # print(f"🔐 [JWT DEBUG] Current username: {current_username}")
        
        # 獲取 JWT 數據用於調試
        jwt_data = get_jwt()
        # print(f"🔐 [JWT DEBUG] JWT data: {jwt_data}")
        
        db_manager = PostgresDBManager.get_instance()
        query = """
            SELECT userID, username, nickname, email, role_level, status, last_login 
            FROM users 
            WHERE username = %s
        """
        result = db_manager.execute_query(query, (current_username,))
        
        # print(f"🔍 [DB DEBUG] Query result: {result}")
        
        if not result or len(result) == 0:
            return jsonify({
                'success': False,
                'msg': '用戶不存在或已被刪除',
                'error': 'User not found'
            }), 404
        
        # 🎯 直接處理數據庫結果，避免未定義的函數
        user_row = result[0]
        user_data = {
            'userID': user_row[0],
            'username': user_row[1],
            'nickname': user_row[2],
            'email': user_row[3],
            'role_level': user_row[4],
            'status': user_row[5],
            'last_login': user_row[6]
        }
        
        # print(f"🔍 [USER DEBUG] User data: {user_data}")
        
        # 🎯 修正狀態檢查邏輯
        allowed_statuses = [2, 3]  # 2=活躍, 3=需要重設密碼（根據您的業務需求調整）
        if user_data['status'] not in allowed_statuses:
            status_messages = {
                1: '帳號已被停用',
                4: '帳號已被永久停權', 
                5: '帳號已被凍結'
            }
            return jsonify({
                'success': False,
                'msg': status_messages.get(user_data['status'], '帳號狀態異常'),
                'error': 'Account not active',
                'status': user_data['status'],
                'allowed_statuses': allowed_statuses
            }), 403
        
        # 更新最後登入時間
        update_login_query = """
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP 
            WHERE username = %s
        """
        db_manager.execute_query(update_login_query, (current_username,), fetch=False)
        
        # 構建用戶信息響應
        user_info = {
            'userID': user_data['userID'],
            'username': user_data['username'],
            'nickname': user_data.get('nickname', user_data['username']),
            'email': user_data.get('email', ''),
            'role_level': user_data.get('role_level', 1),
            'status': user_data['status'],
            'last_login': user_data['last_login'].isoformat() if user_data['last_login'] else None
        }
        
        # 計算 token 過期時間
        from datetime import datetime
        expires_at = jwt_data.get('exp', 0)
        if expires_at:
            expires_at = datetime.fromtimestamp(expires_at).isoformat()
        
        issued_at = jwt_data.get('iat', 0) 
        if issued_at:
            issued_at = datetime.fromtimestamp(issued_at).isoformat()
        
        return jsonify({
            'success': True,
            'msg': 'Access granted',
            'user': user_info,
            'token_status': 'valid',
            'expires_at': expires_at,
            'issued_at': issued_at
        }), 200
        
    except Exception as e:
        import traceback
        print(f"❌ Protected endpoint error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'msg': 'Token validation failed',
            'error': str(e)
        }), 401

@auth_bp.route("/reset_password", methods=["POST"])
@jwt_required()
def reset_password():
    try:
        # 獲取用戶信息
        current_user = get_jwt_identity()
        user_data = json.loads(current_user)
        
        user_id = user_data.get('userID')
        current_status = user_data.get('status')
        
        if current_status != 3:
            return jsonify({"msg": "當前不需要重設密碼", "success": False}), 400
        
        data = request.get_json()
        new_password = data.get('new_password')
        
        if not new_password:
            return jsonify({"msg": "請提供新密碼", "success": False}), 400
        
        # 轉換為字符串並驗證
        new_password_str = str(new_password)
        is_valid, password_msg = validate_password_strength(new_password_str)
        if not is_valid:
            return jsonify({"msg": password_msg, "success": False}), 400
        
        # 執行數據庫更新 - 簡化版本，不處理返回結果
        db_manager = PostgresDBManager.get_instance()
        success = db_manager.execute_query("""
            UPDATE users 
            SET password_hash = crypt(%s, gen_salt('bf')),
                status = 2,
                updated_at = CURRENT_TIMESTAMP
            WHERE userID = %s AND status = 3
        """, (new_password_str, user_id))
        
        if not success:
            return jsonify({"msg": "重設密碼失敗", "success": False}), 400
        
        # 重新查詢用戶信息
        user_result = db_manager.execute_query("""
            SELECT userID, username, nickname, role_level, status 
            FROM users 
            WHERE userID = %s
        """, (user_id,))
        
        if not user_result or len(user_result) == 0:
            return jsonify({"msg": "用戶信息查詢失敗", "success": False}), 400
        
        # 安全地提取用戶信息
        user_row = user_result[0]
        user_info = {
            'userID': user_row[0] if len(user_row) > 0 else user_id,
            'username': user_row[1] if len(user_row) > 1 else user_data.get('username'),
            'nickname': user_row[2] if len(user_row) > 2 else user_data.get('nickname'),
            'role_level': user_row[3] if len(user_row) > 3 else user_data.get('role_level'),
            'status': user_row[4] if len(user_row) > 4 else 2
        }
        
        # 更新 JWT token
        identity_data = {
            "username": user_info['username'],
            "userID": user_info['userID'],
            "nickname": user_info['nickname'],
            "role_level": user_info['role_level'],
            "status": user_info['status']
        }
        
        identity = json.dumps(identity_data)
        new_access_token = create_access_token(identity=identity)
        
        response = jsonify({
            "msg": "密碼重設成功",
            "success": True,
            "user": user_info
        })
        
        set_access_cookies(response, new_access_token)
        return response, 200
        
    except Exception as e:
        print(f"重設密碼錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "msg": f"重設密碼失敗: {str(e)}",
            "success": False
        }), 500