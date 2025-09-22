from pydantic import BaseModel
import datetime
from typing import Literal, Union, Optional, List, Dict
import uuid

# WebSocketイベント用
## 受信用：参加宣言
class JoinDeclare(BaseModel):
    type: Literal["join_declare"] = "join_declare"
    user: uuid.UUID
    is_player: bool
    nickname: str

## 受信用
class Question(BaseModel):
    type: Literal["question"] = "question"
    user: uuid.UUID
    text: str

## 受信用
class Answer(BaseModel):
    type: Literal["answer"] = "answer"
    user: uuid.UUID
    text: str

class Ready(BaseModel):
    type: Literal["ready"] = "ready"
    user: uuid.UUID

## 配信用
class Res_Question(BaseModel):
    type: Literal["res_question"] = "res_question"
    time: datetime.datetime
    user: uuid.UUID
    nickname: str
    include_answer: bool
    title: str
    question: str
    reply: str

## 配信用
class Res_Answer(BaseModel):
    type: Literal["res_answer"] = "res_answer"
    time: datetime.datetime
    user: uuid.UUID
    nickname: str
    judge: Literal["正解","不正解"]
    include_answer: bool
    answer: str

## 配信用
class Event(BaseModel):
    type: Literal["timeup","game_start","wait"]

class CorrectAnswerer(BaseModel):
    user_id:uuid.UUID
    nickname: str
    answered_at: Optional[datetime.datetime]

class Result(BaseModel):
    type: Literal["result"] = "result"
    correct_answer: str
    description: str
    correct_answerers:List[CorrectAnswerer]

# 新規ゲームへリダイレクトさせる
class NewGame_Redirect(BaseModel):
    type: Literal["redirect"] = "redirect"
    game_id:int

## メッセージ表示用
class Response(BaseModel):
    type: Literal["response"] = "response"
    text: str

class WSEvent(BaseModel):
    root: Union[Ready, Result, JoinDeclare, Question, Answer, Event, Res_Question, Res_Answer, NewGame_Redirect, Response]

# RestAPI
class GameData_Res(BaseModel):
    genre: str
    ans_limit: int
    question_limit :int
    start_time: Optional[datetime.datetime]
    end_time: Optional[datetime.datetime]
    messages: List[Union[Res_Answer,Res_Question]]
    status: Literal['waiting', 'playing', 'finished', 'redirected']
    users: Dict[uuid.UUID, str]


class GetGameList(BaseModel):
    password: str

class NewGame_Post(BaseModel):
    user:   uuid.UUID
    password:   str
    answer:     str
    ans_limit:  int
    question_limit:int
    time_limit: datetime.timedelta

class ChangeTheme_Post(BaseModel):
    password: str
    answer: str