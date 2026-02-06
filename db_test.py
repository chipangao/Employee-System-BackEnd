import psycopg2
from psycopg2 import errors

class PostgresDBManager:
    def __init__(self, dbname="postgres", user="chipang", password="root", host="localhost", port="5432"):
        """Initialize the database connection parameters"""
        self.connection_params = {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish a connection to the database"""
        try:
            self.conn = psycopg2.connect(**self.connection_params)
            self.conn.autocommit = True
            self.cursor = self.conn.cursor()
            print("Connected to PostgreSQL database successfully.")
        except psycopg2.Error as e:
            print(f"Error connecting to PostgreSQL database: {e}")
            
    def close(self):
        """Close the database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("PostgreSQL connection is closed.")
    
    def list_database(self):
        """Create a new database"""
        try:
            self.cursor.execute("SELECT datname, datistemplate, datallowconn, datconnlimit, datdba FROM pg_database;")
            databases = self.cursor.fetchall()
            print("List of Databases and Details:")
            arr = []
            for db in databases:
                arr.append({
                   'Name': db[0],
                   'IsTemplate':db[1],
                   'AllowConnections':db[2],
                   'ConnectionLimit':db[3],
                   'OwnerOID':db[4]
                })
            return arr
        except psycopg2.Error as e:
            print(f"Error occur : {e}!")
            return False     
        
    def create_database(self, dbname):
        """Create a new database"""
        try:
            self.cursor.execute(f"CREATE DATABASE {dbname};")
            print(f"Database '{dbname}' created successfully.")
            return True
        except errors.DuplicateDatabase:
            print(f"Database '{dbname}' already exists.")
            return False
        except psycopg2.Error as e:
            print(f"Error creating database '{dbname}': {e}")
            return False
            
    def drop_database(self, dbname):
        """Drop an existing database"""
        try:
            if dbname == "postgres":
                print(f"Error dropping database '{dbname}'")
                return False
            self.cursor.execute(f"DROP DATABASE {dbname};")
            print(f"Database '{dbname}' dropped successfully.")
            return True
        except errors.InvalidCatalogName:
            print(f"Database '{dbname}' does not exist, nothing to drop.")
            return False
        except psycopg2.Error as e:
            print(f"Error dropping database '{dbname}': {e}")
            return False
    
    def create_table(self, table_name):
        """Create a table if it exists"""
        try:
            self.cursor.execute(f"CREATE TABLE {table_name};")
            print(f"Table '{table_name}' created successfully.")
            return True
        except psycopg2.Error as e:
            print(f"Error creating table '{table_name}': {e}")
            return False 
           
    def drop_table(self, table_name):
        """Drop a table if it exists"""
        try:
            self.cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
            print(f"Table '{table_name}' dropped successfully.")
            return True
        except psycopg2.Error as e:
            print(f"Error dropping table '{table_name}': {e}")
            return False
            
    def __enter__(self):
        """Support for context manager (with statement)"""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager (with statement)"""
        self.close()

# Example usage:
if __name__ == "__main__":
    db = PostgresDBManager()
    db.connect()
    db.list_database()
    db.close()
    # with PostgresDBManager() as db_manager:
    #     # Try to create a database
    #     db_manager.create_database("creation")
        
    #     # Try to drop a database
    #     db_manager.drop_database("creation")
        
    #     # Try to drop a table
    #     db_manager.create_table("creation")
        
    #     # Try to drop a table
    #     db_manager.drop_table("creation")