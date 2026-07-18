import asyncio
import json
import aiosqlite

DB_PATH = "data/volteye.db"
OUTPUT_PATH = "linked_players_backup.json"


async def main():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT
                discord_id,
                discord_name,
                albion_player_id,
                albion_player_name,
                created_at
            FROM linked_players
            ORDER BY albion_player_name
        """)

        rows = await cursor.fetchall()

    data = [dict(row) for row in rows]

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(
        f"✅ Backup completado: "
        f"{len(data)} usuarios guardados en {OUTPUT_PATH}"
    )


asyncio.run(main())