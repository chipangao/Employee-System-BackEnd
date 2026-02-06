import psycopg2

conn = psycopg2.connect(database="postgres", 
                        user="chipang",
                        password="root", 
                        host="localhost", 
                        port="5432")

cursor = conn.cursor()

conn.autocommit = True
# try:
#     cursor.execute("CREATE DATABASE creation;");
#     print("Database 'creation' created successfully.")
# except psycopg2.errors.DuplicateDatabase:
#     print("Database 'creation' already exists.")

try:
    cursor.execute("DROP DATABASE creation;");
    print("Database 'creation' dropped successfully.")
except psycopg2.errors.DuplicateDatabase:
    print("Database 'creation' does not exist, nothing to drop.")

# try:
#     cursor.execute("DROP TABLE IF EXISTS creation;");  
#     print("Table 'creation' dropped successfully.") 
# except psycopg2.errors.UndefinedTable:
#     print("Table 'creation' does not exist, nothing to drop.")