import locale

translations = {
    "ja": {
        "language_display": "Japanese - 日本語 🇯🇵",
        "app_title": "ATE-Tainer - AIアキネーターゲーム",
        "app_subtitle": "Gemini APIを活用したオリジナルのアキネイターゲーム",
        "game_id": "ゲームID",
        "nickname": "ニックネーム",
        "connect": "接続",
        "disconnect": "切断",
        "ready": "準備完了",
        "send": "送信",
        "question": "質問",
        "answer": "回答",
        "question_or_answer": "質問または回答",
        "ai_response_placeholder": "ここにAIからの回答が表示されます",
        "game_info": "ゲーム情報",
        "genre": "ジャンル:",
        "participants": "参加者:",
        "unassigned": "未設定",
        "error_game_id_nickname_required": "ゲームIDとニックネームを入力してください。",
        "status_prefix_current": "現在 ",
        "status_waiting": "待機中",
        "status_playing": "ゲーム中",
        "status_finished": "終了済み",
        "status_game_start": "ゲーム開始！",
        "status_time_up": "入力時間終了",
        "new_game_created": "--- 新しいゲーム ({game_id}) が作成されました ---",
        "press_connect_again": "準備ができたら、もう一度「接続」ボタンを押してください。",
        "connected": "接続しました。 User ID: {user_id}",
        "disconnected": "切断しました。",
        "connection_error": "エラー: {error}",
        "receive_error": "受信エラー: {message}",
        "ready_sent": "準備完了を送信しました。",
        "loading_ai_response": "AIの応答: 読み込み中...",
        "question_from": "{name}の質問",
        "answer_from": "{name}の回答",
        "you": "あなた",
        "hidden": "（非表示）",
        "judgment": "判定: {judge}",
        "judge_true": "正解",
        "judge_false": "不正解",
        "ai_response": "AIの応答: {title} ({reply})",
        "error_dialog_title": "エラー",
        "http_error_404": "HTTPエラー: 404 - 指定されたゲームは存在ません。",
        "http_error_server": "HTTPエラー: {status_code} - サーバーエラーが発生しました。",
        "connection_error_dialog_title": "接続エラー",
        "connection_error_dialog_content": "サーバーに接続できませんでした。ネットワーク接続を確認してください。{exc}",
        "data_error_dialog_title": "データエラー",
        "data_error_dialog_content": "サーバーからのデータ形式が不正です。",
        "ok": "OK",
        "result_dialog_title": "結果発表！正解は「{answer}」でした！",
        "result_dialog_ranking": "ランキング",
        "result_dialog_no_correct_answerers": "正解者はいませんでした。",
        "result_dialog_close_button": "閉じる",
        "result_column_rank": "順位",
        "result_column_nickname": "ニックネーム",
        "result_column_time": "解答時間",
        "remaining_questions": "残り質問回数: {count}",
        "remaining_answers": "残り回答回数: {count}",
    },
    "en": {
        "language_display": "English - 英語 🇺🇸",
        "app_title": "ATE-Tainer - AI Akinator Game",
        "app_subtitle": "An original Akinator game using the Gemini API",
        "game_id": "Game ID",
        "nickname": "Nickname",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "ready": "Ready",
        "send": "Send",
        "question": "Question",
        "answer": "Answer",
        "question_or_answer": "Question or Answer",
        "ai_response_placeholder": "AI responses will be displayed here",
        "game_info": "Game Info",
        "genre": "Genre:",
        "participants": "Participants:",
        "unassigned": "Unassigned",
        "error_game_id_nickname_required": "Please enter Game ID and Nickname.",
        "status_prefix_current": "Current status: ",
        "status_waiting": "Waiting",
        "status_playing": "Playing",
        "status_finished": "Finished",
        "status_game_start": "Game Start!",
        "status_time_up": "Time's up",
        "new_game_created": "--- A new game ({game_id}) has been created ---",
        "press_connect_again": "When you are ready, press the 'Connect' button again.",
        "connected": "Connected. User ID: {user_id}",
        "disconnected": "Disconnected.",
        "connection_error": "Error: {error}",
        "receive_error": "Receive Error: {message}",
        "ready_sent": "Sent 'Ready' status.",
        "loading_ai_response": "AI Response: Loading...",
        "question_from": "Question from {name}",
        "answer_from": "Answer from {name}",
        "you": "You",
        "hidden": "(Hidden)",
        "judgment": "Judgment: {judge}",
        "judge_true": "Correct",
        "judge_false": "Incorrect",
        "ai_response": "AI Response: {title} ({reply})",
        "error_dialog_title": "Error",
        "http_error_404": "HTTP Error: 404 - The specified game does not exist.",
        "http_error_server": "HTTP Error: {status_code} - A server error occurred.",
        "connection_error_dialog_title": "Connection Error",
        "connection_error_dialog_content": "Could not connect to the server. Please check your network connection. {exc}",
        "data_error_dialog_title": "Data Error",
        "data_error_dialog_content": "Invalid data format from the server.",
        "ok": "OK",
        "result_dialog_title": "Result! The correct answer was '{answer}'!",
        "result_dialog_ranking": "Ranking",
        "result_dialog_no_correct_answerers": "There were no correct answerers.",
        "result_dialog_close_button": "Close",
        "result_column_rank": "Rank",
        "result_column_nickname": "Nickname",
        "result_column_time": "Time",
        "remaining_questions": "Remaining Questions: {count}",
        "remaining_answers": "Remaining Answers: {count}",
    }
}

# デフォルト言語を設定
default_lang = "ja"
try:
    # システムのロケールを取得
    lang, _ = locale.getdefaultlocale()
    if lang and lang.startswith("en"):
        default_lang = "en"
except Exception:
    # ロケール取得に失敗した場合はデフォルトのまま
    pass

# 現在の言語設定
_current_lang_dict = translations.get(default_lang, translations["en"])
_current_lang = default_lang

def set_language(lang: str):
    """
    UIの言語を設定します。
    """
    global _current_lang_dict, _current_lang
    _current_lang = lang
    _current_lang_dict = translations.get(lang, translations["en"])

def get_available_languages() -> dict[str, str]:
    """
    利用可能な言語のコードと表示名の辞書を取得します。
    """
    return {lang: data["language_display"] for lang, data in translations.items()}

def get_current_language() -> str:
    """
    現在の言語設定を取得します。
    """
    return _current_lang

def get_string(key: str, **kwargs) -> str:
    """
    指定されたキーに対応する翻訳文字列を取得します。
    プレースホルダーをkwargsで置換することも可能です。
    """
    # キーが見つからない場合は、キー自体を返すことで、どのキーが未翻訳か分かりやすくする
    text = _current_lang_dict.get(key, f"<{key}>")
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            # フォーマットに必要なキーがkwargsにない場合
            return f"<Formatting error for key: {key}>"
    return text
