# gunicorn --workers=<整數> --threads=<整數> <wsgi檔名>:<app名稱> --daemon 背景執行
# gunicorn -c gunicorn.py wsgi:app --daemon

# # 开发环境
# export FLASK_ENV=development
# flask run

# # 生产环境
# export FLASK_ENV=production
# gunicorn --bind :5000 wsgi:app

# workers = 2
# max_requests = 1024
# daemon = False
# worker_class = "eventlet"  # 或 "gevent"
# # loglevel = 'info'
# # errorlog = "-"
# bind = "0.0.0.0:5000"


workers = 1  # 對於 Socket.IO，通常建議使用 1 個 worker
worker_class = "eventlet"  # 或 "gevent"
bind = "0.0.0.0:5000"
daemon = False
timeout = 60  # 增加超時時間
keepalive = 5  # 保持連接