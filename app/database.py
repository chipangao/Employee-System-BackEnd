import psycopg2
from psycopg2 import errors, pool
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
                cls._instance.connection_params = {
                    'dbname': app.config.get('POSTGRES_DB', 'creation'),
                    'user': app.config.get('POSTGRES_USER', 'chipang'),
                    'password': app.config.get('POSTGRES_PASSWORD', 'root'),
                    'host': app.config.get('POSTGRES_HOST', 'localhost'),
                    'port': app.config.get('POSTGRES_PORT', '5432')
                }
                
                # 初始化連接池
                cls._instance._init_connection_pool(
                    min_conn=app.config.get('POSTGRES_MIN_CONN', 1),
                    max_conn=app.config.get('POSTGRES_MAX_CONN', 20)
                )
                
                # 註冊關閉鉤子 - 修改為使用 atexit
                atexit.register(cls._instance._close_pool)
                cls._pool_initialized = True
    
    def _init_connection_pool(self, min_conn=1, max_conn=20):
        """Initialize the connection pool"""
        try:
            self.connection_pool = pool.SimpleConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                **self.connection_params
            )
            self._shutting_down = False
            print(f"PostgreSQL connection pool initialized (min: {min_conn}, max: {max_conn})")
        except psycopg2.Error as e:
            print(f"Error initializing connection pool: {e}")
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
            conn = self.connection_pool.getconn()
            if conn and conn.closed:
                print("Connection was closed, creating new one...")
                # 不返回關閉的連接，創建新的
                self.connection_pool.putconn(conn)
                conn = psycopg2.connect(**self.connection_params)
            return conn
        except psycopg2.Error as e:
            print(f"Error getting connection from pool: {e}")
            # 如果連接池已關閉，創建一個新的獨立連接
            if "connection pool is closed" in str(e):
                print("Connection pool closed, creating temporary connection...")
                return psycopg2.connect(**self.connection_params)
            raise
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        if self._shutting_down:
            if conn:
                conn.close()
            return
            
        if self.connection_pool and conn:
            try:
                # 檢查連接是否還有效
                if conn.closed:
                    print("Connection is closed, not returning to pool")
                    return
                self.connection_pool.putconn(conn)
            except psycopg2.Error as e:
                print(f"Error returning connection to pool: {e}")
                # 如果無法返回連接池，直接關閉
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
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            
            if fetch==True:
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    # print('Fetched result:', result)
                    return result
                else:
                    conn.commit()
                    return cursor.rowcount
            else:
                conn.commit()
                return None
                
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            # print(f"Database error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)

    def connect(self):
        """Establish a connection to the database (legacy method)"""
        try:
            self.conn = self.get_connection()
            self.cursor = self.conn.cursor()
        except psycopg2.Error as e:
            print(f"Error connecting to PostgreSQL database: {e}")
            raise

    def _close_pool(self):
        """Close the connection pool safely"""
        if self._shutting_down:
            return
            
        self._shutting_down = True
        print("Closing database connection pool...")
        
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
                print("All database connections closed.")
            except Exception as e:
                print(f"Error closing connection pool: {e}")

    # def execute(self, query, params=None):
    #     """Execute a query within context manager"""
    #     if not self._current_cursor:
    #         raise RuntimeError("Must be used within 'with' context manager")
    #     return self._current_cursor.execute(query, params)
    
    # def fetchall(self):
    #     """Fetch all results within context manager"""
    #     if not self._current_cursor:
    #         raise RuntimeError("Must be used within 'with' context manager")
    #     return self._current_cursor.fetchall()
    
    # def fetchone(self):
    #     """Fetch one result within context manager"""
    #     if not self._current_cursor:
    #         raise RuntimeError("Must be used within 'with' context manager")
    #     return self._current_cursor.fetchone()
    
    def execute_returning(self, query, params=None):
        """執行查詢並返回結果(特別用於 INSERT ... RETURNING)"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            result = cursor.fetchone() if cursor.description else None
            
            conn.commit()
            return result
                
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)