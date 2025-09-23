
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from openai import pydantic_function_tool
from openai.types import ResponseFormatText
from os import environ
from dotenv import load_dotenv
import json

load_dotenv()

class Ai_Agent:
    """Ai_Agentクラスは、単語・人物名当てゲームの判定システムを提供します。このクラスは、ゲームのテーマ判定、質問への回答、ユーザーの回答判定を行うためのメソッドを備えています。
    Attributes:
        ai_type (Literal["gemini", "openai"]): 使用するAIの種類を指定します。
        model (str): 使用するAIモデルの名前を指定します。
        thinking (bool): AIが思考プロセスを出力するかどうかを指定します。
    Methods:
        check_game_thema(answer: str) -> Check_game_thema:
            ゲームの答えとして入力された単語や人物名が利用可能かどうかを判定し、利用可能であればそのジャンルや説明を返します。
        question(answer: str, question: str, answer_description: str = "") -> Question_schema:
            ユーザーからの質問に対して、AIが適切な回答を生成します。質問が曖昧または不適切な場合は回答不能とします。
        answer(answer: str, question: str, answer_description: str = "") -> Answer_schema:
            ユーザーの回答が正解かどうかを判定します。正解の場合は「正解」、不正解の場合は「不正解」を返します。
    内部クラス:
        Check_game_thema:
            ゲーム開始時の答え判定の返答スキーマを定義します。
            Attributes:
                thinking (str): 判定における思考プロセス。
                is_useable (bool): 答えが利用可能かどうか。
                thema (str): ゲームの答え（置き換え済み）。
                genre (str): 答えのジャンル。
                description (str): 答えについての説明。
        Question_schema:
            質問の返答スキーマを定義します。
            Attributes:
                thinking (str): 判定における思考プロセス。
                reply (Literal["はい", "条件によって・部分的にはい", "いいえ", "回答不能"]): 質問に対するAIの返答。
                include_answer (bool): 質問に答えが含まれているかどうか。
        Answer_schema:
            回答の返答スキーマを定義します。
            Attributes:
                thinking (str): 判定における思考プロセス。
                reply (Literal["正解", "不正解"]): ユーザーの回答が正解かどうか。
                is_close (bool): ユーザーの質問自体から答えを推測できるかどうか。"""
    
    #ゲーム開始時の答え判定の返答スキーマ
    class Check_game_thema(BaseModel):
        is_useable: bool = Field(description="1. 使用可能かどうか")
        thema:str = Field(description="2. ゲームの答え（置き換え済み）")
        genre:str = Field(description="3. 答えのジャンル（「[thema]は[genre]です」という文が成り立つように）")
        description:str = Field(description="4. 答えについての説明")

    #質問の返答スキーマ
    class Question_schema(BaseModel):
        reply: str = Field(description="質問に対する返答（いいえ、、今はいいえ、それを含む、場合によってはい、など一言で）")
        reason: str = Field(description="質問に対する返答（文章）。「正しいです」や「それは違います」、「今は違います」や「そういうものではありません。」など、臨機応変に一言文章で。\nプレイヤーに表示するため、答え・ヒントとなる関連ワードは使わずに「それは...」などで答えてください。")
        include_answer: bool = Field(description="その質問を他のプレイヤーが見たとき、それだけで明らかに答えが推測できてしまうかどうか（答えが含まれている場合など）")

    #回答の返答スキーマ
    class Answer_schema(BaseModel):
        reply: Literal["正解","不正解"] = Field(description="ユーザーの回答が正解かどうか")
        is_close: bool = Field(description="ユーザーの質問自体から答えを推測できるかどうか")

    def __init__(self, type:Literal["gemini","openai"], model: str, thinking:bool = True):
        self.ai_type = type
        self.model = model
        self.thinking = thinking
        match self.ai_type:
            case "gemini":
                self.gemini_client = genai.Client(api_key = environ["gemini_key"])
                
            case "openai":
                self.openai_client = AsyncOpenAI(api_key=environ["openai_key"])

            case _:
                raise ValueError("geminiまたはopenaiを入力してください")

    async def _generate(self, schema:type[BaseModel], system_prompt:str, text:str, propertyOrdering:list) -> BaseModel:
        json_schema = schema.model_json_schema()
        json_schema["propertyOrdering"] = propertyOrdering
        match self.ai_type:
            case "gemini":
                response = await self.gemini_client.aio.models.generate_content(
                    model = self.model,
                    contents = text,
                    config = types.GenerateContentConfig(
                        response_schema = json_schema,
                        response_mime_type="application/json",
                        system_instruction=system_prompt,
                        temperature=0.1,
                        #tools=[types.Tool(google_search=types.GoogleSearch())],
                        thinking_config=types.ThinkingConfig(
                            thinking_budget=512
                        )
                    )
                )
                return schema.model_validate_json(response.text or "{}")
            
            case "openai":
                json_schema["additionalProperties"] = False
                response = await self.openai_client.chat.completions.create(
                    model = self.model,
                    messages = [
                        {"role":"system", "content":system_prompt},
                        {"role": "user", "content":text}
                    ],
                    verbosity="low",
                    reasoning_effort="minimal",
                    #temperature = 0.1,
                    response_format = {
                        "type":"json_schema",
                        "json_schema":{
                            "name":json_schema["title"],
                            "strict":True,
                            "schema":json_schema
                        }
                       }
                )
                return schema.model_validate_json(response.choices[0].message.content or "{}")
            case _:
                raise ValueError()
    
    async def check_game_thema(self, answer:str) -> Check_game_thema:
        system_prompt = """あなたは単語・人物名当てゲームの判定システムです。
        これから単語当てクイズを始めるにあたり、ゲームを開始するユーザーがゲームの答えとなる単語・人物名を入力します。
        1. あなたは、その入力を答えとして利用可能かどうか判定してください
        判定基準：
            1. 入力が意味不明・曖昧ではないこと：
                ・「ゾンビ」や「ドラゴン」など、汎用的なキャラクターは不可
            2. 次のいずれかに該当すること：
        　      ・1つの明確な意味を持つ単語である
        　      ・著名な実在の人物
                ・特定の作品における架空のキャラクター名である
            3. 人物名やキャラクター名の場合：
                ・人物名などの場合において、考えうる人物が複数いる場合、より広く知られている人物とする。
        
        2. 答えとして利用可能である場合、上記の条件に従いもっとも一般的、もしくは正式な名称に置き換えてください。
            ・作品に登場する答えの場合、その作品名を括弧でくくって補足してください。

        3. 利用可能である場合、ヒントとなるようその答えのジャンルを出力してください。（人物、架空のキャラクター、動物、4文字熟語、映画、歌、○○学、ゲームなど）
            ・「[thema]は[genre]です。」という文が成り立つ必要があります。
        
        4. 答えについて、それが何かを誰でも分かるように説明をしてください。
        """
        
        schema = self.Check_game_thema.model_json_schema()
        print("生成開始",flush=True)
        response = await self._generate(self.Check_game_thema, system_prompt, answer, ["is_useable","thema","genre"])
        print(response,flush=True)
        return response
    
    async def question(self, answer:str, question:str, answer_description:str = "") -> Question_schema:
        system_prompt = f"""あなたは単語・人物名当てゲームの判定システムです。
        このゲームの答え：「{answer}」
        答えについての説明：「{answer_description}」
        ユーザーは答えについて質問をするので、回答してください。
        ・[単語]＋？　のように、単語だけで質問された場合、「{answer}は[単語]である」が成り立つかどうかで判定します。
        ・入力と同じ言語で回答してください。
        以下の場合は回答不能とします。
        1. 質問が曖昧、または意味不明な場合。
        2. 質問に答えが含まれる場合。この場合、include_answerをTrueとしてください。
        3. 最初の文字は〇ですか？など文字から当てようとしている質問の場合。
        4. あなたが質問に対する答えを知らない場合。"""

        response = await self._generate(self.Question_schema,system_prompt,question,["reply","include_answer"])
        print(response)
        validated = self.Question_schema.model_validate(response)

        return validated
    
    async def answer(self, answer:str, question:str,genre:str, answer_description:str = "") -> Answer_schema:
        system_prompt = f"""あなたは単語・人物名当てゲームの判定システムです。
        このゲームの答え：「{answer}」
        ユーザーに与えられているジャンル情報：「{genre}」
        答えについての説明：「{answer_description}」
        ユーザーは回答するので、それが正しいか判定してください。
        また、入力と同じ言語で応答してください。
        判定基準：
        ・ユーザーの回答が答えである、またはその表記揺れ（表記の違い・異なる書き方）の場合は正解とします。
        ・ユーザーの回答が、正解のカテゴリを包含するような上位概念（抽象的、広義の語）の場合、不正解とします。
        ただしジャンル内で、一般的にそれが答えのみを指す通称として用いられる場合は正解とします。
        """
        response = await self._generate(self.Answer_schema, system_prompt, question, ["reply","is_close"])
        print(response)
        return self.Answer_schema.model_validate(response)
