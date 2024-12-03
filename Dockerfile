# 使用輕量級的 Python 基礎映像
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 複製所需檔案到容器
COPY requirements.txt requirements.txt
COPY app.py app.py
COPY templates/index.html templates/index.html

# 安裝 Python 套件
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 Flask 預設埠
EXPOSE 5000

# 環境變數設置
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 啟動應用
CMD ["flask", "run"]
