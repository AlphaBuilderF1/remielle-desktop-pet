from __future__ import annotations

import json
import re
import threading
import uuid
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

from .constants import MEMORY_PATH


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class MemoryStore:
    """在本机保存可检查、可删除的用户记忆与最近对话。"""

    def __init__(self, path: Path | None = None, max_memories: int = 80, max_turns: int = 24):
        self.path = path or MEMORY_PATH
        self.max_memories = max_memories
        self.max_turns = max_turns
        self._lock = threading.RLock()
        self.data = self._load()

    @staticmethod
    def _empty() -> dict:
        now = _now()
        return {
            "version": 1,
            "memories": [],
            "recent_conversations": [],
            "relationship": {
                "first_met": now,
                "last_seen": now,
                "interaction_count": 0,
            },
        }

    def _load(self) -> dict:
        data = self._empty()
        if not self.path.exists():
            return data
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return data
        if not isinstance(loaded, dict):
            return data
        memories = loaded.get("memories")
        recent = loaded.get("recent_conversations")
        relationship = loaded.get("relationship")
        if isinstance(memories, list):
            data["memories"] = [item for item in memories if isinstance(item, dict)][-self.max_memories :]
        if isinstance(recent, list):
            data["recent_conversations"] = [item for item in recent if isinstance(item, dict)][-self.max_turns :]
        if isinstance(relationship, dict):
            data["relationship"].update(relationship)
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    @staticmethod
    def _compact(text: str, limit: int = 120) -> str:
        return re.sub(r"\s+", " ", text).strip()[:limit]

    @classmethod
    def _clean(cls, text: str, limit: int = 120) -> str:
        return cls._compact(text, limit).strip(" ，,。.!！?？:：;；\"'“”")

    def memories(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self.data["memories"]]

    def remember(self, text: str, category: str = "用户信息", source: str = "manual") -> bool:
        cleaned = self._clean(text)
        if len(cleaned) < 2:
            return False
        normalized = cleaned.casefold()
        with self._lock:
            snapshot = deepcopy(self.data)
            try:
                for item in self.data["memories"]:
                    if str(item.get("text", "")).casefold() == normalized:
                        item["updated_at"] = _now()
                        self._save()
                        return False
                now = _now()
                self.data["memories"].append(
                    {
                        "id": uuid.uuid4().hex,
                        "text": cleaned,
                        "category": category,
                        "source": source,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                self.data["memories"] = self.data["memories"][-self.max_memories :]
                self._save()
            except OSError:
                self.data = snapshot
                raise
        return True

    def forget(self, memory_id: str) -> bool:
        with self._lock:
            snapshot = deepcopy(self.data)
            before = len(self.data["memories"])
            self.data["memories"] = [item for item in self.data["memories"] if item.get("id") != memory_id]
            changed = len(self.data["memories"]) != before
            if changed:
                try:
                    self._save()
                except OSError:
                    self.data = snapshot
                    raise
            return changed

    def clear(self) -> None:
        with self._lock:
            snapshot = self.data
            self.data = self._empty()
            try:
                self._save()
            except OSError:
                self.data = snapshot
                raise

    def record_turn(self, user_message: str, assistant_message: str) -> list[str]:
        inferred = self.extract_explicit_memories(user_message)
        stored: list[str] = []
        with self._lock:
            snapshot = deepcopy(self.data)
            try:
                for text, category in inferred:
                    if self._remember_without_save(text, category, "conversation"):
                        stored.append(text)
                self.data["recent_conversations"].append(
                    {
                        "at": _now(),
                        "user": self._compact(user_message, 500),
                        "assistant": self._compact(assistant_message, 500),
                    }
                )
                self.data["recent_conversations"] = self.data["recent_conversations"][-self.max_turns :]
                relation = self.data["relationship"]
                relation["last_seen"] = _now()
                relation["interaction_count"] = int(relation.get("interaction_count", 0)) + 1
                self._save()
            except OSError:
                self.data = snapshot
                raise
        return stored

    def _remember_without_save(self, text: str, category: str, source: str) -> bool:
        cleaned = self._clean(text)
        if len(cleaned) < 2:
            return False
        normalized = cleaned.casefold()
        for item in self.data["memories"]:
            if str(item.get("text", "")).casefold() == normalized:
                item["updated_at"] = _now()
                return False
        now = _now()
        self.data["memories"].append(
            {
                "id": uuid.uuid4().hex,
                "text": cleaned,
                "category": category,
                "source": source,
                "created_at": now,
                "updated_at": now,
            }
        )
        self.data["memories"] = self.data["memories"][-self.max_memories :]
        return True

    @classmethod
    def extract_explicit_memories(cls, message: str) -> list[tuple[str, str]]:
        """只记录用户明确表达的稳定信息，避免猜测和过度收集。"""
        raw = cls._compact(message, 300)
        if not raw or raw.endswith(("?", "？")):
            return []
        text = cls._clean(raw, 300)
        patterns = (
            (r"^(?:请)?记住[：:,， ]*(.{2,100})$", "明确记忆", lambda value: value),
            (r"^我叫(.{1,24})$", "称呼", lambda value: f"用户叫{value}"),
            (r"^你可以叫我(.{1,24})$", "称呼", lambda value: f"用户希望被称为{value}"),
            (r"^我(?:喜欢|偏爱|很爱)(.{1,80})$", "偏好", lambda value: f"用户喜欢{value}"),
            (r"^我(?:不喜欢|讨厌)(.{1,80})$", "偏好", lambda value: f"用户不喜欢{value}"),
            (r"^我的(生日|职业|工作|爱好|目标)是(.{1,80})$", "个人资料", lambda value: f"用户的{value}"),
        )
        results: list[tuple[str, str]] = []
        for pattern, category, formatter in patterns:
            match = re.match(pattern, text)
            if not match:
                continue
            if len(match.groups()) == 1:
                value = cls._clean(match.group(1))
            else:
                value = f"{cls._clean(match.group(1))}是{cls._clean(match.group(2))}"
            memory = cls._clean(formatter(value))
            if memory:
                results.append((memory, category))
            break
        return results

    def recent_messages(self, limit: int = 8) -> list[dict]:
        with self._lock:
            turns = self.data["recent_conversations"][-max(0, limit // 2) :]
            messages: list[dict] = []
            for turn in turns:
                user = str(turn.get("user", "")).strip()
                assistant = str(turn.get("assistant", "")).strip()
                if user:
                    messages.append({"role": "user", "content": user})
                if assistant:
                    messages.append({"role": "assistant", "content": assistant})
            return messages[-limit:]

    def relationship(self) -> dict:
        with self._lock:
            relation = dict(self.data["relationship"])
        try:
            first_day = datetime.fromisoformat(str(relation["first_met"])).date()
        except (KeyError, TypeError, ValueError):
            first_day = date.today()
        relation["days_together"] = max(1, (date.today() - first_day).days + 1)
        count = int(relation.get("interaction_count", 0))
        relation["stage"] = "初次相识" if count < 5 else "逐渐熟悉" if count < 25 else "默契共犯"
        return relation

    def prompt_context(self) -> str:
        relation = self.relationship()
        with self._lock:
            memories = [str(item.get("text", "")).strip() for item in self.data["memories"][-16:]]
        lines = [
            "【关系状态】",
            f"你们已相识第{relation['days_together']}天，完成过{relation.get('interaction_count', 0)}轮对话，关系阶段：{relation['stage']}。",
        ]
        if memories:
            lines.append("【用户明确允许保留的记忆】")
            lines.extend(f"- {item}" for item in memories if item)
        else:
            lines.extend(("【用户记忆】", "暂无长期记忆。"))
        return "\n".join(lines)
