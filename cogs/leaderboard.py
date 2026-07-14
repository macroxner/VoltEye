from discord.ext import commands

from utils.embeds import linked_players_embed, mvp_embed, error_embed
from utils.helpers import clean_albion_timestamp, start_of_today_utc_iso


class LeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def sync_all_linked_players(self):
        players = await self.bot.db.get_all_linked_players()

        for linked in players:
            try:
                stats = await self.bot.albion.get_basic_stats(linked["albion_player_id"])

                for event in stats["recent_kills_api"]:
                    await self.bot.db.save_event(
                        discord_id=linked["discord_id"],
                        albion_player_id=linked["albion_player_id"],
                        albion_player_name=linked["albion_player_name"],
                        event_id=event.get("EventId"),
                        event_type="kill",
                        event_time=clean_albion_timestamp(event.get("TimeStamp")),
                        fame=event.get("TotalVictimKillFame", 0)
                    )

                for event in stats["recent_deaths_api"]:
                    await self.bot.db.save_event(
                        discord_id=linked["discord_id"],
                        albion_player_id=linked["albion_player_id"],
                        albion_player_name=linked["albion_player_name"],
                        event_id=event.get("EventId"),
                        event_type="death",
                        event_time=clean_albion_timestamp(event.get("TimeStamp")),
                        fame=event.get("TotalVictimKillFame", 0)
                    )

            except Exception as error:
                print(f"Error sincronizando {linked['albion_player_name']}: {error}")

    @commands.command(name="linked")
    async def linked(self, ctx):
        rows = await self.bot.db.get_all_linked_players()

        await ctx.reply(
            embed=linked_players_embed(rows),
            mention_author=False
        )

    @commands.command(name="mvp")
    async def mvp(self, ctx):
        async with ctx.typing():
            try:
                await self.sync_all_linked_players()
            except Exception:
                await ctx.reply(
                    embed=error_embed("No he podido actualizar los datos ahora mismo."),
                    mention_author=False
                )
                return

        row = await self.bot.db.get_daily_mvp(start_of_today_utc_iso())

        await ctx.reply(
            embed=mvp_embed(row),
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(LeaderboardCog(bot))