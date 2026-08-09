from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from .config import save_config
from .constants import PERSONALITY_PRESETS

if TYPE_CHECKING:
    from .app import DesktopPet


class MemoryPersonalityWindow:
    def __init__(self, app: DesktopPet):
        self.app = app
        self.window: tk.Toplevel | None = None
        self.memory_ids: list[str] = []
        self.memory_list: tk.Listbox | None = None
        self.relation_label: tk.Label | None = None

    def show(self) -> None:
        if self.window and self.window.winfo_exists():
            self.refresh_memories()
            self.window.deiconify()
            self.window.lift()
            return

        window = tk.Toplevel(self.app.root)
        self.window = window
        window.title("蕾米埃尔 · 记忆与性格")
        window.geometry("620x680")
        window.minsize(540, 600)
        window.configure(bg="#f8f3fb")
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", self.close)

        footer = tk.Frame(window, bg="#eee5f3", padx=20, pady=14)
        footer.pack(side="bottom", fill="x")
        body = tk.Frame(window, bg="#f8f3fb", padx=24, pady=20)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(8, weight=1)

        tk.Label(
            body,
            text="记忆与性格",
            bg="#f8f3fb",
            fg="#4a3658",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            body,
            text="长期记忆只保存在本机，可随时查看和删除。",
            bg="#f8f3fb",
            fg="#786982",
        ).grid(row=1, column=0, sticky="w", pady=(3, 12))

        enabled = tk.BooleanVar(value=bool(self.app.config.get("memory_enabled", True)))
        style_name = tk.StringVar(value=str(self.app.config.get("personality_style", "神秘共犯")))

        personality = tk.LabelFrame(
            body,
            text=" 性格 ",
            bg="#f8f3fb",
            fg="#5d4769",
            padx=12,
            pady=10,
        )
        personality.grid(row=2, column=0, sticky="ew")
        personality.columnconfigure(1, weight=1)
        tk.Label(personality, text="风格", bg="#f8f3fb", fg="#4a3658").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            personality,
            textvariable=style_name,
            values=list(PERSONALITY_PRESETS),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0))
        tk.Label(personality, text="自定义补充", bg="#f8f3fb", fg="#4a3658").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 4)
        )
        custom = tk.Text(
            personality,
            height=3,
            wrap="word",
            relief="solid",
            bd=1,
            font=("Microsoft YaHei UI", 9),
        )
        custom.grid(row=2, column=0, columnspan=2, sticky="ew")
        custom.insert("1.0", str(self.app.config.get("custom_personality", "")))
        tk.Checkbutton(
            personality,
            text="启用跨重启记忆",
            variable=enabled,
            bg="#f8f3fb",
            activebackground="#f8f3fb",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.relation_label = tk.Label(
            body,
            bg="#eee5f3",
            fg="#624c70",
            anchor="w",
            justify="left",
            wraplength=540,
            padx=12,
            pady=8,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.relation_label.grid(row=3, column=0, sticky="ew", pady=(12, 8))

        tk.Label(body, text="长期记忆", bg="#f8f3fb", fg="#4a3658").grid(row=4, column=0, sticky="w")
        add_row = tk.Frame(body, bg="#f8f3fb")
        add_row.grid(row=5, column=0, sticky="ew", pady=(5, 7))
        add_row.columnconfigure(0, weight=1)
        memory_entry = tk.Entry(add_row, relief="solid", bd=1, font=("Microsoft YaHei UI", 9))
        memory_entry.grid(row=0, column=0, sticky="ew", ipady=6)

        def add_memory() -> None:
            value = memory_entry.get().strip()
            if not value:
                return
            try:
                stored = self.app.memory.remember(value, category="手动添加")
            except OSError as exc:
                messagebox.showerror("保存失败", f"无法写入记忆：\n{exc}", parent=window)
                return
            if stored:
                memory_entry.delete(0, "end")
                self.refresh_memories()
                self.app.reset_speech_cache()

        ttk.Button(add_row, text="添加", command=add_memory).grid(row=0, column=1, padx=(8, 0))
        memory_entry.bind("<Return>", lambda _event: add_memory())

        list_frame = tk.Frame(body, bg="#f8f3fb")
        list_frame.grid(row=8, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.memory_list = tk.Listbox(
            list_frame,
            activestyle="none",
            selectbackground="#b58bd1",
            relief="solid",
            bd=1,
            font=("Microsoft YaHei UI", 9),
        )
        self.memory_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.memory_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.memory_list.configure(yscrollcommand=scrollbar.set)

        actions = tk.Frame(body, bg="#f8f3fb")
        actions.grid(row=9, column=0, sticky="ew", pady=(8, 0))

        def delete_selected() -> None:
            if not self.memory_list:
                return
            selected = self.memory_list.curselection()
            if not selected:
                return
            if selected[0] >= len(self.memory_ids):
                return
            memory_id = self.memory_ids[selected[0]]
            try:
                forgotten = self.app.memory.forget(memory_id)
            except OSError as exc:
                messagebox.showerror("删除失败", f"无法更新记忆文件：\n{exc}", parent=window)
                return
            if forgotten:
                self.refresh_memories()
                self.app.reset_speech_cache()

        def clear_all() -> None:
            if not messagebox.askyesno(
                "清空记忆",
                "确定清空长期记忆和最近对话吗？此操作无法撤销。",
                parent=window,
            ):
                return
            try:
                self.app.memory.clear()
            except OSError as exc:
                messagebox.showerror("清空失败", f"无法更新记忆文件：\n{exc}", parent=window)
                return
            self.app.chat.reset_context()
            self.refresh_memories()
            self.app.reset_speech_cache()

        ttk.Button(actions, text="删除选中", command=delete_selected).pack(side="left")
        ttk.Button(actions, text="清空全部", command=clear_all).pack(side="left", padx=(8, 0))
        tk.Label(
            actions,
            text="聊天中输入“/记住 内容”也可直接添加",
            bg="#f8f3fb",
            fg="#8a7a92",
            font=("Microsoft YaHei UI", 8),
        ).pack(side="right")

        def save() -> None:
            new_config = dict(self.app.config)
            new_config["memory_enabled"] = bool(enabled.get())
            new_config["personality_style"] = style_name.get()
            new_config["custom_personality"] = custom.get("1.0", "end").strip()[:300]
            try:
                save_config(new_config)
            except OSError as exc:
                messagebox.showerror("保存失败", f"无法保存设置：\n{exc}", parent=window)
                return
            self.app.config.clear()
            self.app.config.update(new_config)
            if self.app.config["memory_enabled"] and not self.app.chat.history:
                self.app.chat.history.extend(self.app.memory.recent_messages(limit=8))
            self.app.reset_speech_cache()
            self.app.show_bubble("性格与记忆设置已经生效。")
            self.close()

        ttk.Button(footer, text="取消", command=self.close).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="保存", command=save).pack(side="right")
        self.refresh_memories()

    def refresh_memories(self) -> None:
        memories = self.app.memory.memories()
        self.memory_ids = [str(item.get("id", "")) for item in memories]
        if self.memory_list and self.memory_list.winfo_exists():
            self.memory_list.delete(0, "end")
            for item in memories:
                category = str(item.get("category", "记忆"))
                self.memory_list.insert("end", f"[{category}] {item.get('text', '')}")
            if not memories:
                self.memory_list.insert("end", "还没有长期记忆。")
        if self.relation_label and self.relation_label.winfo_exists():
            relation = self.app.memory.relationship()
            emotion = self.app.memory.emotion()
            self.relation_label.configure(
                text=(
                    f"{emotion['symbol']} {emotion['label']} · 关系：{relation['stage']} · "
                    f"相识第 {relation['days_together']} 天 · {relation.get('interaction_count', 0)} 轮对话 · "
                    f"{len(memories)} 条长期记忆"
                )
            )

    def close(self) -> None:
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
