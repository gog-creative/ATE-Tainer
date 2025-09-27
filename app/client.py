import flet as ft
import websocket
import json
import uuid
import threading
import httpx
import datetime
from typing import Callable, Any, List, Union
import os
import logging
import sys
from pydantic import ValidationError
import schemes
from localization import get_string, set_language, get_available_languages, get_current_language

URL_DOMAIN = "gog-lab.org"
os.environ["debug"] = "True"

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path) # type: ignore
    return os.path.join(os.path.abspath("."), relative_path)

# ---------------------------------------------------------------------------- #
# 1. WebSocket Client (Handles Network Communication)
# ---------------------------------------------------------------------------- #
class WebSocketClient:
    """Manages the WebSocket connection and communication, independent of the UI."""
    def __init__(self,
                 on_open: Callable[[], None],
                 on_message: Callable[[str], None],
                 on_error: Callable[[str], None],
                 on_close: Callable[[], None]):
        self.ws_app = None
        self.thread = None
        self.is_connected = False
        self.nickname = ""
        self.user_id: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.getnode()))

        self._on_open_callback = on_open
        self._on_message_callback = on_message
        self._on_error_callback = on_error
        self._on_close_callback = on_close

    def _on_message(self, ws, message: str):
        if os.environ.get('debug') == 'True':
            logging.info(f"RECV: {message}")
        self._on_message_callback(message)

    def _on_error(self, ws, error):
        self.is_connected = False
        self._on_error_callback(str(error))

    def _on_close(self, ws, close_status_code, close_msg):
        self.is_connected = False
        self._on_close_callback()

    def _on_open(self, ws):
        self.is_connected = True
        join_data = schemes.JoinDeclare(
            user=self.user_id,
            is_player=True,
            nickname=self.nickname
        )
        self.send_message(json.dumps(join_data.model_dump(mode='json')))
        self._on_open_callback()

    def connect(self, game_id: str, nickname: str):
        if self.is_connected:
            return
        self.nickname = nickname
        uri = f"wss://{URL_DOMAIN}/{game_id}/"
        self.ws_app = websocket.WebSocketApp(uri,
                                  on_open=self._on_open,
                                  on_message=self._on_message,
                                  on_error=self._on_error,
                                  on_close=self._on_close)

        self.thread = threading.Thread(target=self.ws_app.run_forever, daemon=True)
        self.thread.start()

    def disconnect(self):
        if self.ws_app and self.is_connected:
            self.ws_app.close()

    def send_message(self, message: str):
        if self.ws_app and self.is_connected:
            if os.environ.get('debug') == 'True':
                logging.info(f"SEND: {message}")
            self.ws_app.send(message)
        else:
            self._on_error_callback("Not connected.")

# ---------------------------------------------------------------------------- #
# 2. Main Application Control (UI and Logic)
# ---------------------------------------------------------------------------- #
class GameClientControl(ft.Column):
    """Encapsulates the entire game client UI and its logic."""
    def __init__(self, page: ft.Page):
        super().__init__(expand=True)
        self.page = page
        self.ws_client = WebSocketClient(
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )
        self.countdown_thread = None
        self.countdown_stop_event = threading.Event()
        self.update_thread = None
        self.update_stop_event = threading.Event()
        self.is_ready_sent = False
        self.last_question_sent = None
        self.game_is_over = False

        self._event_handlers = {
            "res_question": self._handle_res_question,
            "res_answer": self._handle_res_answer,
            "redirect": self._handle_redirect,
            "game_start": self._handle_game_start,
            "timeup": self._handle_game_end,
            "result": self._handle_game_end,
            "response": self._handle_response,
        }
        
        self._init_ui_components()
        self._build_ui()

    def _build_ui(self):
        """Build the UI structure for this control."""
        self.connection_view = ft.Row(
            [self.connect_column],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True
        )

        self.game_view = ft.Column(
            [
                self.game_controls_row,
                ft.Row(
                    [self.side_panel, self.main_content_column],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START
                )
            ],
            visible=False,
            expand=True
        )
        self.controls = [self.connection_view, self.game_view]

    def _init_ui_components(self):
        """Create all UI components."""
        self.game_id_input = ft.TextField(width=250, input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]"))
        self.nickname_input = ft.TextField(width=250)
        self.connect_button = ft.FilledButton(on_click=self._connect_click, width=250,style=ft.ButtonStyle(shape=ft.StadiumBorder(), padding=20))
        
        self.title_text = ft.Text("ATE-Tainer", size=50, weight=ft.FontWeight.BOLD)
        self.subtitle_text = ft.Text(size=20)
        self.version_text = ft.Text("build-20250927 (2.0.5.0)", color=ft.Colors.GREY, size=12)
        
        languages = get_available_languages()
        self.language_dropdown = ft.Dropdown(
            width=250,
            options=[ft.dropdown.Option(key=lang_code, text=display_name) for lang_code, display_name in languages.items()],
            value=get_current_language(),
            on_change=self._language_changed,
        )
        
        self.connect_column = ft.Column(
            [
                self.title_text,
                self.subtitle_text,
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                self.game_id_input,
                self.nickname_input,
                self.connect_button,
                self.language_dropdown,
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                self.version_text,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15
        )

        self.disconnect_button = ft.ElevatedButton(on_click=self._disconnect_click)
        self.timer_text = ft.Text("--:--", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_800)
        
        self.status_text = ft.Text(weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER)
        self.status_panel = ft.Container(
            content=self.status_text,
            padding=10,
            border_radius=5,
            visible=False,
            alignment=ft.alignment.center
        )
        
        self.game_controls_row = ft.Row(
            [self.disconnect_button, self.status_panel, self.timer_text], 
            alignment=ft.MainAxisAlignment.START, 
            vertical_alignment=ft.CrossAxisAlignment.CENTER, 
            spacing=15
        )

        self.message_input = ft.TextField(expand=True, disabled=True, on_submit=self._send_click)
        self.qa_mode_selector = ft.CupertinoSlidingSegmentedButton(selected_index=0, controls=[ft.Text(), ft.Text()], disabled=True)
        self.send_button = ft.ElevatedButton(on_click=self._send_click, disabled=True)
        self.chat_input_row = ft.Row([self.message_input, self.qa_mode_selector, self.send_button], spacing=15, visible=False)

        self.chat_area = ft.ListView(expand=True, spacing=15, auto_scroll=True)
        self.chat_area_container = ft.Container(self.chat_area, border=ft.border.all(1, ft.Colors.GREY), border_radius=5, padding=15, expand=True)
        
        self.ai_response_text = ft.Text(size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER, color=ft.Colors.BLACK)
        self.ai_response_panel = ft.Container(
            content=self.ai_response_text,
            padding=20,
            border=ft.border.all(2, ft.Colors.BLUE_GREY_200),
            border_radius=10,
            bgcolor=ft.Colors.BLUE_GREY_50,
            visible=True,
            alignment=ft.alignment.center,
            margin=ft.margin.only(bottom=10)
        )
        
        self.ready_button = ft.ElevatedButton(on_click=self._ready_click, width=250, style=ft.ButtonStyle(shape=ft.StadiumBorder(), padding=20))
        self.ready_row = ft.Row([self.ready_button], alignment=ft.MainAxisAlignment.CENTER, visible=False)

        self.main_content_column = ft.Column([self.ai_response_panel, self.chat_area_container, self.chat_input_row, self.ready_row], expand=True)

        self.genre_text = ft.Text()
        self.question_limit_text = ft.Text()
        self.answer_limit_text = ft.Text()
        self.participants_list = ft.ListView(spacing=5, expand=False)
        self.side_panel_game_info_title = ft.Text(size=20, weight=ft.FontWeight.BOLD)
        self.side_panel_genre_title = ft.Text(weight=ft.FontWeight.BOLD)
        self.side_panel_question_limit_title = ft.Text(weight=ft.FontWeight.BOLD)
        self.side_panel_answer_limit_title = ft.Text(weight=ft.FontWeight.BOLD)
        self.side_panel_participants_title = ft.Text(weight=ft.FontWeight.BOLD)
        self.side_panel = ft.Container(content=ft.Column([
            self.side_panel_game_info_title, ft.Divider(), 
            self.side_panel_genre_title, self.genre_text, 
            self.question_limit_text,
            self.answer_limit_text,
            ft.Divider(), 
            self.side_panel_participants_title, self.participants_list
        ]), width=250, padding=15, border=ft.border.all(1, ft.Colors.GREY), border_radius=5)
        
        self._update_ui_texts()

    def _update_ui_texts(self):
        """Update all UI component texts based on the current language."""
        self.page.title = get_string("app_title")
        self.subtitle_text.value = get_string("app_subtitle")
        self.game_id_input.label = get_string("game_id")
        self.nickname_input.label = get_string("nickname")
        self.connect_button.text = get_string("connect")
        self.disconnect_button.text = get_string("disconnect")
        self.message_input.label = get_string("question_or_answer")
        self.qa_mode_selector.controls[0].value = get_string("question")
        self.qa_mode_selector.controls[1].value = get_string("answer")
        self.send_button.text = get_string("send")
        self.ai_response_text.value = get_string("ai_response_placeholder")
        self.ready_button.text = get_string("ready")
        self.side_panel_game_info_title.value = get_string("game_info")
        self.side_panel_genre_title.value = get_string("genre")
        self.side_panel_participants_title.value = get_string("participants")
        self.update()

    def _language_changed(self, e):
        """Handle language selection change."""
        set_language(e.control.value)
        self._update_ui_texts()

    # --- UI Event Handlers ---
    def _connect_click(self, e):
        self.connect_button.disabled = True
        self.is_ready_sent = False
        self.game_is_over = False
        game_id = self.game_id_input.value or "".strip()
        nickname = self.nickname_input.value
        if not game_id or not nickname:
            self._add_raw_message_to_chat(get_string("error_game_id_nickname_required"))
            self.connect_button.disabled = False
            return

        self.ai_response_text.value = get_string("ai_response_placeholder")
        self.status_panel.visible = False
        self.chat_area.controls.clear()
        self.update()

        try:
            api_url = f"https://{URL_DOMAIN}/{game_id}/?user_id={self.ws_client.user_id}"
            response = httpx.get(api_url)
            response.raise_for_status()
            
            game_data = schemes.GameData_Res.model_validate(response.json())
            
            for message in game_data.messages:
                self._add_formatted_message(message)
            
            self._handle_status(game_data)
            self.ws_client.connect(game_id, nickname)
            self._set_ui_for_connected(True)

            # Start periodic updates
            self.update_stop_event.clear()
            self.update_thread = threading.Thread(target=self._periodic_update_logic, daemon=True)
            self.update_thread.start()

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                self._show_error_dialog(get_string("error_dialog_title"), get_string("http_error_404"))
            else:
                self._show_error_dialog(get_string("error_dialog_title"), get_string("http_error_server", status_code=exc.response.status_code))
            self.connect_button.disabled = False
        except httpx.RequestError as exc:
            self._show_error_dialog(get_string("connection_error_dialog_title"), get_string("connection_error_dialog_content", exc=exc))
            print(f"RequestError: {exc}")
            self.connect_button.disabled = False
        except ValidationError as exc:
            error_message = get_string("data_error_dialog_content")
            self._show_error_dialog(get_string("data_error_dialog_title"), error_message)
            print(f"ValidationError: {exc}")
            if 'response' in locals() and response:
                print("Received data:", response.text)
            self.connect_button.disabled = False

    def _disconnect_click(self, e):
        self.update_stop_event.set()
        self.ws_client.disconnect()
        self._set_ui_for_connected(False)
        self.connect_button.disabled = False

    def _ready_click(self, e):
        self.ws_client.send_message(json.dumps({"type": "ready", "user": str(self.ws_client.user_id)}))
        self.ready_button.disabled = True
        self.is_ready_sent = True
        self._add_raw_message_to_chat(get_string("ready_sent"))
        self.update()

    def _send_click(self, e):
        text = self.message_input.value
        if not text:
            return
        
        self._set_game_controls_enabled(False)
        mode = "question" if self.qa_mode_selector.selected_index == 0 else "answer"

        if mode == "question":
            placeholder_data = {
                "type": "local_question_loading",
                "user": self.ws_client.user_id,
                "question": text,
                "nickname": self.ws_client.nickname
            }
            self._add_formatted_message(placeholder_data)
            self.last_question_sent = text
            data_to_send = schemes.Question(user=self.ws_client.user_id, text=text)
        else:
            data_to_send = schemes.Answer(user=self.ws_client.user_id, text=text)

        self.ws_client.send_message(data_to_send.model_dump_json())
        self.message_input.value = ""
        self.update()

    # --- WebSocket Callback Handlers ---
    def _on_ws_open(self):
        self._add_raw_message_to_chat(get_string("connected", user_id=self.ws_client.user_id))

    def _on_ws_message(self, message: str):
        try:
            event = schemes.WSEvent.model_validate({"root":json.loads(message)}).root
            
            handler = self._event_handlers.get(event.type)
            if handler:
                handler(event)
            else:
                print(f"No handler for event type: {event.type}")

        except (ValidationError, json.JSONDecodeError) as e:
            self._add_raw_message_to_chat(get_string("receive_error", message=message))
            print(f"Error parsing message: {e}")

    def _on_ws_error(self, error: str):
        self._add_raw_message_to_chat(get_string("connection_error", error=error))

    def _on_ws_close(self):
        self.countdown_stop_event.set()
        self.update_stop_event.set()
        self._add_raw_message_to_chat(get_string("disconnected"))
        self._handle_disconnect(None)
        self.connect_button.disabled = False

    # --- Server Event Handlers ---
    def _handle_response(self, data: schemes.Response):
        if self.last_question_sent:
            placeholder = next((c for c in self.chat_area.controls if isinstance(c, ft.Row) and c.data == self.last_question_sent), None)
            if placeholder:
                self.chat_area.controls.remove(placeholder)
            self.last_question_sent = None

        self._add_raw_message_to_chat(f"{data.text}", color=ft.Colors.BLUE)
        self._set_game_controls_enabled(True)

    def _handle_res_question(self, data: schemes.Res_Question):
        placeholder = next((c for c in self.chat_area.controls if isinstance(c, ft.Row) and c.data == data.question), None)
        if placeholder:
            self.chat_area.controls.remove(placeholder)

        if self.game_is_over:
            self.update()
            return

        if data.user == self.ws_client.user_id:
            self.last_question_sent = None
            self._set_game_controls_enabled(True)
            self.question_limit_text.value = get_string("question_limit", count=data.remaining_count)

        if data.title:
            response_text = f"{data.title} \n{data.reply}"
            self._show_ai_response(response_text)

        self._add_formatted_message(data)
        self.update()

    def _handle_res_answer(self, data: schemes.Res_Answer):
        if self.game_is_over:
            return

        judge_text = get_string("judge_true") if data.judge else get_string("judge_false")
        self._show_ai_response(get_string("judgment", judge=judge_text))

        self._add_formatted_message(data)
        if data.user == self.ws_client.user_id:
            self._set_game_controls_enabled(True)
            self.answer_limit_text.value = get_string("answer_limit", count=data.remaining_count)
        self.update()

    def _handle_disconnect(self, data: Any):
        self._set_ui_for_connected(False)
        self._set_game_controls_enabled(False)
        self.update()

    def _handle_redirect(self, data: schemes.NewGame_Redirect):
        self.countdown_stop_event.set()
        self.game_id_input.value = str(data.game_id)
        self.chat_area.controls.clear()
        self._add_raw_message_to_chat(get_string("new_game_created", game_id=data.game_id), color=ft.Colors.BLUE)
        self._add_raw_message_to_chat(get_string("press_connect_again"))
        self.ws_client.disconnect()
        self.update()

    def _handle_game_start(self, data: schemes.Event):
        self._set_game_controls_enabled(True)
        self.chat_input_row.visible = True
        self.ready_row.visible = False
        self.ai_response_text.value = ""
        self._update_status_panel(get_string("status_game_start"), ft.Colors.GREEN_700)
        
        def fetch_status_and_start_countdown(game_id):
            try:
                api_url = f"https://{URL_DOMAIN}/{game_id}/?user_id={self.ws_client.user_id}"
                response = httpx.get(api_url)
                response.raise_for_status()
                game_data = schemes.GameData_Res.model_validate(response.json())
                self.page.run_thread(self._handle_status, game_data) if self.page else None
            except Exception as e:
                self.page.run_thread(self._add_raw_message_to_chat, f"タイマー開始エラー: {e}") if self.page else None

        if self.game_id_input.value:
            threading.Thread(target=fetch_status_and_start_countdown, args=(self.game_id_input.value,), daemon=True).start()
        self.update()

    def _handle_status(self, data: schemes.GameData_Res):
        self.genre_text.value = data.genre or get_string("unassigned")
        # ゲームプレイ中はWebSocketからの情報で更新するため、ここでは更新しない
        if data.status != "playing":
            self.question_limit_text.value = get_string("question_limit", count=data.question_limit)
            self.answer_limit_text.value = get_string("answer_limit", count=data.ans_limit)
        self.participants_list.controls.clear()
        for nickname in data.users.values():
            self.participants_list.controls.append(ft.Text(f"- {nickname}"))

        if data.status == "playing" and data.end_time:
            self._set_game_controls_enabled(True)
            self.chat_input_row.visible = True
            self.ready_row.visible = False
            self._update_status_panel(get_string("status_playing"), ft.Colors.GREEN_700)
            self._start_countdown(data.end_time.isoformat())
        else:
            self._set_game_controls_enabled(False)
            self.chat_input_row.visible = False
            state_text = {
                "waiting": get_string("status_waiting"), 
                "finished": get_string("status_finished")
            }.get(data.status, data.status)
            
            status_prefix = get_string("status_prefix_current")
            
            if data.status == "waiting":
                self.ready_row.visible = True
                self.ready_button.disabled = self.is_ready_sent
                self._update_status_panel(f"{status_prefix}{state_text}", ft.Colors.AMBER_700)
            else: # finished
                self.ready_row.visible = False
                self._update_status_panel(f"{status_prefix}{state_text}", ft.Colors.RED_700)
        self.update()

    def _handle_game_end(self, data: Union[schemes.Event, schemes.Result]):
        self.game_is_over = True
        self.countdown_stop_event.set()
        self._set_game_controls_enabled(False)
        self._update_status_panel(get_string("status_time_up"), ft.Colors.RED_700)
        if isinstance(data, schemes.Result):
            self._show_result_dialog(data)
        self.update()

    def _show_result_dialog(self, data: schemes.Result):
        def close_dialog(e):
            self.page.close(dlg) if self.page else None

        # Sort answerers by time
        sorted_answerers = sorted(data.correct_answerers, key=lambda x: x.answer_time)

        # Create data rows
        rows = []
        for i, answerer in enumerate(sorted_answerers):
            # timedeltaを分:秒.ミリ秒の形式にフォーマット
            total_seconds = answerer.answer_time.total_seconds()
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            milliseconds = int((total_seconds - int(total_seconds)) * 100)
            time_str = f"{minutes:02d}分{seconds:02d}秒{milliseconds:02d}"

            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(i + 1))),
                    ft.DataCell(ft.Text(answerer.nickname)),
                    ft.DataCell(ft.Text(time_str)),
                ])
            )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(get_string("result_dialog_title", answer=data.correct_answer)),
            content=ft.Column(
                [
                    ft.Text(data.description, size=16),
                    ft.Divider(),
                    ft.Text(get_string("result_dialog_ranking"), size=20, weight=ft.FontWeight.BOLD),
                    ft.DataTable(
                        columns=[
                            ft.DataColumn(ft.Text(get_string("result_column_rank"))),
                            ft.DataColumn(ft.Text(get_string("result_column_nickname"))),
                            ft.DataColumn(ft.Text(get_string("result_column_time"))),
                        ],
                        rows=rows,
                    ) if rows else ft.Text(get_string("result_dialog_no_correct_answerers")),
                ],
                tight=True,
                width=500,
                scroll=ft.ScrollMode.ADAPTIVE,
            ),
            actions=[ft.TextButton(get_string("result_dialog_close_button"), on_click=close_dialog)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg) if self.page else None
        self.page.update() if self.page else None

    def _periodic_update_logic(self):
        """Periodically fetches game data and updates the UI."""
        while not self.update_stop_event.wait(5):  # Wait for 5 seconds
            if not self.ws_client.is_connected:
                break
            try:
                game_id = self.game_id_input.value
                if not game_id: continue

                api_url = f"https://{URL_DOMAIN}/{game_id}/?user_id={self.ws_client.user_id}"
                response = httpx.get(api_url)
                response.raise_for_status()
                game_data = schemes.GameData_Res.model_validate(response.json())
                
                if self.page:
                    self._handle_status(game_data)

            except httpx.HTTPStatusError as exc:
                # Game might have ended and been removed, stop polling.
                if exc.response.status_code == 404:
                    break
            except Exception as e:
                print(f"Error during periodic update: {e}")

    # --- Message & Card Builders ---
    def _add_raw_message_to_chat(self, text: str, color: str = ft.Colors.WHITE):
        self.chat_area.controls.append(ft.Container(ft.Text(text, color=color, weight=ft.FontWeight.BOLD)))
        self.update()

    def _add_formatted_message(self, msg_data: Union[schemes.Res_Question, schemes.Res_Answer, dict]):
        card_builders = {
            "local_question_loading": self._build_loading_card,
            "res_question": self._build_question_card,
            "res_answer": self._build_answer_card,
        }

        if isinstance(msg_data, dict):
            msg_type = msg_data.get("type")
            is_own = True
        else:
            msg_type = msg_data.type
            is_own = msg_data.user == self.ws_client.user_id

        builder = card_builders.get(msg_type or "")
        if not builder: return

        card = builder(msg_data)
        message_row = ft.Row([card], alignment=ft.MainAxisAlignment.END if is_own else ft.MainAxisAlignment.START)
        
        if msg_type == "local_question_loading" and isinstance(msg_data, dict):
            question = msg_data.get("question")
            if isinstance(question, str):
                message_row.data = question

        self.chat_area.controls.append(message_row)
        self.update()

    def _build_card_container(self, card_items: List[ft.Control], is_own: bool) -> ft.Container:
        return ft.Container(
            content=ft.Column(card_items, spacing=5),
            padding=12, border_radius=10,
            bgcolor=ft.Colors.LIGHT_BLUE_100 if is_own else ft.Colors.GREY_200,
        )

    def _build_loading_card(self, data: dict) -> ft.Container:
        display_name = get_string("you")
        question = data.get("question", "")
        card_items = [
            ft.Text(get_string("question_from", name=display_name), weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
            ft.Text(f'''{question}''', color=ft.Colors.BLACK),
            ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
            ft.Text(get_string("loading_ai_response"), italic=True, color=ft.Colors.BLACK)
        ]
        return self._build_card_container(card_items, is_own=True)

    def _build_question_card(self, data: schemes.Res_Question) -> ft.Container:
        is_own = data.user == self.ws_client.user_id
        display_name = get_string("you") if is_own else data.nickname
        card_items: list[ft.Control] = [
            ft.Text(get_string("question_from", name=display_name), weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
        ]
        if not data.include_answer:
            card_items.append(ft.Text(f"{data.question}", color=ft.Colors.BLACK))
        else:
            card_items.append(ft.Text(get_string("hidden"), italic=True, color=ft.Colors.BLACK))

        if data.title:
            card_items.extend([
                ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                ft.Text(get_string("ai_response", title=data.title, reply=data.reply), color=ft.Colors.BLACK)
            ])
        return self._build_card_container(card_items, is_own)

    def _build_answer_card(self, data: schemes.Res_Answer) -> ft.Container:
        is_own = data.user == self.ws_client.user_id
        display_name = get_string("you") if is_own else data.nickname
        card_items = [
            ft.Text(get_string("answer_from", name=display_name), weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
        ]
        if data.judge or data.include_answer:
            card_items.append(ft.Text(get_string("hidden"), italic=True, color=ft.Colors.BLACK))
        else:
            card_items.append(ft.Text(f"'''{data.answer}'''", color=ft.Colors.BLACK))

        if data.judge is not None:
            judge_text = get_string("judge_true") if data.judge else get_string("judge_false")
            card_items.extend([
                ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                ft.Text(get_string("judgment", judge=judge_text), weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK)
            ])
        return self._build_card_container(card_items, is_own)

    # --- UI State Helpers ---
    def _update_status_panel(self, text: str, bgcolor: str):
        """Updates the status panel with a message and background color."""
        self.status_text.value = text
        self.status_panel.bgcolor = bgcolor
        self.status_panel.visible = True
        self.update()

    def _show_ai_response(self, text: str):
        """AIレスポンスパネルにテキストを表示し、表示状態にする。"""
        self.ai_response_text.value = text
        self.ai_response_panel.visible = True
        self.update()

    def _set_ui_for_connected(self, is_connected: bool):
        self.connection_view.visible = not is_connected
        self.game_view.visible = is_connected
        if not is_connected:
            self.timer_text.value = "--:--"
            self.genre_text.value = ""
            self.participants_list.controls.clear()

    def _set_game_controls_enabled(self, is_enabled: bool):
        self.message_input.disabled = not is_enabled
        self.qa_mode_selector.disabled = not is_enabled
        self.send_button.disabled = not is_enabled
        self.update()

    def _show_error_dialog(self, title: str, content: str):
        def close_dialog(e):
            self.page.close(dlg) if self.page else None

        dlg = ft.AlertDialog(
            modal=True, title=ft.Text(title), content=ft.Text(content),
            actions=[ft.TextButton(get_string("ok"), on_click=close_dialog)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg) if self.page else None
        self.page.update() if self.page else None

    def _start_countdown(self, end_time_str: str):
        if self.countdown_thread and self.countdown_thread.is_alive():
            return

        def countdown_logic():
            end_time = datetime.datetime.fromisoformat(end_time_str)
            while not self.countdown_stop_event.wait(1):
                now = datetime.datetime.now(end_time.tzinfo)
                remaining = end_time - now
                if remaining.total_seconds() <= 0:
                    self.timer_text.value = "00:00"
                    self.update()
                    break
                minutes, seconds = divmod(int(remaining.total_seconds()), 60)
                self.timer_text.value = f"{minutes:02d}:{seconds:02d}"
                self.update()

        self.countdown_stop_event.clear()
        self.countdown_thread = threading.Thread(target=countdown_logic, daemon=True)
        self.countdown_thread.start()

# ---------------------------------------------------------------------------- #
# 3. Application Entry Point
# ---------------------------------------------------------------------------- #
def main(page: ft.Page):
    """Initializes and runs the Flet application."""
    page.title = get_string("app_title")
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.DARK
    print(resource_path("icon.ico"))
    page.window.icon = resource_path("icon.ico")

    app = GameClientControl(page)
    page.add(app)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    ft.app(target=main)