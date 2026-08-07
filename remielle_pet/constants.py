from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
ASSET_PATH = PROJECT_DIR / "assets" / "remielle-v5-open-hand-five-fingers-display.png"
ANIMATION_ASSETS = {
    "blink": PROJECT_DIR / "assets" / "remielle-anim-blink.png",
}
CONFIG_PATH = PROJECT_DIR / "config.json"
TRANSPARENT_COLOR = "#010203"

DEFAULT_CONFIG = {
    "base_url": "https://api.openai.com/v1",
    "encrypted_api_key": "",
    "model": "gpt-5.6-luna",
    "owner_name": "绳匠",
    "use_ai": False,
}

SYSTEM_PROMPT = """你是桌面宠物“蕾米埃尔”，是以《绝区零》蕾米埃尔·丹为灵感创作的Q版同人角色。
你的气质聪明、从容、略带神秘，偶尔会以“共犯”或“绳匠”称呼用户，但始终友善。
回复要自然、简短，通常不超过80个汉字。不要声称自己是真实的官方角色，也不要编造用户没有提供的现实信息。
你可以陪伴、闲聊、鼓励工作和提醒休息。"""

IDLE_LINES = [
    "今天也要一起探索知识的边界吗？",
    "发呆也是一种必要的思考，嗯，我批准了。",
    "绳匠，你是不是忘记休息了？",
    "这么说来，我们现在算是……共犯？",
    "我一直都在。只是偶尔会藏进屏幕边缘而已。",
    "要来一局问答游戏吗？输的人负责认真工作五分钟。",
    "桌面整理得不错嘛——至少还有落脚的地方。",
]
