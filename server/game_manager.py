import asyncio
import datetime
from typing import Optional, TYPE_CHECKING, Literal
import uuid
import random
import json
from fastapi import HTTPException
from fastapi import WebSocket
from pydantic import BaseModel

import schemes
from ai import Ai_Agent

if TYPE_CHECKING:
    from .game_manager import GameManager

TZ = datetime.timezone(datetime.timedelta(hours=9))

# ユーザーデータ
class User_data(BaseModel):
    user_id: uuid.UUID
    is_player: bool
    nickname: str
    remaining_answering: int
    remaining_question: int
    answered_correctly: bool = False
    is_ready: bool = False
    answered_at: Optional[datetime.datetime] = None


# ゲーム
class Game_data:
    def __init__(
        self,
        game_id: int,
        answer: str,
        genre: str,
        answer_description: str,
        user: uuid.UUID,
        question_limit: int,
        ans_limit: int,
        time_limit: datetime.timedelta,
        ai_agent: Ai_Agent,
        game_manager: "GameManager",
        initial_post_data: schemes.NewGame_Post,
    ):
        self.game_id: int = game_id
        self.answer: str = answer                           # ゲームの答え
        self.genre: str = genre                             # 答えのジャンル
        self.answer_description: str = answer_description   # 答えの詳細な説明
        self.user: uuid.UUID = user                         # ゲームを作成したユーザーのID
        self.question_limit: int = question_limit           # プレイヤー1人あたりの質問回数上限
        self.ans_limit: int = ans_limit                     # プレイヤー1人あたりの回答回数上限
        self.time_limit: datetime.timedelta = time_limit    # ゲームの制限時間
        self.start_time: Optional[datetime.datetime] = None     # ゲームの開始時刻
        self.end_time: Optional[datetime.datetime] = None         # ゲームの終了時刻
        
        self.ai_agent = ai_agent                            # ゲームロジックを処理するAIエージェントのインスタンス
        self.timer_task: Optional[asyncio.Task] = None      # 制限時間を管理する非同期タスク
        
        self.users: dict[uuid.UUID, User_data] = {}         # ゲームに参加しているユーザーデータの辞書 (キー: user_id)
        self.connections: dict[WebSocket, Optional[uuid.UUID]] = {}          # 現在接続中のWebSocketコネクションのセット
        self.state: Literal["waiting", "playing", "finished", "redirected"] = "waiting"  # ゲームの進行状態
        self.messages: list[schemes.Res_Answer | schemes.Res_Question] = []  # ゲーム中にやりとりされた質問と回答の履歴
        self.correct_answerer: list[User_data] = []         # 正解したユーザーのリスト
        self.game_manager = game_manager                    # 親となるGameManagerのインスタンス
        self.initial_post_data = initial_post_data          # ゲーム作成時の初期設定データ
        self.manual_next_answer: Optional[str] = None       # 手動で設定された次ゲームのお題
        self.new_game_id:        Optional[int]

    @classmethod
    async def __aio_init__(
        cls,
        game_id: int,
        post_data: schemes.NewGame_Post,
        ai_agent: Ai_Agent,
        game_manager: "GameManager",
    ) -> "Game_data":
        res = await ai_agent.check_game_thema(post_data.answer)
        if not res.is_useable:
            raise HTTPException(400)
        answer = res.thema
        genre = res.genre
        answer_description = res.description

        return cls(
            game_id=game_id,
            answer=answer,
            genre=genre,
            answer_description=answer_description,
            user=post_data.user,
            question_limit=post_data.question_limit,
            ans_limit=post_data.ans_limit,
            time_limit=post_data.time_limit,
            ai_agent=ai_agent,
            game_manager=game_manager,
            initial_post_data=post_data,
        )

    async def check_all_ready(self):
        if len(self.users) > 0 and all(self.users[user_uuid].is_ready for user_uuid in self.connections.values() if user_uuid):
            await self.start_game()

    # ゲームのタイマー
    async def game_timer(self, time: int):
        try:
            # 毎秒判定して待機する
            for _ in range(time):
                # 接続中のプレイヤーが1人以上いて、かつ全員が正解済みの場合
                connected_user_ids = {uid for uid in self.connections.values() if uid is not None}
                connected_players = [
                    user
                    for user_id, user in self.users.items()
                    if user.is_player and user_id in connected_user_ids
                ]

                if len(connected_players) > 0 and all(
                    p.answered_correctly for p in connected_players
                ):
                    await self.game_over()
                    return
                
                await asyncio.sleep(1)
            await self.game_over()

        except asyncio.CancelledError:
            return

    async def start_game(self):
        self.state = "playing"
        self.start_time = datetime.datetime.now(TZ)
        self.end_time = self.start_time + self.time_limit
        self.timer_task = asyncio.create_task(self.game_timer(int(self.time_limit.total_seconds())))
        await self.broadcast(schemes.WSEvent(root=schemes.Event(type="game_start")))

    async def ai_question(self, question: str):
        return await self.ai_agent.question(
            answer=self.answer,
            question=question,
            answer_description=self.answer_description,
        )

    async def ai_answer(self, answer: str):
        return await self.ai_agent.answer(
            genre=self.genre,
            answer=self.answer,
            question=answer,
            answer_description=self.answer_description,
        )

    # イベント配信（レスポンスは個別に）
    async def broadcast(self, data: schemes.WSEvent):
        async def send(data: schemes.WSEvent, ws: WebSocket):
            try:
                await ws.send_text(data.root.model_dump_json())
            except Exception:
                print(f"{ws.client}への送信に失敗")
        await asyncio.gather(*(send(data, ws) for ws in self.connections.keys()))

    # タイムアウト時に呼び出される
    async def game_over(self):
        self.state = "finished"

        await self.broadcast(schemes.WSEvent(root=schemes.Event(type="timeup")))
        # 結果発表～！を配信
        await self.broadcast(
            schemes.WSEvent(
                root=schemes.Result(
                    correct_answer=self.answer,
                    description=self.answer_description,
                    correct_answerers=[
                        schemes.CorrectAnswerer(
                            user_id=user.user_id, nickname=user.nickname, answered_at=user.answered_at
                        )
                        for user in self.correct_answerer
                    ],
                )
            )
        )
        print("新規ゲームを作成")
        await asyncio.sleep(5)
        
        new_game_data = self.initial_post_data.model_copy(deep=True)
        if self.manual_next_answer:
            new_game_data.answer = self.manual_next_answer
        else:
            with open("themes.txt", "r", encoding="utf-8") as f:
                themes = f.readlines()
            new_game_data.answer = random.choice(themes).strip()

        new_game_id = await self.game_manager.create_game(new_game_data)
        print(f"新規ゲームID：{new_game_id}")
        await self.broadcast(
            schemes.WSEvent(root=schemes.NewGame_Redirect(game_id=new_game_id))
        )
        self.state = "redirected"
        self.new_game_id = new_game_id


class GameManager:
    def __init__(self, ai_agent: Ai_Agent):
        self.games: dict[int, Game_data] = {}
        self.ai = ai_agent

    async def create_game(self, data: schemes.NewGame_Post) -> int:
        game_id = random.randint(100000, 999999)
        while game_id in self.games:
            game_id = random.randint(100000, 999999)

        self.games[game_id] = await Game_data.__aio_init__(
            game_id=game_id,
            post_data=data,
            ai_agent=self.ai,
            game_manager=self,
        )
        return game_id

    def get_game(self, game_id: int) -> Optional[Game_data]:
        return self.games.get(game_id)