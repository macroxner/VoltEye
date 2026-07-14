import aiosqlite
from pathlib import Path


class Database:
    def __init__(self):
        self.db_path = Path("data/volteye.db")

    async def init(self):
        self.db_path.parent.mkdir(exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS linked_players (
                    discord_id INTEGER PRIMARY KEY,
                    discord_name TEXT NOT NULL,
                    albion_player_id TEXT NOT NULL,
                    albion_player_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS player_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER NOT NULL,
                    albion_player_id TEXT NOT NULL,
                    albion_player_name TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    fame INTEGER DEFAULT 0,
                    weapon TEXT,
                    killer_name TEXT,
                    victim_name TEXT,
                    UNIQUE(albion_player_id, event_id, event_type)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS posted_events (
                    post_key TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS battle_reports (
                    battle_id TEXT PRIMARY KEY,
                    battle_url TEXT NOT NULL,
                    battle_time TEXT NOT NULL,
                    submitted_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS battle_attendance (
                    battle_id TEXT NOT NULL,
                    discord_id INTEGER NOT NULL,
                    albion_player_id TEXT NOT NULL,
                    albion_player_name TEXT NOT NULL,
                    attended INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (battle_id, discord_id),
                    FOREIGN KEY (battle_id)
                        REFERENCES battle_reports(battle_id)
                        ON DELETE CASCADE
                )
            """)

            await self._ensure_column(db, "player_events", "weapon", "TEXT")
            await self._ensure_column(db, "player_events", "killer_name", "TEXT")
            await self._ensure_column(db, "player_events", "victim_name", "TEXT")

            await db.commit()

    async def _ensure_column(self, db, table: str, column: str, column_type: str):
        cursor = await db.execute(f"PRAGMA table_info({table})")
        columns = await cursor.fetchall()

        existing = [col[1] for col in columns]

        if column not in existing:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    async def link_player(self, discord_id, discord_name, player_id, player_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO linked_players (
                    discord_id,
                    discord_name,
                    albion_player_id,
                    albion_player_name
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    discord_name = excluded.discord_name,
                    albion_player_id = excluded.albion_player_id,
                    albion_player_name = excluded.albion_player_name
            """, (discord_id, discord_name, player_id, player_name))

            await db.commit()

    async def unlink_player(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM linked_players WHERE discord_id = ?", (discord_id,))
            await db.commit()

    async def get_player_by_discord_id(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM linked_players WHERE discord_id = ?",
                (discord_id,)
            )
            return await cursor.fetchone()

    async def get_all_linked_players(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT *
                FROM linked_players
                ORDER BY albion_player_name ASC
            """)
            return await cursor.fetchall()

    async def save_event(
        self,
        discord_id,
        albion_player_id,
        albion_player_name,
        event_id,
        event_type,
        event_time,
        fame=0,
        weapon=None,
        killer_name=None,
        victim_name=None
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO player_events (
                    discord_id,
                    albion_player_id,
                    albion_player_name,
                    event_id,
                    event_type,
                    event_time,
                    fame,
                    weapon,
                    killer_name,
                    victim_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                discord_id,
                albion_player_id,
                albion_player_name,
                str(event_id),
                event_type,
                event_time,
                fame,
                weapon,
                killer_name,
                victim_name
            ))

            await db.commit()

    async def get_event_counts(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT
                    SUM(CASE WHEN event_type = 'kill' THEN 1 ELSE 0 END) AS total_kills,
                    SUM(CASE WHEN event_type = 'death' THEN 1 ELSE 0 END) AS total_deaths
                FROM player_events
                WHERE discord_id = ?
            """, (discord_id,))
            return await cursor.fetchone()

    async def get_kills_since(self, discord_id, since_iso):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT COUNT(*)
                FROM player_events
                WHERE discord_id = ?
                AND event_type = 'kill'
                AND event_time >= ?
            """, (discord_id, since_iso))
            row = await cursor.fetchone()
            return row[0] or 0

    async def get_deaths_since(self, discord_id, since_iso):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT COUNT(*)
                FROM player_events
                WHERE discord_id = ?
                AND event_type = 'death'
                AND event_time >= ?
            """, (discord_id, since_iso))
            row = await cursor.fetchone()
            return row[0] or 0

    async def get_daily_mvp(self, since_iso):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT discord_id, albion_player_name, COUNT(*) AS kills_today
                FROM player_events
                WHERE event_type = 'kill'
                AND event_time >= ?
                GROUP BY discord_id, albion_player_name
                ORDER BY kills_today DESC
                LIMIT 1
            """, (since_iso,))
            return await cursor.fetchone()

    async def get_favorite_weapon(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT weapon, COUNT(*) AS total
                FROM player_events
                WHERE discord_id = ?
                AND event_type = 'kill'
                AND weapon IS NOT NULL
                AND weapon != ''
                GROUP BY weapon
                ORDER BY total DESC
                LIMIT 1
            """, (discord_id,))
            return await cursor.fetchone()

    async def get_top_victim(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT victim_name, COUNT(*) AS total
                FROM player_events
                WHERE discord_id = ?
                AND event_type = 'kill'
                AND victim_name IS NOT NULL
                AND victim_name != ''
                GROUP BY victim_name
                ORDER BY total DESC
                LIMIT 1
            """, (discord_id,))
            return await cursor.fetchone()

    async def get_top_killer(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT killer_name, COUNT(*) AS total
                FROM player_events
                WHERE discord_id = ?
                AND event_type = 'death'
                AND killer_name IS NOT NULL
                AND killer_name != ''
                GROUP BY killer_name
                ORDER BY total DESC
                LIMIT 1
            """, (discord_id,))
            return await cursor.fetchone()

    async def get_events_ordered(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT event_type, event_time
                FROM player_events
                WHERE discord_id = ?
                ORDER BY event_time ASC
            """, (discord_id,))
            return await cursor.fetchall()

    async def get_daily_history(self, discord_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT
                    substr(event_time, 1, 10) AS day,
                    SUM(CASE WHEN event_type = 'kill' THEN 1 ELSE 0 END) AS kills,
                    SUM(CASE WHEN event_type = 'death' THEN 1 ELSE 0 END) AS deaths
                FROM player_events
                WHERE discord_id = ?
                GROUP BY day
                ORDER BY day ASC
            """, (discord_id,))
            return await cursor.fetchall()

    async def has_posted(self, post_key: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM posted_events WHERE post_key = ?",
                (post_key,)
            )
            return await cursor.fetchone() is not None


    async def mark_posted(self, post_key: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO posted_events (post_key) VALUES (?)",
                (post_key,)
            )
            await db.commit()

    async def battle_exists(self, battle_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM battle_reports WHERE battle_id = ?",
                (battle_id,)
            )
            return await cursor.fetchone() is not None


    async def save_battle_report(
        self,
        battle_id: str,
        battle_url: str,
        battle_time: str,
        submitted_by: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO battle_reports (
                    battle_id,
                    battle_url,
                    battle_time,
                    submitted_by
                )
                VALUES (?, ?, ?, ?)
            """, (
                battle_id,
                battle_url,
                battle_time,
                submitted_by
            ))

            await db.commit()


    async def save_battle_attendance(
        self,
        battle_id: str,
        discord_id: int,
        albion_player_id: str,
        albion_player_name: str,
        attended: bool
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO battle_attendance (
                    battle_id,
                    discord_id,
                    albion_player_id,
                    albion_player_name,
                    attended
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(battle_id, discord_id) DO UPDATE SET
                    albion_player_id = excluded.albion_player_id,
                    albion_player_name = excluded.albion_player_name,
                    attended = excluded.attended
            """, (
                battle_id,
                discord_id,
                albion_player_id,
                albion_player_name,
                1 if attended else 0
            ))

            await db.commit()


    async def get_battle_attendance(self, battle_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("""
                SELECT *
                FROM battle_attendance
                WHERE battle_id = ?
                ORDER BY attended DESC, albion_player_name COLLATE NOCASE ASC
            """, (battle_id,))

            return await cursor.fetchall()


    async def get_user_attendance_stats(self, discord_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("""
                SELECT
                    COUNT(*) AS total_battles,
                    SUM(CASE WHEN ba.attended = 1 THEN 1 ELSE 0 END)
                        AS attended_battles,
                    MAX(
                        CASE
                            WHEN ba.attended = 1 THEN br.battle_time
                            ELSE NULL
                        END
                    ) AS last_attendance
                FROM battle_attendance ba
                INNER JOIN battle_reports br
                    ON br.battle_id = ba.battle_id
                WHERE ba.discord_id = ?
            """, (discord_id,))

            return await cursor.fetchone()


    async def get_inactive_players(self, cutoff_iso: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("""
                SELECT
                    lp.discord_id,
                    lp.albion_player_id,
                    lp.albion_player_name,
                    COUNT(ba.battle_id) AS tracked_battles,
                    SUM(
                        CASE
                            WHEN ba.attended = 1 THEN 1
                            ELSE 0
                        END
                    ) AS attended_battles,
                    MAX(
                        CASE
                            WHEN ba.attended = 1 THEN br.battle_time
                            ELSE NULL
                        END
                    ) AS last_attendance
                FROM linked_players lp
                LEFT JOIN battle_attendance ba
                    ON ba.discord_id = lp.discord_id
                LEFT JOIN battle_reports br
                    ON br.battle_id = ba.battle_id
                GROUP BY
                    lp.discord_id,
                    lp.albion_player_id,
                    lp.albion_player_name
                HAVING
                    last_attendance IS NULL
                    OR last_attendance < ?
                ORDER BY
                    last_attendance IS NOT NULL,
                    last_attendance ASC,
                    lp.albion_player_name COLLATE NOCASE ASC
            """, (cutoff_iso,))

            return await cursor.fetchall()


    async def get_recent_battle_reports(self, limit: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("""
                SELECT
                    br.*,
                    SUM(
                        CASE
                            WHEN ba.attended = 1 THEN 1
                            ELSE 0
                        END
                    ) AS attendees,
                    COUNT(ba.discord_id) AS registered_players
                FROM battle_reports br
                LEFT JOIN battle_attendance ba
                    ON ba.battle_id = br.battle_id
                GROUP BY br.battle_id
                ORDER BY br.battle_time DESC
                LIMIT ?
            """, (limit,))

            return await cursor.fetchall()