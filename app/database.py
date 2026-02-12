# 修改導入部分
import psycopg
from psycopg_pool import ConnectionPool  # psycopg 3 的連線池
from psycopg import errors
from flask import current_app
import threading
import atexit

class PostgresDBManager:
    _instance = None
    _lock = threading.Lock()
    _pool_initialized = False
    
    def __init__(self, app=None):
        """Initialize the database connection parameters"""
        self.connection_pool = None
        self._shutting_down = False
        self._current_conn = None
        self._current_cursor = None
        if app is not None:
            self.init_app(app)
    
    def __enter__(self):
        """Enter the context manager - get connection from pool"""
        self._current_conn = self.get_connection()
        self._current_cursor = self._current_conn.cursor()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager - handle cleanup"""
        try:
            if exc_type is not None:
                # Exception occurred, rollback
                if self._current_conn:
                    self._current_conn.rollback()
            else:
                # No exception, commit
                if self._current_conn:
                    self._current_conn.commit()
        finally:
            # Always clean up
            if self._current_cursor:
                self._current_cursor.close()
            if self._current_conn:
                self.return_connection(self._current_conn)
            # Reset instance variables
            self._current_conn = None
            self._current_cursor = None
                    
    @classmethod
    def init_app(cls, app):
        """Initialize with Flask app"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                
                # ✅ psycopg 3 使用 dsn 字串更簡單
                dsn = f"dbname={app.config.get('POSTGRES_DB', 'creation')} " \
                      f"user={app.config.get('POSTGRES_USER', 'chipang')} " \
                      f"password={app.config.get('POSTGRES_PASSWORD', 'root')} " \
                      f"host={app.config.get('POSTGRES_HOST', 'localhost')} " \
                      f"port={app.config.get('POSTGRES_PORT', '5432')}"
                
                cls._instance.dsn = dsn
                
                # ✅ 初始化 psycopg 3 連接池
                cls._instance._init_connection_pool(
                    min_conn=app.config.get('POSTGRES_MIN_CONN', 1),
                    max_conn=app.config.get('POSTGRES_MAX_CONN', 20)
                )
                
                # 註冊關閉鉤子
                atexit.register(cls._instance._close_pool)
                cls._pool_initialized = True
    
    def _init_connection_pool(self, min_conn=1, max_conn=20):
        """Initialize the connection pool (psycopg 3 version)"""
        try:
            # ✅ psycopg 3 的 ConnectionPool API 不同
            self.connection_pool = ConnectionPool(
                conninfo=self.dsn,
                min_size=min_conn,
                max_size=max_conn,
                open=True  # 立即開啟連線池
            )
            self._shutting_down = False
            print(f"✅ PostgreSQL connection pool initialized (min: {min_conn}, max: {max_conn})")
        except psycopg.Error as e:
            print(f"❌ Error initializing connection pool: {e}")
            raise
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        if cls._instance is None:
            raise RuntimeError("Database manager not initialized")
        return cls._instance
    
    def get_connection(self):
        """Get a connection from the pool"""
        if self._shutting_down:
            raise RuntimeError("Database manager is shutting down")
            
        if self.connection_pool is None:
            raise RuntimeError("Connection pool not initialized")
        
        try:
            # ✅ psycopg 3 的連線池直接使用，不需 getconn/putconn
            conn = self.connection_pool.getconn()
            return conn
        except psycopg.Error as e:
            print(f"❌ Error getting connection from pool: {e}")
            # 如果連線池出問題，創建臨時連線
            if "pool is closed" in str(e):
                print("Connection pool closed, creating temporary connection...")
                return psycopg.connect(self.dsn)
            raise
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        if self._shutting_down or self.connection_pool is None:
            if conn:
                conn.close()
            return
            
        try:
            # ✅ psycopg 3 使用 putconn
            self.connection_pool.putconn(conn)
        except psycopg.Error as e:
            print(f"❌ Error returning connection to pool: {e}")
            try:
                conn.close()
            except:
                pass

    def execute_query(self, query, params=None, fetch=True):
        """Execute a query using connection pool"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            # ✅ psycopg 3 的 cursor 使用方式相同
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            
            if fetch:
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    return result
                else:
                    conn.commit()
                    return cursor.rowcount
            else:
                conn.commit()
                return None
                
        except psycopg.Error as e:
            if conn:
                conn.rollback()
            print(f"❌ Database error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)

    def execute_returning(self, query, params=None):
        """Execute query with RETURNING clause"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            result = cursor.fetchone() if cursor.description else None
            
            conn.commit()
            return result
                
        except psycopg.Error as e:
            if conn:
                conn.rollback()
            print(f"❌ Database error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)

    def _close_pool(self):
        """Close the connection pool safely"""
        if self._shutting_down:
            return
            
        self._shutting_down = True
        print("Closing database connection pool...")
        
        if self.connection_pool:
            try:
                # ✅ psycopg 3 使用 close()
                self.connection_pool.close()
                print("✅ All database connections closed.")
            except Exception as e:
                print(f"❌ Error closing connection pool: {e}")