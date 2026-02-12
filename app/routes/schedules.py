from flask import Blueprint, json, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date, timedelta

import psycopg
from app.database import PostgresDBManager
from config import Config

schedules_bp = Blueprint('schedules', __name__, url_prefix='/api/schedules')

# 獲取排班列表
@schedules_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_schedule_data():
    db_manager = PostgresDBManager.get_instance()
    try:
        current_user = get_jwt_identity()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        nickname = request.args.get('nickname')  # 新增：nickname 參數

        # 如果沒有提供日期，默認為當前月份
        if not start_date or not end_date:
            today = datetime.now()
            first_day = today.replace(day=1)
            if today.month == 12:
                last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            
            start_date = first_day.strftime('%Y-%m-%d')
            end_date = last_day.strftime('%Y-%m-%d')

        # 構建基礎查詢
        query = """
        SELECT
            s.id,
            s.schedule_date,
            s.user_id,
            s.shift_name,
            -- 優先使用 shift_types.description
            COALESCE(st.description, s.shift_description) as shift_description,
            s.user_name_snapshot,
            s.week_number,
            s.year,
            s.created_by,
            s.created_at,
            s.updated_at,
            s.remark,
            u.userID,
            u.username,
            u.nickname,
            u.email,
            u.phone,
            u.department_id,
            u.role_level
            FROM schedules s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN shift_types st ON s.shift_name = st.shift_name AND st.is_active = TRUE
            WHERE s.schedule_date BETWEEN %s AND %s
        """
        
        params = [start_date, end_date]
        
        # 如果有 nickname 參數，添加篩選條件
        if nickname:
            query += " AND u.nickname ILIKE %s"
            params.append(f'%{nickname}%')
        
        # 添加排序
        query += " ORDER BY u.nickname, s.schedule_date"
        
        result = db_manager.execute_query(query, params)
        
        schedules = []
        # print(f"查詢結果數量: {len(result)}")
        # print(f"查詢result: {result}")
        # print(f"查詢參數: {result[5]}")
        for row in result:
            schedule = {
                'id': row[0],
                'schedule_date': row[1].isoformat() if row[1] else None,
                'user_id': row[2],
                'shift_name': row[3],
                'shift_description': row[4],
                'user_name_snapshot': row[5],
                'week_number': row[6],
                'year': row[7],
                'created_by': row[8],
                'created_at': row[9].isoformat() if row[9] else None,
                'updated_at': row[10].isoformat() if row[10] else None,
                'remark': row[11] ,
                'userID': row[12],
                'username': row[13],
                'nickname': row[14],
                'email': row[15],
                'phone': row[16],
                'department_id': row[17],
                'role_level': row[18]
            }
            schedules.append(schedule)
            
        return jsonify({
            'success': True,
            'data': schedules,
            'count': len(schedules),
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            },
            'search_nickname': nickname  # 返回搜索的 nickname
        })
        
    except Exception as e:
        print(f"獲取排班數據錯誤: {str(e)}")  # 調試用
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 創建排班
@schedules_bp.route('/', methods=['POST'])
@jwt_required()
def create_schedule():
    db_manager = PostgresDBManager.get_instance()
    try:
        current_identity = get_jwt_identity()
        # 從 JWT identity 中提取暱稱 (nickname)
        current_user = "unknown"  # 默認值
        
        if isinstance(current_identity, dict):
            # 如果 identity 是字典，提取 nickname
            current_user = current_identity.get('nickname', 'unknown')
        elif isinstance(current_identity, str):
            # 如果 identity 是字符串，嘗試解析 JSON
            try:
                identity_data = json.loads(current_identity)
                current_user = identity_data.get('nickname', 'unknown')
            except json.JSONDecodeError:
                # 如果不是 JSON 字符串，直接使用
                current_user = current_identity
            except Exception as e:
                print(f"解析 JWT identity 錯誤: {e}")
                current_user = "unknown"
        else:
            current_user = str(current_identity)
        
        data = request.get_json()

        # print(f"收到的數據: {data}")  # 調試用
        # print(f"當前用戶暱稱: {current_user}")  # 調試用
        # print(f"暱稱長度: {len(current_user) if current_user else 0}")  # 調試用

        # 驗證必要字段 - 改為 userID
        required_fields = ['userID', 'schedule_date', 'shift_name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'缺少必要欄位: {field}'
                }), 400

        userID = data['userID']  # 改為 userID
        schedule_date = data['schedule_date']
        shift_name = data['shift_name']
        shift_description = data.get('shift_description')

        # 檢查字段長度
        if shift_name and len(shift_name) > 50:
            return jsonify({
                'success': False,
                'error': f'班別名稱過長 (最多50字符，當前{len(shift_name)}字符): {shift_name}'
            }), 400

        # 處理 created_by 長度限制 - 使用暱稱
        if current_user and len(current_user) > 50:
            created_by = current_user[:50]
            print(f"用戶暱稱被截斷: {current_user} -> {created_by}")
        else:
            created_by = current_user

        # 檢查用戶是否存在 - 改為使用 userID 查詢
        user_check_query = "SELECT id, userID, username, nickname FROM users WHERE userID = %s AND status > 1"
        user_result = db_manager.execute_query(user_check_query, (userID,))
        
        if not user_result:
            return jsonify({
                'success': False,
                'error': f'用戶不存在或狀態異常 (userID: {userID})'
            }), 400

        # 獲取用戶的 id 和暱稱
        user_id = user_result[0][0]  # 獲取 users 表的 id
        user_nickname = user_result[0][3]
        
        # 處理 user_name_snapshot 長度限制 (VARCHAR(100))
        if user_nickname and len(user_nickname) > 100:
            user_name_snapshot = user_nickname[:100]
            print(f"用戶暱稱快照被截斷: {user_nickname} -> {user_name_snapshot}")
        else:
            user_name_snapshot = user_nickname

        # 檢查班別是否存在
        shift_check_query = "SELECT id, shift_name, description FROM shift_types WHERE shift_name = %s AND is_active = TRUE"
        shift_result = db_manager.execute_query(shift_check_query, (shift_name,))
        
        if not shift_result:
            return jsonify({
                'success': False,
                'error': f'無效的班別名稱: {shift_name}'
            }), 400

        # 如果沒有提供班別描述，使用默認描述
        if not shift_description:
            shift_description = shift_result[0][1]

        # 檢查是否已存在排班 - 使用 user_id (users 表的 id)
        existing_check_query = """
            SELECT id FROM schedules 
            WHERE user_id = %s AND schedule_date = %s
        """
        existing_result = db_manager.execute_query(existing_check_query, (user_id, schedule_date))
        # print('existing_result:', existing_result)
        
        # 檢查鎖定 - 如果已鎖定會拋出異常
        check_lock(data['schedule_date'])
        
        if existing_result:
            return jsonify({
                'success': False,
                'error': '該用戶在此日期已有排班'
            }), 400

        # 計算週數和年份
        schedule_date_obj = datetime.strptime(schedule_date, '%Y-%m-%d').date()
        week_number = schedule_date_obj.isocalendar()[1]
        year = schedule_date_obj.year
        
        # print(f"準備插入的數據:")
        # print(f"  user_id: {user_id} (來自 users 表的 id)")
        # print(f"  userID: {userID} (輸入的 userID)")
        # print(f"  schedule_date: {schedule_date}")
        # print(f"  shift_name: '{shift_name}' (長度: {len(shift_name)})")
        # print(f"  shift_description: '{shift_description}' (長度: {len(shift_description) if shift_description else 0})")
        # print(f"  user_name_snapshot: '{user_name_snapshot}' (長度: {len(user_name_snapshot) if user_name_snapshot else 0})")
        # print(f"  created_by: '{created_by}' (長度: {len(created_by) if created_by else 0})")
        # print(f"  week_number: {week_number}")
        # print(f"  year: {year}")

        # 插入排班記錄 - 使用 user_id (users 表的 id)
        insert_query = """
            INSERT INTO schedules (
                user_id, schedule_date, shift_name, shift_description,
                user_name_snapshot, week_number, year, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        insert_params = (
            user_id, schedule_date, shift_name, shift_description,
            user_name_snapshot, week_number, year, created_by
        )

        result = db_manager.execute_query(insert_query, insert_params)
        print(f"插入結果: {result}")  # 調試用
        
        if not result:
            return jsonify({
                'success': False,
                'error': '創建排班失敗，未返回 ID'
            }), 500
        
        if result == 0:
            return jsonify({
                'success': False,
                'msg': '用戶不存在或已被刪除',
                'error': 'User not found'
            }), 404

        return jsonify({
            'success': True,
            'message': '排班創建成功',
            'data': ''
        }), 201

    except Exception as e:
        # print(f"創建排班詳細錯誤: {str(e)}")  # 調試用
        # import traceback
        # print(f"錯誤堆棧: {traceback.format_exc()}")  # 調試用
        return jsonify({
            'success': False,
            'error': f'{str(e)}'
        }), 500
 
def check_lock(schedule_date):
    db_manager = PostgresDBManager.get_instance()
    check_islock = """SELECT * FROM get_schedule_lock_status(%s,%s,%s,%s,%s); """
    # print('Config.SCHEDULE_WEEKS_AHEAD:',Config.SCHEDULE_WEEKS_AHEAD  )
    try:
        islock_result = db_manager.execute_query(
            check_islock, 
            (   schedule_date, 
                date.today(),
                Config.SCHEDULE_DAYS_BEFORE_LOCK,  # 使用配置的提前天數
                Config.SCHEDULE_LOCK_TIME,         # 使用配置的鎖定時間
                Config.SCHEDULE_WEEKS_AHEAD        # 使用配置的提前周數 
             )
        )
        
        if not islock_result:
            raise Exception("無法獲取鎖定狀態")
        
        result = islock_result[0]
        locked = result[5]
        
        if locked:
            # 拋出自定義異常
            raise ValueError(f"排班已鎖定: {schedule_date}")
        
        return False  # 未鎖定
        
    except Exception as e:
        print(f"鎖定檢查錯誤: {str(e)}")
        raise  # 重新拋出異常

# 更新排班接口
@schedules_bp.route('/<int:schedule_id>', methods=['PUT'])
@jwt_required()
def update_schedule(schedule_id):
    db_manager = PostgresDBManager.get_instance()
    data = request.get_json()
    
    try:
        # 驗證必要字段
        required_fields = ['shift_name', 'schedule_date']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'缺少必要欄位: {field}'
                }), 400
        
        # 檢查鎖定 - 如果已鎖定會拋出異常
        check_lock(data['schedule_date'])
        
        # 如果通過了鎖定檢查，繼續執行更新
        update_query = """
            UPDATE schedules 
            SET shift_name = %s
            WHERE id = %s
            RETURNING id
        """
        
        result = db_manager.execute_query(
            update_query, 
            (data['shift_name'], schedule_id)
        )
        
        if result and result != 0:  
            return jsonify({
                'success': True,
                'message': '排班更新成功',
                'data': ''
            })
        else:
            return jsonify({
                'success': False,
                'message': '排班更新失敗',
                'data': ''
            })
            
    except ValueError as e:  # 捕獲鎖定異常
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
        
    except psycopg.Error as e:
        return jsonify({
            'success': False,
            'error': f'數據庫錯誤: {str(e)}'
        }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# @schedules_bp.route('/self', methods=['GET'])
# @jwt_required()
# def get_one_schedule_data():
#     db_manager = PostgresDBManager.get_instance()
#     try:
#         current_user_str = get_jwt_identity()
        
#         print(f"current_user 類型: {type(current_user_str)}")
#         print(f"current_user 原始內容: {current_user_str}")
        
#         # 解析 JSON 字符串為字典
#         current_user = json.loads(current_user_str)
        
#         # 現在可以安全地訪問字典
#         username = current_user.get('nickname')
#         print(f'username: {username}')
        
#         start_date = request.args.get('start_date')
#         end_date = request.args.get('end_date')

#         query = """
#             SELECT * FROM schedules s
#             LEFT JOIN users u ON s.user_id = u.id
#             WHERE user_name_snapshot = %s
#             AND schedule_date BETWEEN %s AND %s
#         """
        
#         params = (username, start_date, end_date)
#         result = db_manager.execute_query(query, params)
#         print(result)
        
#         # schedules = []
#         # for row in result:
#         #     schedule = {
#         #         'id': row[0],
#         #         'schedule_date': row[1].isoformat() if row[1] else None,
#         #         'user_id': row[2],
#         #         'shift_name': row[3],
#         #         'shift_description': row[4],
#         #         'user_name_snapshot': row[5],
#         #         'week_number': row[6],
#         #         'year': row[7],
#         #         'created_by': row[8],
#         #         'created_at': row[9].isoformat() if row[9] else None,
#         #         'updated_at': row[10].isoformat() if row[10] else None,
#         #         'userID': row[11],
#         #         'username': row[12],
#         #         'nickname': row[13],
#         #         'email': row[14],
#         #         'phone': row[15],
#         #         'department_id': row[16],
#         #         'role_level': row[17]
#         #     }
#         #     schedules.append(schedule)
            
#         return jsonify({
#             'success': True,
#             # 'data': schedules,
#             # 'count': len(schedules),
#             'date_range': {
#                 'start_date': start_date,
#                 'end_date': end_date
#             }
#         })
        
#     except Exception as e:
#         print(f"獲取排班數據錯誤: {str(e)}")  # 調試用
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# 刪除排班
# @schedules_bp.route('/<int:schedule_id>', methods=['DELETE'])
# @jwt_required()
# def delete_schedule(schedule_id):
#     try:
#         current_user = get_jwt_identity()
        
#         with PostgresDBManager() as db:
#             # 檢查排班是否存在和鎖定狀態
#             db.execute("""
#                 SELECT schedule_date, is_schedule_locked(schedule_date) as is_locked
#                 FROM schedules WHERE id = %s
#             """, (schedule_id,))
            
#             result = db.fetchone()
#             if not result:
#                 return jsonify({
#                     'success': False,
#                     'error': '排班不存在'
#                 }), 404
            
#             schedule_date, is_locked = result
#             if is_locked:
#                 return jsonify({
#                     'success': False,
#                     'error': '該排班已鎖定，無法刪除'
#                 }), 400
            
#             # 刪除排班
#             db.execute("DELETE FROM schedules WHERE id = %s", (schedule_id,))
            
#             return jsonify({
#                 'success': True,
#                 'message': '排班刪除成功'
#             })
            
#     except psycopg2.Error as e:
#         return jsonify({
#             'success': False,
#             'error': f'數據庫錯誤: {str(e)}'
#         }), 500
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# 批量創建排班
# @schedules_bp.route('/batch', methods=['POST'])
# @jwt_required()
# def batch_create_schedules():
#     try:
#         data = request.get_json()
#         current_user = get_jwt_identity()
        
#         schedules = data.get('schedules', [])
#         if not schedules:
#             return jsonify({
#                 'success': False,
#                 'error': '沒有提供排班數據'
#             }), 400
        
#         results = {
#             'success': [],
#             'failed': []
#         }
        
#         with PostgresDBManager() as db:
#             for schedule_data in schedules:
#                 try:
#                     required_fields = ['user_id', 'schedule_date', 'shift_name']
#                     for field in required_fields:
#                         if field not in schedule_data:
#                             results['failed'].append({
#                                 'data': schedule_data,
#                                 'error': f'缺少必要欄位: {field}'
#                             })
#                             continue
                    
#                     # 檢查是否已存在
#                     db.execute(
#                         "SELECT id FROM schedules WHERE user_id = %s AND schedule_date = %s",
#                         (schedule_data['user_id'], schedule_data['schedule_date'])
#                     )
#                     if db.fetchone():
#                         results['failed'].append({
#                             'data': schedule_data,
#                             'error': '該用戶在此日期已有排班'
#                         })
#                         continue
                    
#                     # 檢查班別
#                     db.execute(
#                         "SELECT shift_name FROM shift_types WHERE shift_name = %s AND is_active = TRUE",
#                         (schedule_data['shift_name'],)
#                     )
#                     if not db.fetchone():
#                         results['failed'].append({
#                             'data': schedule_data,
#                             'error': '無效的班別名稱'
#                         })
#                         continue
                    
#                     # 插入排班
#                     schedule_date = datetime.strptime(schedule_data['schedule_date'], '%Y-%m-%d').date()
#                     week_number = schedule_date.isocalendar()[1]
#                     year = schedule_date.year
                    
#                     query = """
#                     INSERT INTO schedules (
#                         user_id, schedule_date, shift_name, shift_description,
#                         week_number, year, created_by
#                     ) VALUES (%s, %s, %s, %s, %s, %s, %s)
#                     RETURNING id
#                     """
                    
#                     params = (
#                         schedule_data['user_id'],
#                         schedule_data['schedule_date'],
#                         schedule_data['shift_name'],
#                         schedule_data.get('shift_description'),
#                         week_number,
#                         year,
#                         current_user
#                     )
                    
#                     db.execute(query, params)
#                     schedule_id = db.fetchone()[0]
                    
#                     results['success'].append({
#                         'id': schedule_id,
#                         'user_id': schedule_data['user_id'],
#                         'schedule_date': schedule_data['schedule_date']
#                     })
                    
#                 except Exception as e:
#                     results['failed'].append({
#                         'data': schedule_data,
#                         'error': str(e)
#                     })
            
#             return jsonify({
#                 'success': True,
#                 'message': '批量創建完成',
#                 'data': results
#             })
            
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# 檢查排班鎖定狀態
# @schedules_bp.route('/lock-status/<date>', methods=['GET'])
# @jwt_required()
# def get_lock_status(date):
#     try:
#         check_date = datetime.strptime(date, '%Y-%m-%d').date()
        
#         with PostgresDBManager() as db:
#             db.execute("SELECT * FROM get_schedule_lock_status(%s)", (check_date,))
#             result = db.fetchone()
            
#             if not result:
#                 return jsonify({
#                     'success': False,
#                     'error': '無法獲取鎖定狀態'
#                 }), 400
            
#             columns = [desc[0] for desc in db.description]
#             lock_status = dict(zip(columns, result))
            
#             # 轉換日期時間格式
#             for key, value in lock_status.items():
#                 if isinstance(value, (datetime, date)):
#                     lock_status[key] = value.isoformat()
            
#             return jsonify({
#                 'success': True,
#                 'data': lock_status
#             })
            
#     except ValueError:
#         return jsonify({
#             'success': False,
#             'error': '無效的日期格式，請使用 YYYY-MM-DD'
#         }), 400
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# 獲取有效班別列表
@schedules_bp.route('/shift-types', methods=['GET'])
@jwt_required()
def get_shift_types():
    db_manager = PostgresDBManager.get_instance()
    try:
        query = """
            SELECT * FROM get_valid_shift_names()
        """
        
        result = db_manager.execute_query(query)
        
        # 將數組轉換為結構化對象
        shift_types = []
        for row in result:
            shift_types.append({
                'shift_name': row[0],
                'description': row[1],
                'sort_order': row[2]
            })
            
        return jsonify({
            'success': True,
            'data': shift_types
        })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
@schedules_bp.route('/users', methods=['GET'])
@jwt_required()
def get_all_users():
    db_manager = PostgresDBManager.get_instance()
    try:
        query = """
            SELECT * FROM get_active_users()
        """
        
        result = db_manager.execute_query(query)
        
        # 將數組轉換為結構化對象
        shift_types = []
        for row in result:
            shift_types.append({
                'id': row[0],
                'userID': row[1],
                'nickname': row[2]
            })
            
        return jsonify({
            'success': True,
            'data': shift_types
        })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500