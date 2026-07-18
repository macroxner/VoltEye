import discord
from discord.ext import commands

from config import COMMAND_PREFIX
from utils.embeds import error_embed, stats_embed
from utils.helpers import (
    start_of_today_utc_iso,
    start_of_week_utc_iso,
    calculate_longest_killstreak,
)


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stats")
    async def stats(
        self,
        ctx,
        member: discord.Member | None = None
    ):
        target = member or ctx.author

        # ==========================================================
        # IMPORTANTE:
        # !stats NO consulta kills, deaths ni historial de Albion.
        #
        # Todo lo mostrado aquí sale EXCLUSIVAMENTE de la base
        # de datos de VoltEye, que debe ser rellenada únicamente
        # mediante !battles <URL>.
        # ==========================================================

        linked = await self.bot.db.get_player_by_discord_id(
            target.id
        )

        if not linked:
            if target == ctx.author:
                message = (
                    "No tienes cuenta enlazada. "
                    f"Usa `{COMMAND_PREFIX}link NombreAlbion`."
                )
            else:
                message = (
                    f"{target.mention} no tiene cuenta enlazada."
                )

            await ctx.reply(
                embed=error_embed(message),
                mention_author=False
            )
            return

        # ----------------------------------------------------------
        # NO LLAMAMOS A:
        #
        # self.bot.albion.get_basic_stats(...)
        # self.bot.albion.get_player_kills(...)
        # self.bot.albion.get_player_deaths(...)
        # self.bot.albion.get_player_info(...)
        #
        # Así es imposible que !stats importe eventos externos.
        # ----------------------------------------------------------

        player_stats = {
            "id": linked["albion_player_id"],
            "name": linked["albion_player_name"],

            # No necesitamos consultar Albion para estos datos.
            # Los dejamos neutrales.
            "guild": "No registrado",
            "alliance": "No registrado",

            # IMPORTANTE:
            # No usamos la fama global de Albion porque incluiría
            # contenido ajeno a las battleboards procesadas.
            "kill_fame": 0,
            "death_fame": 0,
        }

        # ==========================================================
        # TODO A PARTIR DE AQUÍ SALE DE player_events
        # ==========================================================

        counts = await self.bot.db.get_event_counts(
            target.id
        )

        total_kills = 0
        total_deaths = 0

        if counts:
            total_kills = counts["total_kills"] or 0
            total_deaths = counts["total_deaths"] or 0

        favorite_weapon = (
            await self.bot.db.get_favorite_weapon(
                target.id
            )
        )

        top_killer = (
            await self.bot.db.get_top_killer(
                target.id
            )
        )

        top_victim = (
            await self.bot.db.get_top_victim(
                target.id
            )
        )

        ordered_events = (
            await self.bot.db.get_events_ordered(
                target.id
            )
        )

        kills_today = (
            await self.bot.db.get_kills_since(
                target.id,
                start_of_today_utc_iso()
            )
        )

        deaths_today = (
            await self.bot.db.get_deaths_since(
                target.id,
                start_of_today_utc_iso()
            )
        )

        kills_week = (
            await self.bot.db.get_kills_since(
                target.id,
                start_of_week_utc_iso()
            )
        )

        counters = {
            "total_kills": total_kills,
            "total_deaths": total_deaths,

            "kills_today": kills_today,
            "deaths_today": deaths_today,
            "kills_week": kills_week,

            "favorite_weapon": (
                f"{favorite_weapon['weapon']} "
                f"x{favorite_weapon['total']}"
                if favorite_weapon
                else "Sin datos"
            ),

            "top_killer": (
                f"{top_killer['killer_name']} "
                f"x{top_killer['total']}"
                if top_killer
                else "Sin datos"
            ),

            "top_victim": (
                f"{top_victim['victim_name']} "
                f"x{top_victim['total']}"
                if top_victim
                else "Sin datos"
            ),

            "longest_killstreak": (
                calculate_longest_killstreak(
                    ordered_events
                )
                if ordered_events
                else 0
            ),
        }

        await ctx.reply(
            embed=stats_embed(
                target,
                player_stats,
                counters
            ),
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(StatsCog(bot))