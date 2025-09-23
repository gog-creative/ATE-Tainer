# ATE-Tainer V2

ATE-Tainerは、Gemini APIを活用したオリジナルのアキネイター風ゲームです。
AIが出すお題を、質問を繰り返して当ててみましょう！
なお、Discordの「AIアキネイター」というBOTを基に開発しました。V2とあるのはこのためです。

## ゲームのルール

### 概要

出題者（AI）が考えたお題を、プレイヤーが質問を繰り返して当てるゲームです。
他のプレイヤーの質問や回答もヒントになります。

### ゲームの流れ

1.  **ゲームに参加**
    *   指定されたゲームIDと、自分のニックネームを入力してゲームに参加します。

2.  **準備完了**
    *   参加者全員が「準備完了」ボタンを押すと、ゲームが開始されます。

3.  **質問**
    *   AIに対して、お題に関する質問をテキストで入力します。（例：「それは生き物ですか？」）
    *   AIは質問に対して「はい」「いいえ」「おそらくそう」「わからない」などで回答します。
    *   他のプレイヤーの質問とAIの回答も、チャット形式で見ることができます。
    *   質問できる回数には上限があります。

4.  **回答**
    *   お題がわかったら、いつでも回答を入力できます。（例：「りんご」）
    *   AIがあなたの回答が正解か不正解かを判定します。
    *   回答できる回数にも上限があります。

5.  **ゲーム終了**
    *   以下のいずれかの条件でゲーム終了となります。
        *   制限時間が経過した。
        *   接続しているプレイヤー全員が正解した。

6.  **結果発表**
    *   ゲームが終了すると、正解のお題と、正解したプレイヤーのランキング（解答時間が早い順）が表示されます。

7.  **次のゲームへ**
    *   結果発表後、自動的に新しいゲームが作成されます。続けてプレイする場合は、再度「接続」ボタンを押してください。

## 開発者向け情報

### 技術スタック

*   **バックエンド:** FastAPI (Python)
*   **フロントエンド:** Flet (Python)
*   **AI:** Google Gemini API
*   **リアルタイム通信:** WebSocket

### セットアップ

1.  **リポジトリをクローンします。**
    ```bash
    git clone https://github.com/your-username/ATE-Tainer.git
    cd ATE-Tainer
    ```

2.  **仮想環境を作成し、アクティベートします。**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux or macOS
    venv\Scripts\activate    # Windows
    ```

3.  **必要なライブラリをインストールします。**
    ```bash
    pip install -r app/requirements.txt
    ```

4.  **環境変数を設定します。**
    *   `.env` ファイルを `app` ディレクトリに作成します。
    *   以下の内容を記述し、ご自身のAPIキーとパスワードを設定してください。

    ```.env
    GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"
    password="YOUR_ADMIN_PASSWORD"
    ```

### 実行

1.  **サーバーを起動します。**
    *   `app` ディレクトリに移動し、以下のコマンドを実行します。
    ```bash
    cd app
    uvicorn server:fastapi --reload
    ```

2.  **クライアントを起動します。**
    *   別のターミナルを開き、`app` ディレクトリで以下のコマンドを実行します。
    ```bash
    flet run client.py
    ```

### ディレクトリ構成

```
C:.
├───.gitignore
├───build.md
├───docker-compose.yml
└───app
    ├───admin.html          # 管理者用Webパネル
    ├───ai.py               # Gemini APIとの連携ロジック
    ├───client.py           # Flet製のクライアントアプリケーション
    ├───game_manager.py     # ゲームの状態やロジックを管理
    ├───GEMINI.md
    ├───icon.ico
    ├───requirements.txt    # Pythonの依存ライブラリ
    ├───schemes.py          # Pydanticモデル（通信用のデータ構造の定義）
    ├───server.py           # FastAPI製のバックエンドサーバー
    └───themes.txt          # 次のゲームのお題候補
```