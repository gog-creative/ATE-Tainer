from fastapi import FastAPI, WebSocket, WebSocketDisconnect, WebSocketException
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from ai import Ai_Agent
import datetime
import uuid
import schemes
from dotenv import load_dotenv
from os import environ
from game_manager import GameManager, User_data
from google.genai import errors as ai_errors

load_dotenv()
ai = Ai_Agent("gemini", "gemini-2.5-flash")
#ai = Ai_Agent("openai", "gpt-5-mini")
fastapi = FastAPI()
fastapi.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)
game_manager = GameManager(ai)
TZ = datetime.timezone(datetime.timedelta(hours=9))

@fastapi.get("/", response_class=HTMLResponse)
async def panel():
    with open("admin.html","r", encoding="utf-8") as f:
        html = f.read()
    return html

@fastapi.post("/new_game")
async def post_new_game(data: schemes.NewGame_Post):
    if data.password != environ["password"]:
        raise HTTPException(403, "Password is incorect")
    try:
        game_id = await game_manager.create_game(data)
    except ai_errors.ServerError as e:
        raise HTTPException(503, e.message)
    return {"game_id": game_id}

@fastapi.post("/game_list")
async def get_game_list(data: schemes.GetGameList):
    if data.password != environ["password"]:
        raise HTTPException(403, "Password is incorrect")
    l = {}
    for id, game in game_manager.games.items():
        l[id] = {
            "status": game.state,
            "answer": game.answer,
            "connection_count": len(game.connections)
        }
    return l


@fastapi.post("/{game_id}/change_theme")
async def post_change_theme(game_id: int, data: schemes.ChangeTheme_Post):
    if data.password != environ["password"]:
        raise HTTPException(403, "Password is incorect")
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(404, "Unknown game ID.")
    game.manual_next_answer = data.answer
    if game.state == "finished":
        game.state = "redirected"
    return {"message": "Theme for the next game has been changed."}


@fastapi.get("/{game_id}/", response_model=schemes.GameData_Res)
async def get_gamedata(game_id: int, user_id: uuid.UUID):
    game = game_manager.get_game(game_id)
    if not game:
        raise HTTPException(404, "Unknown game ID.")

    return schemes.GameData_Res(
        messages=game.messages,
        genre=game.genre,
        ans_limit=game.ans_limit,
        question_limit=game.question_limit,
        start_time=game.start_time,
        end_time=game.end_time,
        status=game.state,
        users={uid:user.nickname for uid, user in game.users.items()}
    )


@fastapi.websocket("/{game_id}/")
async def websocket_broadcast(ws: WebSocket, game_id: int):
    try:
        game = game_manager.get_game(game_id)
        if not game:
            # Consider sending a WebSocket close message with a proper code
            await ws.close(code=4000, reason="Unknown game ID.")
            return

        await ws.accept()
        game.connections[ws] = None
        while True:
            if game.state == "redirected":
                await ws.send_text(schemes.NewGame_Redirect(game_id=game.new_game_id or 0).model_dump_json())
            msg = await ws.receive_json()
            data = schemes.WSEvent.model_validate({"root":msg})
            data = data.root
            # ここから受信内容のタイプ別に処理
            if data.type == "join_declare":
                if data.user in game.users:
                    game.connections[ws] = data.user
                    continue
                user = User_data(
                    user_id=data.user,
                    nickname=data.nickname,
                    is_player=data.is_player,
                    remaining_answering=game.ans_limit if data.is_player else 0,
                    remaining_question=game.question_limit if data.is_player else 0,
                )
                game.users[user.user_id] = user
                game.connections[ws] = user.user_id

            elif data.type == "ready":
                if game.state != "waiting":
                    continue
                user = game.users.get(data.user)
                if not user:
                    continue

                user.is_ready = True
                await game.check_all_ready()

            elif data.type == "question":
                if game.state != "playing":
                    await ws.send_text(
                        schemes.WSEvent(root=schemes.Response(text="ゲーム中ではありません。")).root.model_dump_json()
                    )
                    continue

                user = game.users[data.user]
                if user.remaining_question == 0:
                    await ws.send_text(schemes.Response(text="質問権がありません。").model_dump_json())
                    continue
                if user.answered_correctly:
                    await ws.send_text(
                        schemes.WSEvent(
                            root=schemes.Response(text="すでに正解済みです。")
                        ).root.model_dump_json()
                    )
                    continue
                try:
                    res = await game.ai_question(data.text)
                except Exception as e:
                    await ws.send_text(schemes.Response(text=f"AI処理中にエラーが発生しました：{e.args}").model_dump_json())
                    return
                # レスポンス
                await ws.send_text(schemes.Response(text=f"回答：{res.reply}（{res.reason}）").model_dump_json())
                broadcast_data = schemes.Res_Question(
                    time=datetime.datetime.now(TZ),
                    user=user.user_id,
                    nickname=user.nickname,
                    include_answer=res.include_answer,
                    title=res.reply,
                    question=data.text,
                    reply=res.reason,
                )

                # 配信
                game.users[data.user].remaining_question -= 1
                game.messages.append(broadcast_data)
                await game.broadcast(schemes.WSEvent(root=broadcast_data))

            elif data.type == "answer":
                if game.state != "playing":
                    await ws.send_text(
                        schemes.WSEvent(root=schemes.Response(text="ゲーム中ではありません。")).root.model_dump_json()
                    )
                    continue

                user = game.users[data.user]
                if user.remaining_answering == 0:
                    await ws.send_text(
                        schemes.WSEvent(
                            root=schemes.Response(text="回答権はもうありません。")
                        ).root.model_dump_json()
                    )
                    continue
                if user.answered_correctly:
                    await ws.send_text(
                        schemes.WSEvent(
                            root=schemes.Response(text="すでに正解済みです。")
                        ).root.model_dump_json()
                    )
                    continue
                try:
                    res = await game.ai_answer(data.text)
                except Exception as e:
                    await ws.send_text(schemes.Response(text=f"AI処理中にエラーが発生しました：{e.args}").model_dump_json())
                    return
    
                if res.reply == "正解":
                    user.answered_correctly = True
                    game.correct_answerer.append(user)

                # レスポンス
                await ws.send_text(schemes.Response(text=f"判定：{res.reply}").model_dump_json())
                broadcast_data = schemes.Res_Answer(
                    time=datetime.datetime.now(TZ),
                    user=user.user_id,
                    nickname=user.nickname,
                    include_answer=res.is_close,
                    judge=res.reply,
                    answer=data.text,
                )

                # 配信
                user.remaining_answering -= 1
                game.messages.append(broadcast_data)
                await game.broadcast(schemes.WSEvent(root=broadcast_data))

    except (WebSocketDisconnect, WebSocketException):
        if game and ws in game.connections:
            del game.connections[ws]