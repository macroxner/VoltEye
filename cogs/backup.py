import json
import discord
import aiosqlite

from discord.ext import commands


class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="backuplinks")
    @commands.has_permissions(administrator=True)
    async def backuplinks(self, ctx):

        async with aiosqlite.connect(
            self.bot.db.db_path
        ) as db:

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

        players = [
            dict(row)
            for row in rows
        ]

        filename = "linked_players_backup.json"

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                players,
                file,
                ensure_ascii=False,
                indent=4
            )

        await ctx.reply(
            content=(
                f"✅ Backup creado con "
                f"**{len(players)} usuarios enlazados**."
            ),
            file=discord.File(filename),
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(BackupCog(bot))