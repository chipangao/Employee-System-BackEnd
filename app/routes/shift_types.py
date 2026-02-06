from datetime import time
from math import ceil
from flask import Blueprint, json, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.database import PostgresDBManager
from app.errors import abort_msg
from app.utils.auth_utils import authenticate_and_login_user, reset_user_password, validate_password_strength

shift_types_bp = Blueprint('shift_types', __name__, url_prefix='/api/shift_types')

@shift_types_bp.route("/", methods=["GET"])
@jwt_required()
def get_shift_types():
    """
    獲取班別列表（支持搜尋和篩選）
    """
    db_manager = PostgresDBManager.get_instance()
    
    try:
        # 獲取查詢參數
        search = request.args.get('search', '').strip()
        is_active = request.args.get('is_active', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # 構建基礎查詢
        base_query = """
        SELECT 
            id,
            shift_name,
            description,
            is_active,
            sort_order,
            created_by,
            created_at
        FROM shift_types 
        WHERE 1=1
        """
        
        count_query = "SELECT COUNT(*) FROM shift_types WHERE 1=1"
        
        # 構建查詢條件和參數
        conditions = []
        params = []
        
        # 搜尋條件
        if search:
            conditions.append("""
                (shift_name ILIKE %s OR description ILIKE %s)
            """)
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        # 狀態篩選
        if is_active and is_active.lower() in ['true', 'false']:
            is_active_bool = is_active.lower() == 'true'
            conditions.append("is_active = %s")
            params.append(is_active_bool)
        
        # 組合查詢條件
        if conditions:
            where_clause = " AND " + " AND ".join(conditions)
            base_query += where_clause
            count_query += where_clause
        
        # 添加排序
        base_query += " ORDER BY sort_order ASC, created_at DESC"
        
        # 分頁處理
        offset = (page - 1) * per_page
        base_query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        # 執行查詢
        result = db_manager.execute_query(base_query, tuple(params))
        
        # 獲取總數
        total_result = db_manager.execute_query(count_query, tuple(params[:-2]) if params else ())
        total_count = total_result[0][0] if total_result else 0
        total_pages = ceil(total_count / per_page) if per_page > 0 else 1
        
        # 格式化響應數據
        shift_types_list = []
        for shift_type in result:
            shift_types_list.append({
                'id': shift_type[0],
                'shift_name': shift_type[1],
                'description': shift_type[2],
                'is_active': shift_type[3],
                'sort_order': shift_type[4],
                'created_by': shift_type[5],
                'created_at': shift_type[6].isoformat() if shift_type[6] else None
            })
        
        # 構建響應
        response = {
            'success': True,
            'data': {
                'shift_types': shift_types_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages
                }
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        import traceback
        print(f"💥 [ERROR] get_shift_types exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'獲取班別列表失敗: {str(e)}'
        }), 500

@shift_types_bp.route("/", methods=["POST"])
@jwt_required()
def create_shift_type():
    """
    新增班別
    """
    db_manager = PostgresDBManager.get_instance()
    
    try:
        # 獲取當前用戶
        current_user_identity = get_jwt_identity()
        current_user = {}
        if isinstance(current_user_identity, str):
            try:
                current_user = json.loads(current_user_identity)
            except json.JSONDecodeError:
                current_user = {'username': current_user_identity}
        
        current_username = current_user.get('username', 'system')
        
        data = request.get_json()
        
        # 驗證必要欄位
        required_fields = ['shift_name']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'缺少必要欄位: {field}'
                }), 400
        
        # 檢查班別名稱是否已存在
        check_query = "SELECT id FROM shift_types WHERE shift_name = %s AND is_active = TRUE"
        existing = db_manager.execute_query(check_query, (data['shift_name'],))
        if existing:
            return jsonify({
                'success': False,
                'message': '班別名稱已存在'
            }), 400
        
        # 插入新班別
        insert_query = """
            INSERT INTO shift_types 
            (shift_name, description, sort_order, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        
        result = db_manager.execute_query(
            insert_query,
            (
                data['shift_name'],
                data.get('description', ''),
                data.get('sort_order', 0),
                current_username
            )
        )
        
        return jsonify({
            'success': True,
            'message': '班別新增成功',
        }), 201
        
    except Exception as e:
        import traceback
        print(f"💥 [ERROR] create_shift_type exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'新增班別失敗: {str(e)}'
        }), 500

@shift_types_bp.route("/", methods=["PUT"])
@jwt_required()
def update_shift_type():
    """
    更新班別
    """
    db_manager = PostgresDBManager.get_instance()
    
    try:
        # 獲取當前用戶
        current_user_identity = get_jwt_identity()
        current_user = {}
        if isinstance(current_user_identity, str):
            try:
                current_user = json.loads(current_user_identity)
            except json.JSONDecodeError:
                current_user = {'username': current_user_identity}
        
        current_username = current_user.get('username', 'system')
        data = request.get_json()
        
        shift_id = data['id']
        # 檢查班別是否存在
        check_query = "SELECT id FROM shift_types WHERE id = %s"
        existing = db_manager.execute_query(check_query, (shift_id,))
        if not existing:
            return jsonify({
                'success': False,
                'error': '班別不存在'
            }), 404
        
        # 如果修改了班別名稱，檢查是否與其他班別重複
        if 'shift_name' in data and data['shift_name']:
            name_check_query = "SELECT id FROM shift_types WHERE shift_name = %s AND id != %s AND is_active = TRUE"
            name_existing = db_manager.execute_query(name_check_query, (data['shift_name'], data['id']))
            if name_existing:
                return jsonify({
                    'success': False,
                    'error': '班別名稱已存在'
                }), 400
        
        # 構建更新語句
        update_fields = []
        update_params = []
        
        if 'shift_name' in data:
            update_fields.append("shift_name = %s")
            update_params.append(data['shift_name'])
        
        if 'description' in data:
            update_fields.append("description = %s")
            update_params.append(data['description'])
        
        if 'is_active' in data:
            update_fields.append("is_active = %s")
            update_params.append(data['is_active'])
        
        if 'sort_order' in data:
            update_fields.append("sort_order = %s")
            update_params.append(data['sort_order'])
        
        if not update_fields:
            return jsonify({
                'success': False,
                'error': '沒有提供更新欄位'
            }), 400
        
        # 添加更新者和ID參數
        update_fields.append("created_by = %s")  # 使用 created_by 替代原本的 updated_by
        update_params.append(current_username)
        update_params.append(data['id'])
        
        update_query = f"""
            UPDATE shift_types 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        db_manager.execute_query(update_query, tuple(update_params))
        
        return jsonify({
            'success': True,
            'message': '班別更新成功'
        }), 200
        
    except Exception as e:
        import traceback
        print(f"💥 [ERROR] update_shift_type exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'更新班別失敗: {str(e)}'
        }), 500

@shift_types_bp.route("/", methods=["DELETE"])
@jwt_required()
def delete_shift_type():
    """
    刪除班別（硬刪除）
    """
    db_manager = PostgresDBManager.get_instance()
    
    try:
        # 獲取當前用戶
        current_user_identity = get_jwt_identity()
        current_user = {}
        if isinstance(current_user_identity, str):
            try:
                current_user = json.loads(current_user_identity)
            except json.JSONDecodeError:
                current_user = {'username': current_user_identity}
        
        current_username = current_user.get('username', 'system')
        data = request.get_json()
        shift_id = data['id']
        # 檢查班別是否存在
        check_query = "SELECT id, shift_name FROM shift_types WHERE id = %s"
        existing = db_manager.execute_query(check_query, (shift_id,))
        if not existing:
            return jsonify({
                'success': False,
                'error': '班別不存在'
            }), 404
        
        # 硬刪除：直接從資料庫刪除
        delete_query = "DELETE FROM shift_types WHERE id = %s"
        
        db_manager.execute_query(delete_query, (shift_id,))
        
        return jsonify({
            'success': True,
            'message': '班別刪除成功'
        }), 200
        
    except Exception as e:
        import traceback
        print(f"💥 [ERROR] delete_shift_type exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'刪除班別失敗: {str(e)}'
        }), 500

@shift_types_bp.route("/<int:shift_type_id>", methods=["GET"])
@jwt_required()
def get_shift_type_detail(shift_type_id):
    """
    獲取單個班別詳情
    """
    db_manager = PostgresDBManager.get_instance()
    
    try:
        query = """
            SELECT id, shift_name, description, 
                   is_active, sort_order, created_by, created_at
            FROM shift_types 
            WHERE id = %s
        """
        
        result = db_manager.execute_query(query, (shift_type_id,))
        
        if not result:
            return jsonify({
                'success': False,
                'error': '班別不存在'
            }), 404
        
        shift_type = result[0]
        
        data = {
            'id': shift_type[0],
            'shift_name': shift_type[1],
            'description': shift_type[2],
            'is_active': shift_type[3],
            'sort_order': shift_type[4],
            'created_by': shift_type[5],
            'created_at': shift_type[6].isoformat() if shift_type[6] else None
        }
        
        return jsonify({
            'success': True,
            'data': data
        }), 200
        
    except Exception as e:
        import traceback
        print(f"💥 [ERROR] get_shift_type_detail exception: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'獲取班別詳情失敗: {str(e)}'
        }), 500