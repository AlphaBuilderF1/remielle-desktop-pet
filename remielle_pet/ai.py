from __future__ import annotations

import json
import os
import random
import urllib.error
import urllib.request

from .constants import SYSTEM_PROMPT
from .security import unprotect_api_key


def offline_reply(message: str, owner_name: str) -> str:
    text = message.strip()
    if not text:
        return "我听着呢。"
    if any(word in text for word in ("你好", "嗨", "早上好", "晚上好")):
        return f"你好呀，{owner_name}。今天也请多关照。"
    if any(word in text for word in ("累", "困", "疲惫", "不想干")):
        return "那就休息五分钟吧。真正聪明的人，知道什么时候该保存体力。"
    if any(word in text for word in ("工作", "学习", "写代码", "加油")):
        return "我会在这里监督你。先专心二十五分钟，回来再向我汇报成果吧。"
    if any(word in text for word in ("喜欢", "可爱", "漂亮")):
        return "眼光不错嘛。这个答案，我就先记在心里了♪"
    if "吃什么" in text:
        return random.choice([
            "今天适合吃热乎乎的面。",
            "要不来份咖喱？思考会消耗能量的。",
            "交给命运：去吃你看到的第三家店。",
        ])
    if any(word in text for word in ("再见", "晚安", "睡觉")):
        return "晚安。等你下次唤醒屏幕时，我还会在这里。"
    return random.choice([
        "很有意思。再多说一点，我想听听你的想法。",
        "这个问题值得认真想想——不过，我也想先听你的答案。",
        "嗯，我记住了。我们又多了一条共同的秘密。",
        "问答游戏还没结束哦。你愿意给我一点线索吗？",
    ])


class AIClient:
    def __init__(self, config: dict):
        self.config = config
        try:
            self.session_key = unprotect_api_key(str(config.get("encrypted_api_key", "")))
        except OSError:
            self.session_key = ""

    def get_api_key(self) -> str:
        return self.session_key or os.environ.get("PET_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

    def mode_label(self) -> str:
        if not self.config.get("use_ai"):
            return "离线陪伴模式"
        model = str(self.config.get("model", "")).strip() or "未填写模型"
        if not self.get_api_key():
            return f"AI · {model}（缺少密钥）"
        return f"AI · {model}"

    def is_ready(self) -> bool:
        return bool(
            self.config.get("use_ai")
            and self.get_api_key()
            and str(self.config.get("base_url", "")).strip()
            and str(self.config.get("model", "")).strip()
        )

    def reply(self, messages: list[dict]) -> str:
        key = self.get_api_key()
        if not self.config.get("use_ai") or not key:
            return offline_reply(messages[-1]["content"], self.config.get("owner_name", "绳匠"))

        base_url = str(self.config.get("base_url", "")).rstrip("/")
        model = str(self.config.get("model", "")).strip()
        if not base_url or not model:
            raise ValueError("请先在设置中填写接口地址和模型名称。")

        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages[-12:]],
                "temperature": 0.85,
                "max_completion_tokens": 180,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"接口返回 {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"无法连接 AI 接口：{exc.reason}") from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError("接口返回了无法识别的内容。") from exc
