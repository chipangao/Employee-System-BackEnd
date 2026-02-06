from datetime import datetime
import uuid
from zoneinfo import ZoneInfo
import requests
from flask import Blueprint, jsonify, request, make_response
from flask_jwt_extended import get_jwt_identity, jwt_required
import json

from app.database import PostgresDBManager
from config import Config


leave_bp = Blueprint('leave', __name__, url_prefix='/api/leave')

# 格式化日期函数
def format_date(dates_param):
    """
    通用函数，处理所有格式的请假日期
    """

    print('dates_param:', dates_param)

    if not dates_param:
        return ""
    
    def format_dt(dt_str):
        if not dt_str:
            return ""
        try:
            if dt_str.endswith('Z'):
                dt_str = dt_str[:-1]
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime('%Y-%m-%d')
        except:
            return dt_str
    
    if isinstance(dates_param, str):
        return format_dt(dates_param)
    
    elif isinstance(dates_param, dict):
        start = format_dt(dates_param.get('start'))
        end = format_dt(dates_param.get('end'))
        
        if start and end and start != end:
            return f"{start} 至 {end}"
        elif start:
            return start
        elif end:
            return end
    
    return str(dates_param)

def format_submit_time(submit_time):
    """格式化提交時間為易讀格式"""
    # 例如將 "2026-02-05T07:43:52.469Z" 轉為 "2026-02-05 15:43"
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(submit_time.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return submit_time
    
def save_leave_token(leave_data):
    """保存請假申請，返回資料庫生成的 token"""
    db_manager = PostgresDBManager.get_instance()
    
    # 讓資料庫生成 token (UUID)
    query = """
        INSERT INTO leave_tokens (leave_data)
        VALUES (%s)
        RETURNING token
    """
    
    try:
        # 使用新的參數 return_inserted_id=True
        result = db_manager.execute_returning(
            query, 
            (json.dumps(leave_data),), 
        )
        
        if result:
            print(f"✅ 保存成功, token: {result[0]}")
            return result[0]
        else:
            print("❌ 保存失敗，未返回 token")
            return None
            
    except Exception as e:
        print(f"❌ 保存 token 時出錯: {e}")
        return None
   
def send_to_synology_chat(data):
    """發送數據到 Synology Chat"""
    current_user = get_jwt_identity()
    user_data = json.loads(current_user)
    nickname = user_data.get("nickname")
    
    # 保存到資料庫，獲取 token
    token = save_leave_token({
        'nickname': nickname,
        'leaveType': data['leaveType'],
        'dates': data['dates'],
        'time': data['time'],
        'reason': data['reason'],
        'submitTime': data['submitTime'],
        'customTime': data['customTime']
    })
    
    if not token:
        print("❌ 無法生成 token，跳過發送")
        return False
    
    # 構建 URL
    base_url = "http://localhost:5173"
    approve_url = f"{base_url}/leave/approve/{token}"
    reject_url = f"{base_url}/leave/reject/{token}"
    
    try:
        url = Config.Synology_Chat_URL
        params = Config.Synology_Chat_PARAMS
        
        response_text = f"""
📋 **請假申請 - 待審批**

申請人 : {nickname}
請假類型 : {data['leaveType']}
請假日期 : {format_date(data['dates'])}
請假時段 : {f"{data['customTime']['start']} - {data['customTime']['end']}" if data['time'] == 'custom' else '上午' if data['time'] == 'am' else'下午' if data['time'] == 'pm' else '全天'}
請假原因 : {data['reason']}
申請時間 : {format_submit_time(data['submitTime'])}

---
審批操作 (請點擊下方按鈕):
<{approve_url}|✅ 批准申請>    <{reject_url}|❌ 拒絕申請>

⚠️ 注意事項:
• 連結將在首次審批 30 分鐘後失效
• 請及時處理，逾期需重新申請
• 請勿將連結分享給他人
        """

        payload = {
            "text": response_text,
        }

        webhook_data = {
            "payload": json.dumps(payload),
        }

        response = requests.post(
            url=url,
            params=params,
            data=webhook_data,
            headers={'Content-Type': 'application/json'},
            verify=False  
        )
        
        if response.status_code == 200:
            print(f"✅ 成功發送到 Synology Chat")
            return True
        else:
            print(f"❌ Webhook 發送失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 發送 Synology Chat 時出錯: {e}")
        return False
 
def send_to_synology_chat_approve(data):
    """發送批准通知到 Synology Chat"""
    
    try:
        url = Config.Synology_Chat_URL
        params = Config.Synology_Chat_PARAMS
        
        response_text = f"""
✅ 請假申請 - 已批准

申請人: {data['nickname']}於{data['dates']}的{data['leaveType']}申請已被批准。
 
        """

        payload = {
            "text": response_text,
        }

        webhook_data = {
            "payload": json.dumps(payload),
        }

        response = requests.post(
            url=url,
            params=params,
            data=webhook_data,
            headers={'Content-Type': 'application/json'},
            verify=False  
        )
        
        if response.status_code == 200:
            print(f"✅ 成功發送到 Synology Chat")
            return True
        else:
            print(f"❌ Webhook 發送失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 發送 Synology Chat 時出錯: {e}")
        return False

def send_to_synology_chat_reject(data,reason):
    """發送拒絕通知到 Synology Chat"""
    
    try:
        url = Config.Synology_Chat_URL
        params = Config.Synology_Chat_PARAMS
        
        response_text = f"""
❌ 請假申請 - 已拒絕

申請人: {data['nickname']}於{data['dates']}的{data['leaveType']}申請已被拒絕。
拒絕原因: {reason}

        """
        
        payload = {
            "text": response_text,
        }   
        
        webhook_data = {
            "payload": json.dumps(payload),
        }
        response = requests.post(
            url=url,
            params=params,
            data=webhook_data,
            headers={'Content-Type': 'application/json'},
            verify=False
        )
        if response.status_code == 200:
            print(f"✅ 成功發送到 Synology Chat")
            return True
        else:
            print(f"❌ Webhook 發送失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 發送 Synology Chat 時出錯: {e}")
        return False
        
@leave_bp.route('/', methods=['POST','GET'])
@jwt_required()
def ask_for_leave():
    print("=" * 50)
    print("📨 收到請假申請請求")
    
    try:
        # GET 請求處理
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'status': 'online',
                'message': '請假申請 API 服務運行中',
                'timestamp': datetime.now().isoformat()
            })
        
        # POST 請求處理
        data = request.get_json(silent=True)
        
        if not data:
            data = request.form.to_dict()
        
        if not data:
            print("❌ 無法解析請求數據")
            return jsonify({
                'success': False,
                'error': '未收到有效數據'
            }), 400
        
        print(f"📊 接收到的請假申請數據: {data}")
        
        # 驗證必要字段
        required_fields = ['leaveType', 'reason', 'dates', 'time', 'submitTime']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            error_msg = f"缺少必要字段: {', '.join(missing_fields)}"
            print(f"❌ {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # 發送到 Synology Chat
        chat_sent = send_to_synology_chat(data)
        
        # 構建返回給前端的響應
        response_data = {
            'success': True,
            'message': '請假申請提交成功',
            'data': {
                'synologyChatSent': chat_sent,
                'message': '申請已成功提交' + ('並發送通知' if chat_sent else '但通知發送失敗')
            }
        }
        
        print(f"✅ 請假申請處理完成")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"❌ 處理錯誤: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'伺服器錯誤: {str(e)}'
        }), 500

@leave_bp.route('/validate-token/<token>', methods=['GET'])
def is_valid_token(token):
    """檢查請假 token 是否有效（免登錄）"""
    try:
        db_manager = PostgresDBManager.get_instance()
        
        query = """
                SELECT 
                    token,
                    leave_data,
                    action,
                    review_reason,
                    processed_at,
                    created_at
                FROM leave_tokens
                WHERE token = %s
                AND created_at >= now() - interval '%s minutes'
            """

        # 使用 execute_query
        result = db_manager.execute_query(query, (token, 30), fetch=True)
        
        # 檢查結果
        if not result or len(result) == 0:
            return jsonify({
                'success': True,
                'valid': False,
                'message': '連結無效或已過期',
            })
        
        # 處理數據
        row = result[0]
        
        # 處理 leave_data：檢查是否是字符串
        leave_data_raw = row[1]
        leave_data_dict = {}
        
        if leave_data_raw is not None:
            if isinstance(leave_data_raw, str):
                try:
                    leave_data_dict = json.loads(leave_data_raw)
                except json.JSONDecodeError:
                    leave_data_dict = {}
            elif isinstance(leave_data_raw, dict):
                # 如果已經是字典，直接使用
                leave_data_dict = leave_data_raw
            else:
                # 其他類型，嘗試轉換
                try:
                    leave_data_dict = dict(leave_data_raw)
                except:
                    leave_data_dict = {}
        
        app_data = {
            'token': row[0],
            'leave_data': leave_data_dict,
            'action': row[2],
            'review_reason': row[3],
            'processed_at': row[4].isoformat() if row[4] else None,
            'created_at': row[5].isoformat() if row[5] else None,
        }
        
        # 檢查有效性
        if app_data['action'] and app_data['action'] not in [None, '', 'pending']:
            return jsonify({
                'success': True,
                'valid': False,
                'message': f'申請已{app_data["action"]}',
                'data': app_data
            })
        
        return jsonify({
            'success': True,
            'valid': True,
            'message': 'Token 有效',
            'data': app_data
        })
        
    except Exception as e:
        print(f"❌ 驗證 token 失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'valid': False
        }), 500

@leave_bp.route('/approve/<token>', methods=['POST'])
def approve_leave(token):
    """批准請假申請（免登錄）"""
    try:
        db_manager = PostgresDBManager.get_instance()
        
        # 1. 更新 leave_tokens 表
        query = """ 
        UPDATE leave_tokens
        SET action = 'approved',
            processed_at = COALESCE(processed_at, now())
        WHERE token = %s
        AND (processed_at IS NULL OR processed_at >= now() - interval '%s minutes')
        RETURNING *
        """
        
        result = db_manager.execute_returning(query, (token, 30))
        
        if not result:
            return jsonify({
                'success': False,
                'error': '批准失敗，可能申請不存在或已處理'
            }), 400
        
        # 2. 提取數據（假設 result 是元組或列表）
        # 注意：需要根據實際數據結構調整索引
        token_row = result[0] if isinstance(result, list) else result
        leave_data = token_row[1]  # 假設第二個欄位是 leave_data
        processed_at = token_row[4]  # 假設第五個欄位是 processed_at
        
        nickname = leave_data.get('nickname')
        leave_type = leave_data.get('leaveType')
        time_period = leave_data.get('time')
        dates_data = leave_data.get('dates')  # 這可能是單個日期或多個日期
        
        print(f'✅ 批准請假申請成功 - 用戶: {nickname}, 類型: {leave_type}')
        
        # 3. 更新 schedules 表
        try:
            import json
            
            # 創建 JSON remark
            remark_json = {
                'leave_type': leave_type,
                'time_period': time_period
            }
            
            # 使用您的 get_leave_dates 函數
            update_query = """
            UPDATE schedules s
            SET remark = %s,
                updated_at = now()
            WHERE EXISTS (
                SELECT 1 
                FROM get_leave_dates(%s::jsonb, %s, %s, %s) fld
                WHERE s.schedule_date = fld.leave_date
                AND s.user_name_snapshot = fld.nickname
            )
            """
            
            rows_updated = db_manager.execute_query(
                update_query,
                (
                    json.dumps(remark_json, ensure_ascii=False),
                    json.dumps(dates_data),
                    nickname,
                    leave_type,
                    time_period
                ),
                fetch=False
            )
            
            if rows_updated == 0 or rows_updated is None:
                print(f"⚠️  沒有找到匹配的記錄，嘗試插入新記錄...")
                
                # 確保觸發器已停用
                disable_trigger_query = """
                ALTER TABLE schedules DISABLE TRIGGER trg_validate_shift_name_and_user
                """
                db_manager.execute_query(disable_trigger_query, fetch=False)
                
                try:
                    # 插入查詢
                    insert_query = """
                    INSERT INTO schedules (
                        user_id,
                        schedule_date,
                        week_number,
                        year,
                        remark
                    ) VALUES (
                        (SELECT id FROM users WHERE nickname = %s LIMIT 1),
                        %s::date,
                        EXTRACT(WEEK FROM %s::date)::integer,
                        EXTRACT(YEAR FROM %s::date)::integer,
                        %s::jsonb
                    )
                    """
                    
                    # 處理多個日期
                    if isinstance(dates_data, list):
                        inserted_count = 0
                        for date_str in dates_data:
                            try:
                                insert_result = db_manager.execute_query(
                                    insert_query,
                                    (
                                        nickname,
                                        date_str,
                                        date_str,
                                        date_str,
                                        json.dumps(remark_json, ensure_ascii=False)
                                    ),
                                    fetch=False
                                )
                                if insert_result:
                                    inserted_count += 1
                                    print(f"✅ 插入日期 {date_str} 成功")
                            except Exception as date_error:
                                print(f"❌ 插入日期 {date_str} 失敗: {date_error}")
                        
                        print(f"✅ 總共插入了 {inserted_count} 筆記錄")
                    else:
                        # 單個日期
                        insert_data = db_manager.execute_query(
                            insert_query,
                            (
                                nickname,
                                dates_data,  # 單個日期字串
                                dates_data,
                                dates_data,
                                json.dumps(remark_json, ensure_ascii=False)
                            ),
                            fetch=False
                        )
                        print(f"✅ 插入成功: {insert_data}")
                        
                finally:
                    # 重新啟用觸發器
                    enable_trigger_query = """
                    ALTER TABLE schedules ENABLE TRIGGER trg_validate_shift_name_and_user
                    """
                    db_manager.execute_query(enable_trigger_query, fetch=False)
                    
            else:
                print(f"✅ 成功更新了 {rows_updated} 筆排班記錄")
                
        except Exception as update_error:
            print(f"⚠️  更新日程表時發生錯誤: {update_error}")
            # 不影響主要流程
        
        # 4. 發送通知
        send_to_synology_chat_approve(leave_data)
        
        return jsonify({
            'success': True,
            'message': '請假申請已批准'
        })
        
    except Exception as e:
        print(f"❌ 批准失敗: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        
@leave_bp.route('/reject/<token>', methods=['POST'])
def reject_leave(token):
    """拒絕請假申請（免登錄）"""
    try:
        data = request.get_json()
        reason = data.get('reason', '')
        
        db_manager = PostgresDBManager.get_instance()
        
        query = """ 
            UPDATE leave_tokens
            SET action = 'rejected',
            review_reason = %s,
                processed_at = COALESCE(processed_at, now())  -- 為空時用 now()，否則保持原值
            WHERE token = %s
            AND (processed_at IS NULL OR processed_at >= now() - interval '%s minutes')
            RETURNING *
        """
        
        result = db_manager.execute_returning(query, (reason, token, 30))
        
        if result:
            send_to_synology_chat_reject(result[1],reason)
            return jsonify({
                'success': True,
                'message': '請假申請已拒絕'
            })
        else:
            return jsonify({
                'success': False,
                'error': '拒絕失敗，可能申請不存在或已處理'
            }), 400
        
    except Exception as e:
        print(f"❌ 拒絕失敗: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500