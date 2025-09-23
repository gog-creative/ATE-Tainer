# ベースイメージとして公式のPythonイメージを使用
FROM python:3.13-slim

# 作業ディレクトリを設定
WORKDIR /app

# ローカルのrequirements.txtをコンテナにコピー
COPY . .

# Pythonの依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコンテナにコピー
COPY . .

# Flaskアプリケーションを起動
CMD ["python3","-m", "uvicorn", "server:fastapi","--host", "0.0.0.0", "--port", "80"]