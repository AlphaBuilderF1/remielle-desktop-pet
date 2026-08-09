"""蕾米埃尔桌面宠物启动入口。"""

import sys
import tempfile
from pathlib import Path

from remielle_pet.ai import AIClient, offline_reply
from remielle_pet.app import DesktopPet
from remielle_pet.config import load_config, save_config
from remielle_pet.constants import ANIMATION_ASSETS, ASSET_PATH, CONFIG_PATH, DEFAULT_CONFIG, MEMORY_PATH
from remielle_pet.memory import MemoryStore
from remielle_pet.security import protect_api_key, unprotect_api_key

__all__ = [
    "AIClient",
    "ANIMATION_ASSETS",
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
        test_config = dict(DEFAULT_CONFIG)
        test_config["custom_personality"] = "说话更俏皮一些"
        prompt = AIClient(test_config, memory).system_prompt()
        assert "神秘共犯" in prompt and "用户喜欢咖啡" in prompt and "说话更俏皮一些" in prompt
    print("Self-test passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        DesktopPet().run()
