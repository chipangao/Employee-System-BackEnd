# utils/auth_utils.py
from flask import json, jsonify, session
from flask_jwt_extended import create_access_token, set_access_cookies
from app.database import PostgresDBManager

def authenticate_and_login_user(username, password=None, is_sso=False):
    """共享的用戶認證和登入邏輯"""
    db_manager = PostgresDBManager.get_instance()
    
    try:
        if is_sso:
            # SSO 登入：只驗證用戶名和狀態（狀態不能是1）
            result = db_manager.execute_query("""
                SELECT userID, username, nickname, role_level, status, last_login 
                FROM users 
                WHERE username = %s 
                AND status != 1
            """, (username,))
        else:
            # 密碼登入：驗證用戶名、密碼和狀態（狀態不能是1）
            result = db_manager.execute_query("""
                SELECT userID, username, nickname, role_level, status, last_login 
                FROM users 
                WHERE username = %s 
                AND password_hash = crypt(%s, password_hash)
                AND status != 1
            """, (username, password))
        
        if not result or len(result) == 0:
            return None, "用戶不存在、密碼錯誤或帳號已停用"
        
        user = result[0]
        userID, username, nickname, role_level, status, last_login = user
        
        # 更新 last_login 時間（只有狀態2的用戶才更新）
        if status == 2 | status == 3:
            db_manager.execute_query("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP 
                WHERE userID = %s
            """, (userID,))
        
        # 🎯 修正：將字典轉換為 JSON 字符串
        identity_data = {
            "username": username,
            "userID": userID,
            "nickname": nickname,
            "role_level": role_level,
            "status": status  # 添加狀態到身份信息
        }
        identity = json.dumps(identity_data)  # 轉換為 JSON 字符串
        
        access_token = create_access_token(identity=identity)
        
        # 建立 session
        session.clear()
        session['user_id'] = userID
        session['username'] = username
        session['nickname'] = nickname
        session['role_level'] = role_level
        session['status'] = status  # 添加狀態到 session
        session['logged_in'] = True
        
        user_info = {
            'userID': userID,
            'username': username,
            'nickname': nickname,
            'role_level': role_level,
            'status': status,  # 添加狀態到用戶信息
            'last_login': last_login.isoformat() if last_login else None
        }
        
        return {
            'user_info': user_info,
            'access_token': access_token
        }, None
        
    except Exception as e:
        return None, f"數據庫錯誤: {str(e)}"

def validate_password_strength(password):
    """驗證密碼強度"""
    # 確保 password 是字符串
    if not isinstance(password, str):
        return False, "密碼必須是字符串格式"
    
    password_str = str(password)  # 強制轉換為字符串
    
    if len(password_str) < 6:
        return False, "密碼長度至少需要6個字符"
    
    if not any(c.isalpha() for c in password_str):
        return False, "密碼必須包含至少一個字母"
    
    if not any(c.isdigit() for c in password_str):
        return False, "密碼必須包含至少一個數字"
    
    return True, "密碼強度符合要求"

def reset_user_password(user_id, new_password):
    """重設用戶密碼"""
    db_manager = PostgresDBManager.get_instance()
    
    try:
        print(f"開始重設用戶 {user_id} 的密碼")
        
        # 更新密碼並將狀態改為2（活躍）
        result = db_manager.execute_query("""
            UPDATE users 
            SET password_hash = crypt(%s, gen_salt('bf')),
                status = 2,
                updated_at = CURRENT_TIMESTAMP
            WHERE userID = %s 
            AND status = 3
            RETURNING userID, username, nickname, role_level, status
        """, (new_password, user_id))
        
        print(f"數據庫更新結果: {result}")
        
        if not result or len(result) == 0:
            return None, "重設密碼失敗：用戶不存在或不需要重設密碼"
        
        user = result[0]
        userID, username, nickname, role_level, status = user
        
        print(f"更新後的用戶信息: userID={userID}, username={username}, status={status}")
        
        # 更新 JWT token 中的狀態信息
        identity_data = {
            "username": username,
            "userID": userID,
            "nickname": nickname,
            "role_level": role_level,
            "status": status
        }
        print(f"JWT identity_data: {identity_data}")
        
        identity = json.dumps(identity_data)
        new_access_token = create_access_token(identity=identity)
        print("新的 JWT token 創建成功")
        
        # 更新 session
        session['status'] = status
        print("Session 更新成功")
        
        user_info = {
            'userID': userID,
            'username': username,
            'nickname': nickname,
            'role_level': role_level,
            'status': status
        }
        
        return {
            'user_info': user_info,
            'access_token': new_access_token
        }, None
        
    except Exception as e:
        print(f"reset_user_password 函數錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"重設密碼錯誤: {str(e)}"

