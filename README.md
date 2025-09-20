# Atetainer

これは、PythonのFletフレームワークとFastAPIを使用して構築されたゲームアプリケーションです。

## 概要



## 特徴

*   FletによるGUIクライアント
*   FastAPIによるバックエンドサーバー
*   マルチプレイ対戦機能
*   イベント向けの連続プレイ機能
*   Dockerによる簡単な環境構築

## 技術スタック

*   **クライアント**: Flet
*   **サーバー**: FastAPI, Uvicorn
*   **言語**: Python
*   **コンテナ化**: Docker, Docker Compose

## 実行方法

1.  DockerとDocker Composeがインストールされていることを確認してください。
2.  プロジェクトのルートディレクトリで、以下のコマンドを実行します。

    ```bash
    docker-compose up --build
    ```

3.  クライアントとサーバーが起動します。

## ファイル構成

```
.
├── app/                  # アプリケーションのソースコード
│   ├── server.py         # FastAPIサーバー
│   ├── client.py         # Fletクライアント
│   ├── game_manager.py   # ゲームロジック
│   ├── ai.py             # AIロジック
│   └── ...
├── docker-compose.yml    # Docker Compose設定ファイル
├── Dockerfile            # Dockerイメージビルド用ファイル
├── requirements.txt      # Python依存ライブラリ
└── README.md             # このファイル
```
