from __future__ import annotations

import json
import math
import queue
import random
import sys
import threading
import time
import tkinter as tk
from collections import deque

from .ai import AIClient
from .chat import ChatWindow
from .config import load_config
from .constants import ANIMATION_ASSETS, ASSET_PATH, EMOTIONAL_IDLE_LINES, IDLE_LINES, TRANSPARENT_COLOR
from .memory import MemoryStore
from .memory_ui import MemoryPersonalityWindow
from .settings import SettingsWindow


ACTION_DURATIONS = {
    "sway": 1.8,
    "hop": 0.9,
    "click_bounce": 0.72,
    "blink": 0.36,
}
IDLE_ACTIONS = ("sway", "hop")


class DesktopPet:
    def __init__(self):
        if not ASSET_PATH.exists():
            raise FileNotFoundError(f"找不到角色素材：{ASSET_PATH}")

        self.config = load_config()
        self.memory = MemoryStore()
        self.ai = AIClient(self.config, self.memory)
        self.root = tk.Tk()
        self.root.title("蕾米埃尔桌宠")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        if sys.platform == "win32":
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.width = 440
        self.height = 540
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{self.width}x{self.height}+{screen_w - self.width - 22}+{screen_h - self.height - 70}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # 素材已按桌面显示尺寸预渲染；二值透明边缘可避免 Windows 色键窗口产生黑边。
        missing_frames = [path for path in ANIMATION_ASSETS.values() if not path.exists()]
        if missing_frames:
            raise FileNotFoundError(f"找不到动作素材：{missing_frames[0]}")
        self.pet_frames = {
            "base": tk.PhotoImage(file=str(ASSET_PATH)),
            **{name: tk.PhotoImage(file=str(path)) for name, path in ANIMATION_ASSETS.items()},
        }
        self.pet_image = self.pet_frames["base"]
        self.current_frame_name = "base"
        self.pet_item = self.canvas.create_image(self.width // 2, 325, image=self.pet_image, anchor="center")

        self.bubble_bg = self.canvas.create_rectangle(
            32, 18, self.width - 32, 116, fill="#fffafd", outline="#c9a8df", width=2, state="hidden"
        )
        self.bubble_text = self.canvas.create_text(
            self.width // 2,
            67,
            width=self.width - 100,
            text="",
            fill="#4b3857",
            font=("Microsoft YaHei UI", 10),
            justify="center",
            state="hidden",
        )
        self.emotion_badge = self.canvas.create_text(
            51,
            31,
            text="✦",
            fill="#a977c7",
            font=("Segoe UI Symbol", 12, "bold"),
            state="hidden",
        )
        self.bubble_after: str | None = None
        self.drag_start = (0, 0)
        self.drag_origin = (0, 0)
        self.was_dragged = False
        self.is_dragging = False
        self.animation_start = time.monotonic()
        self.active_action: str | None = None
        self.action_started = 0.0
        self.next_idle_action = self._next_idle_action_time()
        self.next_blink = self._next_blink_time()
        self.speech_cache: deque[str] = deque(maxlen=8)
        self.speech_queue: queue.Queue[tuple[int, str, object]] = queue.Queue()
        self.speech_prefetching = False
        self.speech_waiting_for_click = False
        self.speech_generation = 0
        self.click_after: str | None = None
        self.double_clicking = False

        self.chat = ChatWindow(self)
        self.settings = SettingsWindow(self)
        self.memory_personality = MemoryPersonalityWindow(self)
        self._bind_events()
        self._build_menu()

        self.root.after(30, self._animate)
        owner_name = str(self.config.get("owner_name", "绳匠"))
        relation = self.memory.relationship()
        emotion = self.memory.emotion()
        if not self.config.get("memory_enabled", True) or not relation.get("interaction_count", 0):
            greeting = f"你好呀，{owner_name}。今后就请多关照了。"
        elif emotion["key"] in ("concerned", "tired"):
            greeting = f"欢迎回来，{owner_name}。今天也不用太勉强自己。"
        elif relation["stage"] == "默契共犯":
            greeting = f"欢迎回来，共犯。我就知道你会再来。"
        else:
            greeting = f"欢迎回来，{owner_name}。我还记得我们的约定。"
        self.root.after(1000, lambda: self.show_bubble(greeting, 6000))
        self.root.after(1600, self.prefetch_speech)
        self.root.after(150000, self._idle_talk)

    def _bind_events(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Double-Button-1>", self._open_chat_from_double_click)
        self.canvas.bind("<Button-3>", self._show_menu)

    def _build_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="和她聊天", command=self.chat.show)
        self.menu.add_command(label="记忆与性格", command=self.open_memory_personality)
        self.menu.add_command(label="设置 AI", command=self.open_settings)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.root.destroy)

    def _start_drag(self, event) -> None:
        self.is_dragging = True
        self.active_action = None
        self.drag_start = (event.x_root, event.y_root)
        self.drag_origin = (self.root.winfo_x(), self.root.winfo_y())
        self.was_dragged = False

    def _drag(self, event) -> None:
        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]
        if abs(dx) + abs(dy) > 4:
            self.was_dragged = True
        self.root.geometry(f"+{self.drag_origin[0] + dx}+{self.drag_origin[1] + dy}")

    def _end_drag(self, _event) -> None:
        self.is_dragging = False
        if self.double_clicking:
            self.double_clicking = False
            return
        if self.was_dragged:
            self.next_idle_action = self._next_idle_action_time()
            return
        if self.click_after:
            self.root.after_cancel(self.click_after)
        self.click_after = self.root.after(260, self._single_click)

    def _single_click(self) -> None:
        self.click_after = None
        self.play_action("click_bounce", interrupt=True)
        self.speak()

    def _open_chat_from_double_click(self, _event) -> None:
        self.double_clicking = True
        if self.click_after:
            self.root.after_cancel(self.click_after)
            self.click_after = None
        self.chat.show()

    def _show_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _animate(self) -> None:
        now = time.monotonic()
        elapsed = now - self.animation_start
        bob = math.sin(elapsed * 2.2) * 3.2
        if not self.is_dragging and not self.active_action:
            if now >= self.next_blink:
                self.play_action("blink")
            elif now >= self.next_idle_action:
                self.play_action(random.choice(IDLE_ACTIONS))

        offset_x = 0.0
        offset_y = 0.0
        if self.active_action:
            action = self.active_action
            duration = ACTION_DURATIONS[action]
            progress = min(1.0, (now - self.action_started) / duration)
            offset_x, offset_y = self.action_offset(action, progress)
            frame_name = self.action_frame(action, progress)
            self._set_pet_frame(frame_name)
            if progress >= 1.0:
                self.active_action = None
                self.next_idle_action = self._next_idle_action_time(now)
                if action == "blink" or now >= self.next_blink:
                    self.next_blink = self._next_blink_time(now)
        else:
            self._set_pet_frame("base")

        self.canvas.coords(self.pet_item, self.width // 2 + offset_x, 325 + bob + offset_y)
        self.root.after(30, self._animate)

    def _set_pet_frame(self, frame_name: str) -> None:
        if frame_name == self.current_frame_name:
            return
        self.current_frame_name = frame_name
        self.canvas.itemconfigure(self.pet_item, image=self.pet_frames[frame_name])

    @staticmethod
    def _next_idle_action_time(now: float | None = None) -> float:
        return (now if now is not None else time.monotonic()) + random.uniform(15.0, 40.0)

    @staticmethod
    def _next_blink_time(now: float | None = None) -> float:
        return (now if now is not None else time.monotonic()) + random.uniform(5.0, 10.0)

    @staticmethod
    def action_frame(action: str, progress: float) -> str:
        progress = max(0.0, min(1.0, progress))
        if action == "blink":
            return "blink" if 0.28 <= progress < 0.64 else "base"
        return "base"

    @staticmethod
    def action_offset(action: str, progress: float) -> tuple[float, float]:
        """返回动作在当前进度下相对于基础浮动的位置偏移。"""
        progress = max(0.0, min(1.0, progress))
        if action == "sway":
            envelope = math.sin(math.pi * progress)
            return math.sin(math.tau * progress) * 9.0 * envelope, math.sin(math.pi * progress) * 1.2
        if action == "hop":
            lift = -(math.sin(math.pi * progress) ** 0.85) * 21.0
            landing = math.sin(math.pi * ((progress - 0.78) / 0.22)) * 2.5 if progress >= 0.78 else 0.0
            return math.sin(math.tau * progress) * 1.5, lift + landing
        if action == "click_bounce":
            damping = 1.0 - progress
            return math.sin(math.tau * progress) * damping * 2.0, -abs(math.sin(math.pi * 2.2 * progress)) * damping * 14.0
        return 0.0, 0.0

    def play_action(self, action: str, interrupt: bool = False) -> None:
        if action not in ACTION_DURATIONS or self.is_dragging:
            return
        if self.active_action and not interrupt:
            return
        self.active_action = action
        self.action_started = time.monotonic()

    def show_bubble(self, text: str, duration: int = 4800) -> None:
        short = text.strip()
        if len(short) > 90:
            short = short[:87] + "…"
        emotion = self.memory.emotion()
        self.canvas.itemconfigure(self.bubble_text, text=short, state="normal")
        self.canvas.itemconfigure(self.bubble_bg, outline=emotion["color"], state="normal")
        self.canvas.itemconfigure(
            self.emotion_badge,
            text=emotion["symbol"],
            fill=emotion["color"],
            state="normal",
        )
        self.canvas.tag_raise(self.bubble_bg)
        self.canvas.tag_raise(self.emotion_badge)
        self.canvas.tag_raise(self.bubble_text)
        if self.bubble_after:
            self.root.after_cancel(self.bubble_after)
        self.bubble_after = self.root.after(duration, self.hide_bubble)

    def hide_bubble(self) -> None:
        self.canvas.itemconfigure(self.bubble_text, state="hidden")
        self.canvas.itemconfigure(self.bubble_bg, state="hidden")
        self.canvas.itemconfigure(self.emotion_badge, state="hidden")
        self.bubble_after = None

    def _idle_talk(self) -> None:
        self.speak()
        self.root.after(random.randint(180000, 360000), self._idle_talk)

    def speak(self) -> None:
        if not self.ai.is_ready():
            emotion_key = str(self.memory.emotion().get("key", "calm"))
            lines = EMOTIONAL_IDLE_LINES.get(emotion_key, IDLE_LINES)
            self.show_bubble(random.choice(lines), 5500)
            return
        if self.speech_cache:
            self.show_bubble(self.speech_cache.popleft(), 6500)
            if len(self.speech_cache) < 2:
                self.prefetch_speech()
            return

        self.speech_waiting_for_click = True
        self.show_bubble("稍等，让我想想……", 2500)
        self.prefetch_speech(show_when_ready=True)

    @staticmethod
    def parse_speech_batch(answer: str) -> list[str]:
        text = answer.strip()
        candidates: list[str] = []
        json_text = text
        if text.startswith("```"):
            json_text = text.replace("```json", "", 1).replace("```", "").strip()
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, list):
                candidates = [str(item) for item in parsed]
        except json.JSONDecodeError:
            start, end = text.find("["), text.rfind("]")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                    if isinstance(parsed, list):
                        candidates = [str(item) for item in parsed]
                except json.JSONDecodeError:
                    pass
        if not candidates:
            candidates = text.splitlines()

        cleaned: list[str] = []
        for candidate in candidates:
            line = candidate.strip().lstrip("-*• 0123456789.、)）").strip().strip('\"“”')
            if line and line not in cleaned:
                cleaned.append(line[:90])
        return cleaned[:4]

    def reset_speech_cache(self, start_prefetch: bool = True) -> None:
        self.speech_generation += 1
        self.speech_cache.clear()
        self.speech_prefetching = False
        self.speech_waiting_for_click = False
        if start_prefetch and self.ai.is_ready():
            self.root.after(50, self.prefetch_speech)

    def prefetch_speech(self, show_when_ready: bool = False) -> None:
        if not self.ai.is_ready():
            return
        if show_when_ready:
            self.speech_waiting_for_click = True
        if self.speech_prefetching or len(self.speech_cache) >= 4:
            return

        self.speech_prefetching = True
        generation = self.speech_generation
        current_time = time.strftime("%Y-%m-%d %H:%M")

        def worker() -> None:
            try:
                answer = self.ai.reply(
                    [{
                        "role": "user",
                        "content": (
                            f"现在是 {current_time}。请以桌面宠物的身份写4句彼此不同、自然有变化的主动台词，"
                            "可以问候、关心、鼓励或开启轻松话题，每句不超过45个汉字。"
                            "严格只返回一个JSON字符串数组，不要代码块，不要解释。"
                        ),
                    }]
                )
                lines = self.parse_speech_batch(answer)
                if not lines:
                    raise RuntimeError("模型没有返回可用台词。")
                self.speech_queue.put((generation, "ok", lines))
            except Exception as exc:
                self.speech_queue.put((generation, "error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(120, self._poll_speech)

    def _poll_speech(self) -> None:
        try:
            generation, status, result = self.speech_queue.get_nowait()
        except queue.Empty:
            if self.speech_prefetching:
                self.root.after(120, self._poll_speech)
            return
        if generation != self.speech_generation:
            if self.speech_prefetching:
                self.root.after(120, self._poll_speech)
            return

        self.speech_prefetching = False
        if status == "ok":
            for line in result:
                if line not in self.speech_cache:
                    self.speech_cache.append(line)
            if self.speech_waiting_for_click and self.speech_cache:
                self.speech_waiting_for_click = False
                self.show_bubble(self.speech_cache.popleft(), 6500)
        elif self.speech_waiting_for_click:
            self.speech_waiting_for_click = False
            self.show_bubble(random.choice(IDLE_LINES), 5500)

    def open_settings(self) -> None:
        self.settings.show()

    def open_memory_personality(self) -> None:
        self.memory_personality.show()

    def refresh_emotional_feedback(self) -> None:
        self.chat.refresh_status()
        if self.memory_personality.window and self.memory_personality.window.winfo_exists():
            self.memory_personality.refresh_memories()

    def run(self) -> None:
        self.root.mainloop()
