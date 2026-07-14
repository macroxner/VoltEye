import discord
from discord.ext import commands

from config import COMMAND_PREFIX
from utils.embeds import error_embed, stats_embed
from utils.helpers import (
    clean_albion_timestamp,
    start_of_today_utc_iso,
    start_of_week_utc_iso,
    get_event_id,
    get_weapon_from_event,
    get_killer_name,
    get_victim_name,
    calculate_longest_killstreak,
)


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def sync_player_events(self, linked, stats: dict):
        for event in stats["recent_kills_api"]:
            await self.bot.db.save_event(
                discord_id=linked["discord_id"],
                albion_player_id=linked["albion_player_id"],
                albion_player_name=linked["albion_player_name"],
                event_id=get_event_id(event),
                event_type="kill",
                event_time=clean_albion_timestamp(event.get("TimeStamp")),
                fame=event.get("TotalVictimKillFame", 0),
                weapon=get_weapon_from_event(event),
                killer_name=get_killer_name(event),
                victim_name=get_victim_name(event),
            )

        for event in stats["recent_deaths_api"]:
            await self.bot.db.save_event(
                discord_id=linked["discord_id"],
                albion_player_id=linked["albion_player_id"],
                albion_player_name=linked["albion_player_name"],
                event_id=get_event_id(event),
                event_type="death",
                event_time=clean_albion_timestamp(event.get("TimeStamp")),
                fame=event.get("TotalVictimKillFame", 0),
                weapon=get_weapon_from_event(event),
                killer_name=get_killer_name(event),
                victim_name=get_victim_name(event),
            )

    @commands.command(name="stats")
    async def stats(self, ctx, member: discord.Member | None = None):
        target = member or ctx.author

        linked = await self.bot.db.get_player_by_discord_id(target.id)

        if not linked:
            if target == ctx.author:
                message = f"No tienes cuenta enlazada. Usa `{COMMAND_PREFIX}link NombreAlbion`."
            else:
                message = f"{target.mention} no tiene cuenta enlazada."

            await ctx.reply(embed=error_embed(message), mention_author=False)
            return

        async with ctx.typing():
            try:
                player_stats = await self.bot.albion.get_basic_stats(linked["albion_player_id"])
                await self.sync_player_events(linked, player_stats)
            except Exception as error:
                print(error)
                await ctx.reply(
                    embed=error_embed("No he podido obtener las stats desde la API de Albion."),
                    mention_author=False
                )
                return

        counts = await self.bot.db.get_event_counts(target.id)

        total_kills = counts["total_kills"] or 0
        total_deaths = counts["total_deaths"] or 0

        favorite_weapon = await self.bot.db.get_favorite_weapon(target.id)
        top_killer = await self.bot.db.get_top_killer(target.id)
        top_victim = await self.bot.db.get_top_victim(target.id)
        ordered_events = await self.bot.db.get_events_ordered(target.id)

        counters = {
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "kills_today": await self.bot.db.get_kills_since(target.id, start_of_today_utc_iso()),
            "deaths_today": await self.bot.db.get_deaths_since(target.id, start_of_today_utc_iso()),
            "kills_week": await self.bot.db.get_kills_since(target.id, start_of_week_utc_iso()),
            "favorite_weapon": (
                f"{favorite_weapon['weapon']} x{favorite_weapon['total']}"
                if favorite_weapon else "Sin datos"
            ),
            "top_killer": (
                f"{top_killer['killer_name']} x{top_killer['total']}"
                if top_killer else "Sin datos"
            ),
            "top_victim": (
                f"{top_victim['victim_name']} x{top_victim['total']}"
                if top_victim else "Sin datos"
            ),
            "favorite_weapon": (
                f"{favorite_weapon['weapon']} x{favorite_weapon['total']}"
                if favorite_weapon else "Sin datos"
            ),
            "top_killer": (
                f"{top_killer['killer_name']} x{top_killer['total']}"
                if top_killer else "Sin datos"
            ),
            "top_victim": (
                f"{top_victim['victim_name']} x{top_victim['total']}"
                if top_victim else "Sin datos"
            ),
            "longest_killstreak": calculate_longest_killstreak(ordered_events),
        }

        await ctx.reply(
            embed=stats_embed(target, player_stats, counters),
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(StatsCog(bot))