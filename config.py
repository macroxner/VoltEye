import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
ALBION_SERVER = os.getenv("ALBION_SERVER", "europe").lower()
BOMB_NAME = os.getenv("BOMB_NAME", "Voltage")
BOT_NAME = os.getenv("BOT_NAME", "VoltEye")

if not DISCORD_TOKEN:
    raise RuntimeError("Falta DISCORD_TOKEN en el archivo .env")

ALBION_API_ROOTS = {
    "americas": "https://gameinfo.albiononline.com/api/gameinfo",
    "europe": "https://gameinfo-ams.albiononline.com/api/gameinfo",
    "asia": "https://gameinfo-sgp.albiononline.com/api/gameinfo",
}

ALBION_API_BASE = ALBION_API_ROOTS.get(ALBION_SERVER)

if not ALBION_API_BASE:
    raise RuntimeError("ALBION_SERVER inválido. Usa: americas, europe o asia.")

KILL_FEED_CHANNEL_ID = int(os.getenv("KILL_FEED_CHANNEL_ID", "0"))
BATTLEBOARD_CHANNEL_ID = int(os.getenv("BATTLEBOARD_CHANNEL_ID", "0"))
ALLIANCE_NAME = os.getenv("ALLIANCE_NAME", "").lower()
ALLIANCE_TAG = os.getenv("ALLIANCE_TAG", "").lower()
BATTLEBOARD_MIN_FAME = int(os.getenv("BATTLEBOARD_MIN_FAME", "5000000"))
FEED_INTERVAL_SECONDS = int(os.getenv("FEED_INTERVAL_SECONDS", "120"))