import asyncio
import json
import aiosqlite
from pathlib import Path

DB_PATH = "data/volteye.db"
BACKUP_PATH = "linked_players_backup.json"


async def main():
    if not Path(BACKUP_PATH).exists():
        print("❌ No existe linked_players_backup.json")
        return

    with open(
        BACKUP_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        players = json.load(file)

    Path("data").mkdir(exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS linked_players (
                discord_id INTEGER PRIMARY KEY,
                discord_name TEXT NOT NULL,
                albion_player_id TEXT NOT NULL,
                albion_player_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        restored = 0

        for player in players:
            await db.execute("""
                INSERT INTO linked_players (
                    discord_id,
                    discord_name,
                    albion_player_id,
                    albion_player_name,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)

                ON CONFLICT(discord_id) DO UPDATE SET
                    discord_name = excluded.discord_name,
                    albion_player_id = excluded.albion_player_id,
                    albion_player_name = excluded.albion_player_name
            """, (
                player["discord_id"],
                player["discord_name"],
                player["albion_player_id"],
                player["albion_player_name"],
                player.get("created_at"),
            ))

            restored += 1

        await db.commit()

    print(f"✅ Restaurados {restored} usuarios.")


asyncio.run(main())