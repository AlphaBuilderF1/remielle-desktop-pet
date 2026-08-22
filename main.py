"""蕾米埃尔桌面宠物启动入口。"""

import json
import sys
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox

from remielle_pet.ai import AIClient, offline_reply
from remielle_pet.app import DesktopPet
from remielle_pet.config import load_config, save_config
from remielle_pet.constants import (
    ANIMATION_ASSETS,
    APP_VERSION,
    ASSET_PATH,
    CONFIG_PATH,
    DATA_DIR,
    DEFAULT_CONFIG,
    MEMORY_PATH,
)
from remielle_pet.memory import MemoryStore
from remielle_pet.security import protect_api_key, unprotect_api_key

__all__ = [
    "AIClient",
    "ANIMATION_ASSETS",
    "APP_VERSION",
    "ASSET_PATH",
    "CONFIG_PATH",
    "DEFAULT_CONFIG",
    "MEMORY_PATH",
    "MemoryStore",
    "DesktopPet",
    "load_config",
    "offline_reply",
    "protect_api_key",
    "save_config",
    "unprotect_api_key",
]


def self_test() -> None:
    assert ASSET_PATH.exists(), "missing character asset"
    assert all(path.exists() for path in ANIMATION_ASSETS.values()), "missing animation asset"
    config = load_config()
    assert all(key in config for key in DEFAULT_CONFIG)
    assert offline_reply("你好", "测试者")
    assert DesktopPet.parse_speech_batch('["第一句", "第二句"]') == ["第一句", "第二句"]
    with tempfile.TemporaryDirectory() as temp_dir:
        memory = MemoryStore(Path(temp_dir) / "memory.json")
        remembered = memory.record_turn("我喜欢咖啡", "记住了。")
        assert remembered == ["用户喜欢咖啡"]
        assert memory.recent_messages()[-1]["content"] == "记住了。"
        assert "用户喜欢咖啡" in memory.prompt_context()
        assert memory.record_turn("你喜欢咖啡吗？", "当然。") == []
        assert memory.record_turn("我喜欢咖啡吗？", "你说呢？") == []
        memory.record_turn("今天压力很大", "先休息一下吧。")
        assert memory.emotion()["key"] == "concerned"
        assert memory.relationship()["stage"] == "逐渐熟悉"
        test_config = dict(DEFAULT_CONFIG)
        test_config["custom_personality"] = "说话更俏皮一些"
        prompt = AIClient(test_config, memory).system_prompt()
        assert "神秘共犯" in prompt and "用户喜欢咖啡" in prompt and "说话更俏皮一些" in prompt
        assert "当前情绪反馈" in prompt and "关心" in prompt
        assert "本轮即时反馈" in AIClient(test_config, memory).system_prompt("我今天好难过")
        memory.data["emotion"]["updated_at"] = (datetime.now().astimezone() - timedelta(hours=7)).isoformat()
        assert memory.emotion()["key"] == "calm"

        legacy_path = Path(temp_dir) / "legacy-memory.json"
        legacy_path.write_text(
            json.dumps({"version": 1, "relationship": {"interaction_count": 6}}),
            encoding="utf-8",
        )
        migrated = MemoryStore(legacy_path)
        assert migrated.relationship()["affinity"] == 12
        assert migrated.emotion()["key"] == "calm"
    print("Self-test passed")


def report_startup_error(exc: BaseException) -> None:
    """让无控制台的便携版也能给出可排查的启动错误。"""
    log_path = DATA_DIR / "启动错误.log"
    try:
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        detail = f"错误记录已保存到：\n{log_path}"
    except OSError:
        detail = "同时无法写入错误记录，请将程序解压到有写入权限的目录。"
    try:
        messagebox.showerror("蕾米埃尔桌宠启动失败", f"程序未能正常启动。\n\n{exc}\n\n{detail}")
    except Exception:
        pass


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        try:
            DesktopPet().run()
        except Exception as error:
            report_startup_error(error)
            raise SystemExit(1) from error
