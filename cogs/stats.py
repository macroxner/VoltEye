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

        # Solo obtenemos información básica del personaje.
        # No descargamos ni guardamos sus kills o muertes recientes.
        try:
            player_info = await self.bot.albion.get_player_info(
                linked["albion_player_id"]
            )
        except Exception as error:
            print(
                "Error obteniendo información del jugador: "
                f"{type(error).__name__}: {error}"
            )

            # Aunque falle Albion, podemos seguir mostrando las
            # estadísticas guardadas desde las battleboards.
            player_info = {
                "Id": linked["albion_player_id"],
                "Name": linked["albion_player_name"],
                "GuildName": None,
                "AllianceName": None,
                "LifetimeStatistics": {},
            }

        lifetime = player_info.get("LifetimeStatistics") or {}
        pvp = lifetime.get("PvP") or {}

        # Este diccionario mantiene el formato que espera stats_embed,
        # pero las kills y muertes no se importan desde Albion.
        player_stats = {
            "id": player_info.get("Id"),
            "name": (
                player_info.get("Name")
                or linked["albion_player_name"]
            ),
            "guild": (
                player_info.get("GuildName")
                or "Sin guild"
            ),
            "alliance": (
                player_info.get("AllianceName")
                or "Sin alianza"
            ),

            # Estas dos cifras son fama global de Albion.
            # No son el número de kills o muertes del bot.
            "kill_fame": pvp.get("KillFame", 0),
            "death_fame": pvp.get("DeathFame", 0),

            # Se dejan vacías para impedir cualquier sincronización
            # accidental del historial reciente.
            "recent_kills_api": [],
            "recent_deaths_api": [],
        }

        counts = await self.bot.db.get_event_counts(target.id)

        total_kills = counts["total_kills"] or 0
        total_deaths = counts["total_deaths"] or 0

        favorite_weapon = await self.bot.db.get_favorite_weapon(
            target.id
        )
        top_killer = await self.bot.db.get_top_killer(
            target.id
        )
        top_victim = await self.bot.db.get_top_victim(
            target.id
        )
        ordered_events = await self.bot.db.get_events_ordered(
            target.id
        )

        counters = {
            "total_kills": total_kills,
            "total_deaths": total_deaths,

            "kills_today": await self.bot.db.get_kills_since(
                target.id,
                start_of_today_utc_iso()
            ),

            "deaths_today": await self.bot.db.get_deaths_since(
                target.id,
                start_of_today_utc_iso()
            ),

            "kills_week": await self.bot.db.get_kills_since(
                target.id,
                start_of_week_utc_iso()
            ),

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