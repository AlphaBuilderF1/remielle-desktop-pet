from __future__ import annotations

import json
import re
import threading
import uuid
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

from .constants import MEMORY_PATH


EMOTION_PROFILES = {
    "calm": {
        "label": "平静",
        "symbol": "✦",
        "color": "#c9a8df",
        "guidance": "语气从容自然，保持轻松陪伴，不刻意强调情绪。",
    },
    "happy": {
        "label": "开心",
        "symbol": "♪",
        "color": "#e49ac2",
        "guidance": "语气比平时更轻快俏皮，可以分享用户的喜悦，但不要过度兴奋。",
    },
    "concerned": {
        "label": "关心",
        "symbol": "♡",
        "color": "#79aecd",
        "guidance": "先倾听和关心用户，避免说教、轻率诊断或连续追问。",
    },
    "focused": {
        "label": "专注",
        "symbol": "✓",
        "color": "#8f82bd",
        "guidance": "语气清晰可靠，适合给出一个短小、可执行的下一步。",
    },
    "tired": {
        "label": "倦意",
        "symbol": "☾",
        "color": "#9ca4c7",
        "guidance": "语气放轻，减少信息密度，适度提醒休息但不强迫用户。",
    },
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
            "version": 2,
            "memories": [],
            "recent_conversations": [],
            "relationship": {
                "first_met": now,
                "last_seen": now,
                "interaction_count": 0,
                "affinity": 0,
            },
            "emotion": {
                "mood": "calm",
                "intensity": 0.25,
                "updated_at": now,
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
        emotion = loaded.get("emotion")
        if isinstance(memories, list):
            data["memories"] = [item for item in memories if isinstance(item, dict)][-self.max_memories :]
        if isinstance(recent, list):
            data["recent_conversations"] = [item for item in recent if isinstance(item, dict)][-self.max_turns :]
        relationship_data = relationship if isinstance(relationship, dict) else {}
        if relationship_data:
            data["relationship"].update(relationship_data)
        if "affinity" not in relationship_data:
            count = _as_int(data["relationship"].get("interaction_count", 0))
            data["relationship"]["affinity"] = min(100, count * 2)
        if isinstance(emotion, dict):
            data["emotion"].update(emotion)
        if data["emotion"].get("mood") not in EMOTION_PROFILES:
            data["emotion"]["mood"] = "calm"
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
                relation["interaction_count"] = _as_int(relation.get("interaction_count", 0)) + 1
                mood, intensity, affinity_bonus = self.detect_emotion(user_message)
                relation["affinity"] = min(
                    100,
                    _as_int(relation.get("affinity", 0)) + 1 + affinity_bonus,
                )
                self.data["emotion"] = {
                    "mood": mood,
                    "intensity": intensity,
                    "updated_at": _now(),
                }
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

    @classmethod
    def detect_emotion(cls, message: str) -> tuple[str, float, int]:
        """根据用户当下表达选择角色反馈状态，不推断医学或心理结论。"""
        text = cls._compact(message, 300).casefold()
        if any(word in text for word in ("难过", "伤心", "焦虑", "压力", "不开心", "痛苦", "生病", "不舒服", "崩溃")):
            return "concerned", 0.9, 2
        if any(word in text for word in ("困", "好累", "累了", "晚安", "睡觉", "熬夜", "没睡")):
            return "tired", 0.82, 1
        if any(word in text for word in ("工作", "学习", "写代码", "考试", "计划", "目标", "专注", "完成任务")):
            return "focused", 0.78, 1
        if any(word in text for word in ("开心", "高兴", "喜欢", "谢谢", "感谢", "可爱", "漂亮", "厉害", "太棒", "爱你", "你好")):
            return "happy", 0.82, 2
        return "calm", 0.35, 0

    @classmethod
    def emotion_for_message(cls, message: str) -> dict:
        mood, intensity, _affinity_bonus = cls.detect_emotion(message)
        result = dict(EMOTION_PROFILES[mood])
        result.update({"key": mood, "intensity": intensity})
        return result

    def emotion(self, now: datetime | None = None) -> dict:
        """返回随时间自然衰减后的情绪表现，不频繁写入磁盘。"""
        with self._lock:
            stored = dict(self.data.get("emotion", {}))
        mood = str(stored.get("mood", "calm"))
        if mood not in EMOTION_PROFILES:
            mood = "calm"
        try:
            updated_at = datetime.fromisoformat(str(stored.get("updated_at", "")))
            current = now or datetime.now().astimezone()
            if updated_at.tzinfo is None:
                updated_at = updated_at.astimezone()
            if current.tzinfo is None:
                current = current.astimezone()
            elapsed_hours = max(0.0, (current - updated_at).total_seconds() / 3600)
        except (TypeError, ValueError):
            elapsed_hours = 0.0
        try:
            stored_intensity = float(stored.get("intensity", 0.25))
        except (TypeError, ValueError):
            stored_intensity = 0.25
        intensity = min(1.0, max(0.2, stored_intensity - elapsed_hours * 0.14))
        if elapsed_hours >= 6 or (mood != "calm" and intensity < 0.32):
            mood = "calm"
            intensity = 0.25
        result = dict(EMOTION_PROFILES[mood])
        result.update({"key": mood, "intensity": round(intensity, 2)})
        return result

    def relationship(self) -> dict:
        with self._lock:
            relation = dict(self.data["relationship"])
        try:
            first_day = datetime.fromisoformat(str(relation["first_met"])).date()
        except (KeyError, TypeError, ValueError):
            first_day = date.today()
        relation["days_together"] = max(1, (date.today() - first_day).days + 1)
        count = max(0, _as_int(relation.get("interaction_count", 0)))
        affinity = min(100, max(0, _as_int(relation.get("affinity", 0)), count * 2))
        relation["affinity"] = affinity
        if affinity < 5:
            relation["stage"] = "初次相识"
        elif affinity < 20:
            relation["stage"] = "逐渐熟悉"
        elif affinity < 50:
            relation["stage"] = "亲密伙伴"
        else:
            relation["stage"] = "默契共犯"
        return relation

    def prompt_context(self) -> str:
        relation = self.relationship()
        emotion = self.emotion()
        with self._lock:
            memories = [str(item.get("text", "")).strip() for item in self.data["memories"][-16:]]
        lines = [
            "【关系状态】",
            f"你们已相识第{relation['days_together']}天，完成过{relation.get('interaction_count', 0)}轮对话，关系阶段：{relation['stage']}。",
            "关系阶段只影响熟悉程度，不得以冷落、内疚或依赖感要求用户继续互动。",
            "【当前情绪反馈】",
            f"当前表现为“{emotion['label']}”：{emotion['guidance']}",
        ]
        if memories:
            lines.append("【用户明确允许保留的记忆】")
            lines.extend(f"- {item}" for item in memories if item)
        else:
            lines.extend(("【用户记忆】", "暂无长期记忆。"))
        return "\n".join(lines)
