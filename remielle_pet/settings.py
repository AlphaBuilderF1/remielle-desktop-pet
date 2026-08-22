from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from .config import save_config
from .security import protect_api_key

if TYPE_CHECKING:
    from .app import DesktopPet


class SettingsWindow:
    def __init__(self, app: DesktopPet):
        self.app = app
        self.window: tk.Toplevel | None = None

    def show(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return

        app = self.app
        window = tk.Toplevel(app.root)
        self.window = window
        window.title("蕾米埃尔 · AI 设置")
        window.geometry("560x640")
        window.minsize(510, 600)
        window.resizable(True, True)
        window.configure(bg="#f8f3fb")
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", self.close)

        footer = tk.Frame(window, bg="#eee5f3", padx=20, pady=14)
        footer.pack(side="bottom", fill="x")

        body = tk.Frame(window, bg="#f8f3fb", padx=26, pady=22)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        tk.Label(
            body,
            text="AI 对话设置",
            bg="#f8f3fb",
            fg="#4a3658",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            body,
            text="设置保存后会立即生效，无需重启桌宠。",
            bg="#f8f3fb",
            fg="#786982",
        ).grid(row=1, column=0, sticky="w", pady=(3, 10))

        current_status = tk.StringVar(value=f"当前：{app.ai.mode_label()}")
        tk.Label(
            body,
            textvariable=current_status,
            bg="#eee5f3",
            fg="#624c70",
            anchor="w",
            padx=12,
            pady=8,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="ew", pady=(0, 12))

        enabled = tk.BooleanVar(value=bool(app.config.get("use_ai")))
        owner = tk.StringVar(value=str(app.config.get("owner_name", "绳匠")))
        base_url = tk.StringVar(value=str(app.config.get("base_url", "")))
        model = tk.StringVar(value=str(app.config.get("model", "")))
        key = tk.StringVar(value=app.ai.session_key)

        tk.Checkbutton(
            body,
            text="启用兼容 AI 接口",
            variable=enabled,
            bg="#f8f3fb",
            activebackground="#f8f3fb",
        ).grid(row=3, column=0, sticky="w", pady=(0, 8))

        def add_entry(parent: tk.Widget, label: str, variable: tk.StringVar, row: int, secret: bool = False) -> int:
            tk.Label(parent, text=label, bg="#f8f3fb", fg="#4a3658").grid(
                row=row, column=0, sticky="w", pady=(5, 3)
            )
            tk.Entry(
                parent,
                textvariable=variable,
                show="●" if secret else "",
                relief="solid",
                bd=1,
                font=("Microsoft YaHei UI", 9),
            ).grid(row=row + 1, column=0, sticky="ew", ipady=7)
            return row + 2

        next_row = 4
        next_row = add_entry(body, "我该怎么称呼你", owner, next_row)
        next_row = add_entry(body, "模型名称", model, next_row)
        next_row = add_entry(body, "接口地址", base_url, next_row)
        next_row = add_entry(body, "API 密钥", key, next_row, secret=True)

        tk.Label(
            body,
            text=(
                "密钥会使用当前 Windows 账户加密保存，不会写入明文。\n"
                "也可以使用环境变量 PET_API_KEY 或 OPENAI_API_KEY。"
            ),
            bg="#f8f3fb",
            fg="#8a7a92",
            font=("Microsoft YaHei UI", 8),
            justify="left",
        ).grid(row=next_row, column=0, sticky="w", pady=(9, 0))
        next_row += 1

        test_status = tk.StringVar(value="")
        tk.Label(
            body,
            textvariable=test_status,
            bg="#f8f3fb",
            fg="#765486",
            anchor="w",
            justify="left",
            wraplength=490,
        ).grid(row=next_row, column=0, sticky="ew", pady=(8, 0))

        def apply_settings(close_window: bool = True, notify: bool = True) -> bool:
            previous_connection = (
                bool(app.config.get("use_ai")),
                str(app.config.get("base_url", "")),
                str(app.config.get("model", "")),
                app.ai.session_key,
            )
            new_config = dict(app.config)
            new_config.update(
                {
                    "use_ai": bool(enabled.get()),
                    "owner_name": owner.get().strip() or "绳匠",
                    "base_url": base_url.get().strip().rstrip("/"),
                    "model": model.get().strip(),
                }
            )
            if new_config["use_ai"] and (not new_config["base_url"] or not new_config["model"]):
                messagebox.showwarning("还缺少信息", "启用 AI 时，请填写接口地址和模型名称。", parent=window)
                return False
            if new_config["use_ai"] and not str(new_config["base_url"]).startswith(("http://", "https://")):
                messagebox.showwarning("接口地址不正确", "接口地址需要以 http:// 或 https:// 开头。", parent=window)
                return False
            try:
                new_config["encrypted_api_key"] = protect_api_key(key.get().strip())
                save_config(new_config)
            except OSError as exc:
                messagebox.showerror("保存失败", f"无法加密或写入设置：\n{exc}", parent=window)
                return False

            app.config.clear()
            app.config.update(new_config)
            app.ai.session_key = key.get().strip()
            current_connection = (
                bool(app.config.get("use_ai")),
                str(app.config.get("base_url", "")),
                str(app.config.get("model", "")),
                app.ai.session_key,
            )
            if current_connection != previous_connection:
                app.reset_speech_cache(start_prefetch=notify)
            elif notify:
                app.prefetch_speech()
            app.chat.refresh_status()
            current_status.set(f"当前：{app.ai.mode_label()}")
            if notify:
                app.show_bubble("设置已经保存，并且立即生效了。")
            if close_window:
                self.close()
            return True

        test_results: queue.Queue[tuple[str, str]] = queue.Queue()

        def finish_test() -> None:
            if not window.winfo_exists():
                return
            try:
                status, detail = test_results.get_nowait()
            except queue.Empty:
                window.after(120, finish_test)
                return
            save_button.configure(state="normal")
            test_button.configure(state="normal")
            if status == "ok":
                test_status.set(f"连接成功 · {app.config.get('model')}\n模型回复：{detail[:100]}")
                app.show_bubble("AI 连接成功。现在可以正常聊天啦。")
                app.prefetch_speech()
            else:
                test_status.set(f"连接失败：{detail}")

        def test_connection() -> None:
            if not apply_settings(close_window=False, notify=False):
                return
            if not app.config.get("use_ai"):
                messagebox.showinfo("尚未启用 AI", "请先勾选“启用兼容 AI 接口”。", parent=window)
                return
            if not app.ai.get_api_key():
                messagebox.showwarning("缺少 API 密钥", "请输入 API 密钥，或先设置相应的环境变量。", parent=window)
                current_status.set(f"当前：{app.ai.mode_label()}")
                return
            test_status.set("正在连接并请求一条简短回复……")
            save_button.configure(state="disabled")
            test_button.configure(state="disabled")

            def worker() -> None:
                try:
                    answer = app.ai.reply([{"role": "user", "content": "这是连接测试，请只用一句简短的话回复。"}])
                    test_results.put(("ok", answer))
                except Exception as exc:
                    test_results.put(("error", str(exc)))

            threading.Thread(target=worker, daemon=True).start()
            window.after(120, finish_test)

        tk.Label(
            footer,
            text="只有点击保存按钮后，修改才会生效。",
            bg="#eee5f3",
            fg="#75677d",
            font=("Microsoft YaHei UI", 8),
        ).pack(side="left")
        ttk.Button(footer, text="取消", command=self.close).pack(side="right", padx=(8, 0))
        save_button = ttk.Button(footer, text="保存设置", command=apply_settings)
        save_button.pack(side="right", padx=(8, 0))
        test_button = ttk.Button(footer, text="保存并测试连接", command=test_connection)
        test_button.pack(side="right")

        window.bind("<Control-s>", lambda _event: apply_settings())

    def close(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
