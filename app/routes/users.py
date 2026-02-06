from datetime import datetime
from flask import Blueprint, json, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from math import ceil

from app.database import PostgresDBManager

users_bp = Blueprint('users', __name__, url_prefix='/api/users')

@users_bp.route("/", methods=['GET'])
@jwt_required()
def getUsersList():
    """
    查看用戶表接口 - 不顯示自己的資料
    """
    db_manager = PostgresDBManager.get_instance()
    
    try:
        # 🎯 獲取當前用戶信息
        current_user_identity = get_jwt_identity()
        import json
        current_user = {}
        if isinstance(current_user_identity, str):
            try:
                current_user = json.loads(current_user_identity)
            except json.JSONDecodeError:
                current_user = {'username': current_user_identity}
        
        current_username = current_user.get('username')
        # print(f"🔐 [JWT DEBUG] Current user for list: {current_username}")
        
        # 獲取查詢參數
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '', type=str)
        role_filter = request.args.get('role', type=int)
        status_filter = request.args.get('status', type=int)
        sort_by = request.args.get('sort_by', 'ID', type=str)
        sort_order = request.args.get('sort_order', 'asc', type=str)
        
        # 驗證參數
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 10
        
        # 計算偏移量
        offset = (page - 1) * per_page
        
        # 構建查詢條件
        where_conditions = []
        query_params = []
        
        # 🎯 排除當前用戶自己的資料
        if current_username:
            where_conditions.append("username != %s")
            query_params.append(current_username)
        
        if search:
            where_conditions.append("(userID ILIKE %s OR username ILIKE %s OR nickname ILIKE %s OR email ILIKE %s)")
            search_term = f"%{search}%"
            query_params.extend([search_term, search_term, search_term, search_term])
        
        if role_filter is not None:
            where_conditions.append("role_level = %s")
            query_params.append(role_filter)
        
        if status_filter is not None:
            where_conditions.append("status = %s")
            query_params.append(status_filter)
        
        # 構建 WHERE 子句
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # 驗證排序字段
        allowed_sort_fields = ['ID', 'userID', 'username', 'nickname', 'email', 'role_level', 'status', 'created_at', 'last_login']
        if sort_by not in allowed_sort_fields:
            sort_by = 'ID'
        
        # 驗證排序方向
        if sort_order.lower() not in ['asc', 'desc']:
            sort_order = 'asc'
        
        # 構建排序子句
        order_clause = f"ORDER BY {sort_by} {sort_order}"
        
        # 查詢總數
        count_query = f"SELECT COUNT(*) FROM users {where_clause}"
        
        total_count = db_manager.execute_query(count_query, tuple(query_params))
        total_records = total_count[0][0] if total_count else 0
        total_pages = ceil(total_records / per_page) if total_records > 0 else 1
        
        # 查詢用戶數據
        data_query = f"""
        SELECT           
            userID,
            username,
            nickname,
            email,
            role_level,
            status,
            last_login,
            created_at,
            updated_at,
            webhook
        FROM users 
        {where_clause}
        {order_clause}
        LIMIT %s OFFSET %s
        """
        
        # 添加分頁參數
        query_params.extend([per_page, offset])
        
        users_data = db_manager.execute_query(data_query, tuple(query_params))
        
        # 格式化響應數據
        users_list = []
        for user in users_data:
            try:
                user_dict = {
                    'userID': user[0],  # userID
                    'username': user[1],  # username
                    'nickname': user[2],  # nickname
                    'email': user[3],  # email
                    'role_level': user[4],  # role_level
                    'status': user[5],  # status
                    'webhook': user[9]  # webhook
                }
                
                # 處理日期字段，確保不為 None
                if user[6]:  # last_login
                    user_dict['last_login'] = user[6].isoformat()
                else:
                    user_dict['last_login'] = None
                    
                if user[7]:  # created_at
                    user_dict['created_at'] = user[7].isoformat()
                else:
                    user_dict['created_at'] = None
                    
                if user[8]:  # updated_at
                    user_dict['updated_at'] = user[8].isoformat()
                else:
                    user_dict['updated_at'] = None
                    
                users_list.append(user_dict)
                
            except Exception as e:
                print(f"處理用戶數據時出錯 {user[0]}: {e}")
                # 跳過有問題的用戶，繼續處理其他用戶
                continue
        
        # 構建響應
        response = {
            'success': True,
            'data': {
                'users': users_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_records': total_records,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages
                },
                'filters': {
                    'search': search,
                    'role': role_filter,
                    'status': status_filter,
                    'sort_by': sort_by,
                    'sort_order': sort_order
                },
                # 🎯 添加當前用戶信息用於調試
                'current_user': current_username
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        import traceback
        print(f"💥 [ERROR] getUsersList exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'伺服器錯誤: {str(e)}'
        }), 500

@users_bp.route("", methods=['POST'])
@jwt_required()
def addUser():
    """
    新增用戶接口（包含 Webhook 支持）
    """
    try:
        current_user_identity = get_jwt_identity()
        current_user = {}

        if isinstance(current_user_identity, str):
            try:
                current_user = json.loads(current_user_identity)
            except json.JSONDecodeError:
                current_user = {'username': current_user_identity}
        
        # 檢查權限
        if current_user.get('role_level') != 5:
            return jsonify({
                'success': False,
                'message': '未授權的操作'
            }), 401
            
        data = request.get_json()
        print("接收到的新增用戶數據:", data)
        
        # 驗證必填字段
        required_fields = ['userID', 'username', 'email', 'nickname', 'password', 'role_level']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'缺少必要字段: {field}'
                }), 400
        
        db_manager = PostgresDBManager.get_instance()
        
        # 檢查用戶ID是否已存在
        existing_userid = db_manager.execute_query(
            "SELECT userID FROM users WHERE userID = %s", 
            (data['userID'],)
        )
        if existing_userid:
            return jsonify({
                'success': False,
                'message': '用戶ID已存在'
            }), 400
        
        # 檢查用戶名是否已存在
        existing_username = db_manager.execute_query(
            "SELECT userID FROM users WHERE username = %s", 
            (data['username'],)
        )
        if existing_username:
            return jsonify({
                'success': False,
                'message': '用戶名已存在'
            }), 400
        
        # 檢查郵箱是否已存在
        existing_email = db_manager.execute_query(
            "SELECT userID FROM users WHERE email = %s", 
            (data['email'],)
        )
        if existing_email:
            return jsonify({
                'success': False,
                'message': '電子郵件已存在'
            }), 400
        
        # 驗證郵箱格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data['email']):
            return jsonify({
                'success': False,
                'message': '電子郵件格式不正確'
            }), 400
        
        # 驗證 Webhook URL 格式（如果提供）
        if 'webhook' in data and data['webhook']:
            webhook_url = data['webhook']
            if webhook_url.strip():
                url_pattern = r'^https?://.+'
                if not re.match(url_pattern, webhook_url):
                    return jsonify({
                        'success': False,
                        'message': 'Webhook URL 格式不正確，必須是有效的 HTTP/HTTPS URL'
                    }), 400
        
        # 驗證角色等級
        if data['role_level'] not in [2, 3, 4, 5]:
            return jsonify({
                'success': False,
                'message': '角色等級無效'
            }), 400
        
        # 驗證密碼長度
        if len(data['password']) < 6:
            return jsonify({
                'success': False,
                'message': '密碼長度至少需要6個字符'
            }), 400
        
        # 構建插入查詢
        query = """
            INSERT INTO users (
                userID, 
                username, 
                email, 
                nickname, 
                password_hash,
                role_level,
                status,
                created_by,
                webhook  -- 新增 webhook 字段
            ) VALUES (
                %s, %s, %s, %s, 
                crypt(%s, gen_salt('bf')), 
                %s, %s, %s, %s
            )
            RETURNING ID, userID, username, nickname, email, role_level, status, created_at, webhook
        """
        
        # 默認狀態為活躍（2），除非指定其他狀態
        status = data.get('status', 2)
        if status not in [1, 2, 3]:
            status = 2
        
        # 執行插入
        result = db_manager.execute_returning(
            query,
            (
                data['userID'],
                data['username'],
                data['email'],
                data['nickname'],
                data['password'],
                data['role_level'],
                status,
                current_user.get('username', '系統'),
                data.get('webhook', '')  # 傳遞 webhook，默認為空字串
            )
        )
        
        if result:
            user_data = result[0]
            return jsonify({
                'success': True,
                'message': '用戶新增成功',
                'data': {
                    'user': {
                        'ID': user_data[0],
                        'userID': user_data[1],
                        'username': user_data[2],
                        'nickname': user_data[3],
                        'email': user_data[4],
                        'role_level': user_data[5],
                        'status': user_data[6],
                        'created_at': user_data[7].isoformat() if user_data[7] else None,
                        'webhook': user_data[8]  # 返回 webhook 字段
                    }
                }
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': '用戶新增失敗'
            }), 500
            
    except Exception as e:
        import traceback
        print(f"💥 [ERROR] addUser exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'伺服器錯誤: {str(e)}'
        }), 500
        
@users_bp.route("/<string:userID>", methods=['PUT'])
@jwt_required()
def updateUser(userID):
    """
    修改用戶信息接口（包含 Webhook 支持）
    """
    try:
        current_user_identity = get_jwt_identity()
        current_user = {}

        if isinstance(current_user_identity, str):
            try:
                current_user = json.loads(current_user_identity)
            except json.JSONDecodeError:
                current_user = {'username': current_user_identity}
        
        # 檢查權限
        if current_user.get('role_level') != 5:
            return jsonify({
                'success': False,
                'message': '未授權的操作'
            }), 401
            
        data = request.get_json()
        print("接收到的更新數據:", data)
        
        db_manager = PostgresDBManager.get_instance()
        
        # 檢查用戶是否存在（包含 webhook 字段）
        existing_user = db_manager.execute_query(
            "SELECT ID, userID, username, nickname, email, role_level, status, last_login, created_at, updated_at, webhook FROM users WHERE userID = %s", 
            (userID,)
        )
       
        if not existing_user:
            return jsonify({
                'success': False,
                'message': '用戶不存在'
            }), 404
        
        # 保存原始用戶數據用於響應
        original_user_data = existing_user[0]
        original_username = original_user_data[2]  # username 在索引 2
        original_status = original_user_data[6]    # status 在索引 6
        original_webhook = original_user_data[10]  # webhook 在索引 10
        
        # 🎯 確定最終狀態：優先使用請求中的新狀態，如果沒有則使用原始狀態
        final_status = data.get('status', original_status)
        if final_status is None:
            final_status = original_status
        
        print(f"🔍 狀態信息 - 原始: {original_status}, 請求: {data.get('status')}, 最終: {final_status}")
        
        # 構建更新字段和值
        update_fields = []
        update_values = []
        
        # 對 username 修改添加特殊檢查
        if 'username' in data and data['username'] and data['username'] != original_username:
            print(f"🔍 檢測到 username 修改: {original_username} -> {data['username']}")
            
            # 1. 檢查 username 是否已被使用
            existing_username = db_manager.execute_query(
                "SELECT userID FROM users WHERE username = %s AND userID != %s", 
                (data['username'], userID)
            )
            if existing_username:
                return jsonify({
                    'success': False,
                    'message': '用戶名已被其他用戶使用'
                }), 400
            
            # 2. 添加 username 到更新字段
            update_fields.append("username = %s")
            update_values.append(data['username'])
            print(f"✅ username 已添加到更新字段")
        
        # 🎯 對 status 修改添加特殊檢查
        if 'status' in data and data['status'] is not None:
            new_status = data['status']
            print(f"🔍 檢測到 status 修改: {original_status} -> {new_status}")
            
            # 檢查 status 修改規則
            if original_status == 3:  # 如果原本狀態是 3（重設密碼）
                if new_status not in [1, 3]:  # 只能修改為 1（停用）或 3（重設密碼）
                    return jsonify({
                        'success': False,
                        'message': '狀態為「重設密碼」的用戶只能修改為「停用」或保持「重設密碼」狀態'
                    }), 400
            
            # 檢查 status 值是否有效
            if new_status not in [1, 2, 3]:
                return jsonify({
                    'success': False,
                    'message': '狀態值無效，必須為 1（停用）、2（活躍）或 3（重設密碼）'
                }), 400
            
            # 只有當 status 實際改變時才添加到更新字段
            if new_status != original_status:
                update_fields.append("status = %s")
                update_values.append(new_status)
                print(f"✅ status 已添加到更新字段: {original_status} -> {new_status}")
            else:
                print("ℹ️ status 沒有變化，不添加到更新字段")
        
        # 🎯 Webhook 更新處理
        if 'webhook' in data:
            webhook_url = data['webhook']
            print(f"🔍 檢測到 webhook 修改: {original_webhook} -> {webhook_url}")
            
            # 驗證 Webhook URL 格式（可選）
            if webhook_url and webhook_url.strip():
                import re
                url_pattern = r'^https?://.+'
                if not re.match(url_pattern, webhook_url):
                    return jsonify({
                        'success': False,
                        'message': 'Webhook URL 格式不正確，必須是有效的 HTTP/HTTPS URL'
                    }), 400
            
            # 如果提供了空字串，表示清除 Webhook
            if webhook_url == "":
                update_fields.append("webhook = NULL")
                print("✅ Webhook 設置為 NULL")
            # 只有當 Webhook 實際改變時才添加到更新字段
            elif webhook_url != original_webhook:
                update_fields.append("webhook = %s")
                update_values.append(webhook_url)
                print(f"✅ Webhook 已添加到更新字段")
            else:
                print("ℹ️ Webhook 沒有變化，不添加到更新字段")
                        
        # 處理其他字段的更新
        other_fields = ['nickname', 'email', 'role_level']
        for field in other_fields:
            if field in data and data[field] is not None:
                # 檢查值是否實際改變
                original_value = original_user_data[
                    3 if field == 'nickname' else 
                    4 if field == 'email' else 
                    5  # role_level
                ]
                if data[field] != original_value:
                    update_fields.append(f"{field} = %s")
                    update_values.append(data[field])
                    print(f"✅ {field} 已添加到更新字段: {original_value} -> {data[field]}")
        
        # 🎯 修改密碼處理邏輯：使用最終狀態來判斷密碼規則
        # status === 1（停用）: 密碼不可提交，保持原密碼
        # status === 2（活躍）: 密碼不可提交，保持原密碼
        # status === 3（重設密碼）: 必須提交密碼，密碼長度至少6個字符
        
        if 'password' in data and data['password']:
            # 如果提供了密碼，檢查狀態規則
            if final_status in [1, 2]:  # 最終狀態為停用或活躍
                return jsonify({
                    'success': False,
                    'message': f'狀態為「{"停用" if final_status == 1 else "活躍"}」的用戶不能修改密碼'
                }), 400
            
            elif final_status == 3:  # 最終狀態為重設密碼
                # 檢查密碼長度
                if len(data['password']) < 6:
                    return jsonify({
                        'success': False,
                        'message': '重設密碼狀態的用戶，密碼長度至少需要6個字符'
                    }), 400
                
                # 添加密碼到更新字段
                update_fields.append("password_hash = crypt(%s, gen_salt('bf'))")
                update_values.append(data['password'])
                print("✅ 密碼已添加到更新字段（重設密碼狀態）")
        
        else:
            # 如果沒有提供密碼，檢查最終狀態是否為重設密碼
            if final_status == 3:
                return jsonify({
                    'success': False,
                    'message': '重設密碼狀態的用戶必須提供新密碼'
                }), 400
        
        # 如果沒有要更新的字段
        if not update_fields:
            return jsonify({
                'success': False,
                'message': '沒有提供要更新或沒有變化'
            }), 400
        
        # 檢查郵箱是否與其他用戶衝突（如果更新郵箱）
        if 'email' in data and data['email']:
            # 驗證郵箱格式
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, data['email']):
                return jsonify({
                    'success': False,
                    'message': '電子郵件格式不正確'
                }), 400
            
            # 檢查郵箱是否已被使用（只有在郵箱實際改變時檢查）
            original_email = original_user_data[4]
            if data['email'] != original_email:
                try:
                    existing_email = db_manager.execute_query(
                        "SELECT userID, username FROM users WHERE email = %s AND userID != %s", 
                        (data['email'], userID)
                    )
                    
                    if existing_email and len(existing_email) > 0:
                        duplicate_user = existing_email[0]
                        return jsonify({
                            'success': False,
                            'message': f'電子郵件已被使用'
                        }), 400
                        
                except Exception as e:
                    print(f"❌ 檢查郵箱時出錯: {str(e)}")
                    return jsonify({
                        'success': False,
                        'message': '檢查郵箱時發生錯誤'
                    }), 500
        
        # 添加更新時間和條件
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        update_values.append(userID)
        
        print('最終 update_fields:', update_fields)
        print('最終 update_values:', update_values)
        
        # 執行更新
        query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE userID = %s
        """
        
        result = db_manager.execute_query(query, update_values)
        
        # 🎯 根據 execute_query 的實際行為調整
        # 如果 result 是受影響的行數（1=成功，0=失敗）
        if result == 1:  # 或者根據你的 execute_query 實際返回值調整
            # 重新查詢更新後的用戶數據（包含 webhook）
            updated_user = db_manager.execute_query(
                "SELECT ID, userID, username, nickname, email, role_level, status, last_login, created_at, updated_at, webhook FROM users WHERE userID = %s", 
                (userID,)
            )
            
            if updated_user:
                user_data = updated_user[0]
                return jsonify({
                    'success': True,
                    'message': '用戶信息更新成功',
                    'data': {
                        'user': {
                            'ID': user_data[0],
                            'userID': user_data[1],
                            'username': user_data[2],
                            'nickname': user_data[3],
                            'email': user_data[4],
                            'role_level': user_data[5],
                            'status': user_data[6],
                            'last_login': user_data[7].isoformat() if user_data[7] else None,
                            'created_at': user_data[8].isoformat() if user_data[8] else None,
                            'updated_at': user_data[9].isoformat() if user_data[9] else None,
                            'webhook': user_data[10]  # 新增 webhook 字段
                        }
                    }
                }), 200
            else:
                return jsonify({
                    'success': True,
                    'message': '用戶信息更新成功',
                    'data': {
                        'user': {
                            'ID': original_user_data[0],
                            'userID': original_user_data[1],
                            'username': data.get('username', original_username),
                            'nickname': data.get('nickname', original_user_data[3]),
                            'email': data.get('email', original_user_data[4]),
                            'role_level': data.get('role_level', original_user_data[5]),
                            'status': data.get('status', original_user_data[6]),
                            'last_login': original_user_data[7].isoformat() if original_user_data[7] else None,
                            'created_at': original_user_data[8].isoformat() if original_user_data[8] else None,
                            'updated_at': '剛剛更新',
                            'webhook': data.get('webhook', original_webhook)  # 新增 webhook 字段
                        }
                    }
                }), 200
        else:
            return jsonify({
                'success': False,
                'message': '用戶信息更新失敗'
            }), 500

    except Exception as e:
        import traceback
        print(f"💥 [ERROR] updateUser exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'伺服器錯誤: {str(e)}'
        }), 500   
