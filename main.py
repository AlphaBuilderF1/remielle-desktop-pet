"""蕾米埃尔桌面宠物启动入口。"""

import sys

from remielle_pet.ai import AIClient, offline_reply
from remielle_pet.app import DesktopPet
from remielle_pet.config import load_config, save_config
from remielle_pet.constants import ANIMATION_ASSETS, ASSET_PATH, CONFIG_PATH, DEFAULT_CONFIG
from remielle_pet.security import protect_api_key, unprotect_api_key

__all__ = [
    "AIClient",
    "ANIMATION_ASSETS",
    "ASSET_PATH",
    "CONFIG_PATH",
    "DEFAULT_CONFIG",
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
    print("Self-test passed")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        DesktopPet().run()
