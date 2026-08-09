from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from .ai import offline_reply

if TYPE_CHECKING:
    from .app import DesktopPet


class ChatWindow:
    def __init__(self, app: DesktopPet):
        self.app = app
        self.window: tk.Toplevel | None = None
        self.history: list[dict] = (
            app.memory.recent_messages(limit=8) if app.config.get("memory_enabled", True) else []
        )
        self.result_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.input_box: tk.Entry | None = None
        self.transcript: tk.Text | None = None
        self.send_button: ttk.Button | None = None
        self.status_label: tk.Label | None = None

    def show(self) -> None:
        if self.window and self.window.winfo_exists():
            self.refresh_status()
            self.window.deiconify()
            self.window.lift()
            if self.input_box:
                self.input_box.focus_set()
            return

        window = tk.Toplevel(self.app.root)
        self.window = window
        window.title("与蕾米埃尔聊天")
        window.geometry("440x560")
        window.minsize(380, 460)
        window.configure(bg="#191622")
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        window.bind("<Escape>", lambda _event: window.withdraw())

        style = ttk.Style(window)
        style.theme_use("clam")
        style.configure("Pet.TButton", background="#ae83d8", foreground="white", borderwidth=0, padding=9)
        style.map("Pet.TButton", background=[("active", "#c39be7")])

        header = tk.Frame(window, bg="#252033", padx=16, pady=13)
        header.pack(fill="x")
        identity = tk.Frame(header, bg="#252033")
        identity.pack(side="left", fill="x", expand=True)
        tk.Label(
            identity,
            text="✦ 蕾米埃尔",
            bg="#252033",
            fg="#f7d9ff",
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(anchor="w")
        self.status_label = tk.Label(identity, bg="#252033", fg="#a99db8", font=("Microsoft YaHei UI", 8))
        self.status_label.pack(anchor="w", pady=(2, 0))
        self.refresh_status()
        tk.Button(
            header,
            text="设置",
            command=self.app.open_settings,
            bg="#3a314d",
            fg="#eee7f8",
            activebackground="#514267",
            activeforeground="white",
            relief="flat",
            padx=12,
        ).pack(side="right")

        input_row = tk.Frame(window, bg="#252033", padx=12, pady=12)
        input_row.pack(side="bottom", fill="x")
        self.input_box = tk.Entry(
            input_row,
            bg="#352e43",
            fg="white",
            insertbackground="white",
            relief="flat",
            font=("Microsoft YaHei UI", 10),
        )
        self.input_box.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 8))
        self.input_box.bind("<Return>", self.send)
        self.send_button = ttk.Button(input_row, text="发送", style="Pet.TButton", command=self.send)
        self.send_button.pack(side="right")

        self.transcript = tk.Text(
            window,
            bg="#191622",
            fg="#eeeaf4",
            insertbackground="white",
            relief="flat",
            padx=16,
            pady=16,
            wrap="word",
            font=("Microsoft YaHei UI", 10),
            state="disabled",
        )
        self.transcript.pack(side="top", fill="both", expand=True)
        self.transcript.tag_configure(
            "name_pet", foreground="#e4b7ff", font=("Microsoft YaHei UI", 10, "bold"), spacing1=8
        )
        self.transcript.tag_configure(
            "name_user", foreground="#99d7ff", font=("Microsoft YaHei UI", 10, "bold"), spacing1=8
        )
        self.transcript.tag_configure("body", foreground="#eeeaf4", lmargin1=8, lmargin2=8, spacing3=8)

        self._append("蕾米埃尔", "终于来找我了。想聊些什么？", "pet")
        self.input_box.focus_set()
        window.after(120, self._poll_result)

    def refresh_status(self) -> None:
        if self.status_label and self.status_label.winfo_exists():
            self.status_label.configure(text=self.app.ai.mode_label())

    def _append(self, name: str, text: str, who: str) -> None:
        if not self.transcript:
            return
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{name}\n", "name_pet" if who == "pet" else "name_user")
        self.transcript.insert("end", f"{text}\n", "body")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def send(self, _event=None) -> str:
        if not self.input_box or not self.send_button:
            return "break"
        message = self.input_box.get().strip()
        if not message:
            return "break"
        self.input_box.delete(0, "end")
        if message == "/记忆":
            self.app.open_memory_personality()
            return "break"
        if message.startswith("/记住 "):
            if not self.app.config.get("memory_enabled", True):
                self._append("蕾米埃尔", "记忆功能现在是关闭的，可以先在“记忆与性格”中开启。", "pet")
                return "break"
            content = message.removeprefix("/记住 ").strip()
            try:
                stored = self.app.memory.remember(content, category="明确记忆")
            except OSError as exc:
                self._append("系统", f"记忆保存失败：{exc}", "pet")
                return "break"
            self._append("蕾米埃尔", "记住了。" if stored else "这件事我已经记得了。", "pet")
            return "break"
        self._append(self.app.config.get("owner_name", "你"), message, "user")
        self.history.append({"role": "user", "content": message})
        self.send_button.configure(state="disabled", text="思考中…")
        threading.Thread(target=self._request_reply, daemon=True).start()
        return "break"

    def _request_reply(self) -> None:
        try:
            answer = self.app.ai.reply(self.history)
            self.result_queue.put(("ok", answer))
        except Exception as exc:
            self.result_queue.put(("error", str(exc)))

    def _poll_result(self) -> None:
        if not self.window or not self.window.winfo_exists():
            return
        try:
            status, result = self.result_queue.get_nowait()
        except queue.Empty:
            self.window.after(120, self._poll_result)
            return

        if status == "ok":
            self.history.append({"role": "assistant", "content": result})
            self._append("蕾米埃尔", result, "pet")
            self.app.show_bubble(result, 6500)
            self._remember_turn(result)
        else:
            self._append("系统", f"{result}\n本条消息已改用离线回复，你的 AI 设置没有被自动修改。", "pet")
            fallback = offline_reply(self.history[-1]["content"], self.app.config.get("owner_name", "绳匠"))
            self.history.append({"role": "assistant", "content": fallback})
            self._append("蕾米埃尔", fallback, "pet")
            self._remember_turn(fallback)
        if self.send_button:
            self.send_button.configure(state="normal", text="发送")
        if self.input_box:
            self.input_box.focus_set()
        self.window.after(120, self._poll_result)

    def _remember_turn(self, answer: str) -> None:
        if not self.app.config.get("memory_enabled", True) or len(self.history) < 2:
            return
        user_message = str(self.history[-2].get("content", ""))
        try:
            self.app.memory.record_turn(user_message, answer)
        except OSError:
            self._append("系统", "本轮对话正常完成，但记忆文件暂时无法写入。", "pet")

    def reset_context(self) -> None:
        self.history.clear()
