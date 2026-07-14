import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.embeds import error_embed


BATTLE_URL_PATTERN = re.compile(
    r"^https?://(?:europe\.)?albionbb\.com/battles/(\d+)(?:[/?#].*)?$",
    re.IGNORECASE
)


def parse_battle_id(value: str) -> str | None:
    value = value.strip()

    if value.isdigit():
        return value

    match = BATTLE_URL_PATTERN.match(value)

    if not match:
        return None

    return match.group(1)


def normalize_name(value: str | None) -> str:
    return (value or "").strip().casefold()


def parse_timestamp(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()

    cleaned = value.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(cleaned)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def extract_battle_players(battle: dict) -> tuple[set[str], set[str]]:
    """
    Devuelve:
      - IDs de jugador encontrados
      - nombres normalizados encontrados

    Admite que 'players' venga como diccionario o lista.
    """
    player_ids: set[str] = set()
    player_names: set[str] = set()

    raw_players = (
        battle.get("players")
        or battle.get("Players")
        or []
    )

    if isinstance(raw_players, dict):
        iterable = []

        for key, value in raw_players.items():
            if not isinstance(value, dict):
                continue

            player = dict(value)
            player.setdefault("id", key)
            iterable.append(player)

    elif isinstance(raw_players, list):
        iterable = raw_players

    else:
        iterable = []

    for player in iterable:
        if not isinstance(player, dict):
            continue

        player_id = (
            player.get("id")
            or player.get("Id")
            or player.get("playerId")
            or player.get("PlayerId")
        )

        player_name = (
            player.get("name")
            or player.get("Name")
            or player.get("playerName")
            or player.get("PlayerName")
        )

        if player_id:
            player_ids.add(str(player_id))

        if player_name:
            player_names.add(normalize_name(str(player_name)))

    return player_ids, player_names


def extract_battle_time(battle: dict) -> str:
    timestamp = (
        battle.get("startTime")
        or battle.get("StartTime")
        or battle.get("startTimeUtc")
        or battle.get("StartTimeUtc")
        or battle.get("endTime")
        or battle.get("EndTime")
    )

    return parse_timestamp(timestamp)


def format_date(value: str | None) -> str:
    if not value:
        return "Nunca"

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return discord.utils.format_dt(parsed, style="R")
    except ValueError:
        return value


def chunk_lines(lines: list[str], max_length: int = 1000) -> list[str]:
    chunks = []
    current = ""

    for line in lines:
        candidate = f"{current}\n{line}".strip()

        if len(candidate) > max_length:
            if current:
                chunks.append(current)

            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


class AttendanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="battle")
    @commands.has_permissions(manage_guild=True)
    async def battle(self, ctx, battle_url: str | None = None):
        if not battle_url:
            await ctx.reply(
                embed=error_embed(
                    "Uso: `!battle URL`\n"
                    "Ejemplo: "
                    "`!battle https://europe.albionbb.com/battles/400379087`"
                ),
                mention_author=False
            )
            return

        battle_id = parse_battle_id(battle_url)

        if not battle_id:
            await ctx.reply(
                embed=error_embed(
                    "El enlace no parece una battleboard válida de AlbionBB."
                ),
                mention_author=False
            )
            return

        if await self.bot.db.battle_exists(battle_id):
            await ctx.reply(
                embed=error_embed(
                    f"La battleboard `{battle_id}` ya fue registrada."
                ),
                mention_author=False
            )
            return

        async with ctx.typing():
            try:
                battle_data = await self.bot.albion.get_battle(battle_id)
            except Exception as error:
                print(
                    f"Error obteniendo battle {battle_id}: "
                    f"{type(error).__name__}: {error}"
                )

                await ctx.reply(
                    embed=error_embed(
                        "No he podido obtener los datos de esa batalla."
                    ),
                    mention_author=False
                )
                return

        participant_ids, participant_names = extract_battle_players(
            battle_data
        )

        if not participant_ids and not participant_names:
            await ctx.reply(
                embed=error_embed(
                    "La batalla existe, pero no he podido leer sus participantes."
                ),
                mention_author=False
            )
            return

        battle_time = extract_battle_time(battle_data)

        await self.bot.db.save_battle_report(
            battle_id=battle_id,
            battle_url=battle_url,
            battle_time=battle_time,
            submitted_by=ctx.author.id
        )

        linked_players = await self.bot.db.get_all_linked_players()

        present = []
        absent = []

        for linked in linked_players:
            id_match = (
                str(linked["albion_player_id"]) in participant_ids
            )

            name_match = (
                normalize_name(linked["albion_player_name"])
                in participant_names
            )

            attended = id_match or name_match

            await self.bot.db.save_battle_attendance(
                battle_id=battle_id,
                discord_id=linked["discord_id"],
                albion_player_id=linked["albion_player_id"],
                albion_player_name=linked["albion_player_name"],
                attended=attended
            )

            line = (
                f"<@{linked['discord_id']}> — "
                f"`{linked['albion_player_name']}`"
            )

            if attended:
                present.append(line)
            else:
                absent.append(line)

        total = len(linked_players)
        attendance_rate = (
            round((len(present) / total) * 100, 1)
            if total > 0
            else 0
        )

        embed = discord.Embed(
            title=f"⚔️ Attendance — Battle {battle_id}",
            url=battle_url,
            description=(
                f"**Presentes:** {len(present)}/{total}\n"
                f"**Ausentes:** {len(absent)}\n"
                f"**Attendance:** {attendance_rate}%"
            ),
            color=discord.Color.gold()
        )

        if present:
            for index, chunk in enumerate(chunk_lines(present), start=1):
                title = "✅ Registrados presentes"

                if index > 1:
                    title += f" ({index})"

                embed.add_field(
                    name=title,
                    value=chunk,
                    inline=False
                )
        else:
            embed.add_field(
                name="✅ Registrados presentes",
                value="Ninguno",
                inline=False
            )

        if absent:
            for index, chunk in enumerate(chunk_lines(absent), start=1):
                title = "❌ Registrados ausentes"

                if index > 1:
                    title += f" ({index})"

                embed.add_field(
                    name=title,
                    value=chunk,
                    inline=False
                )

        embed.set_footer(
            text="Solo se comparan las cuentas enlazadas con VoltEye"
        )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="attendance")
    async def attendance(
        self,
        ctx,
        member: discord.Member | None = None
    ):
        target = member or ctx.author

        linked = await self.bot.db.get_player_by_discord_id(target.id)

        if not linked:
            await ctx.reply(
                embed=error_embed(
                    f"{target.mention} no tiene una cuenta enlazada."
                ),
                mention_author=False
            )
            return

        row = await self.bot.db.get_user_attendance_stats(target.id)

        total = row["total_battles"] or 0
        attended = row["attended_battles"] or 0
        missed = total - attended

        percentage = (
            round((attended / total) * 100, 1)
            if total > 0
            else 0
        )

        embed = discord.Embed(
            title=f"📋 Attendance de {linked['albion_player_name']}",
            description=target.mention,
            color=discord.Color.blue()
        )

        embed.add_field(
            name="✅ Asistencias",
            value=str(attended),
            inline=True
        )

        embed.add_field(
            name="❌ Ausencias",
            value=str(missed),
            inline=True
        )

        embed.add_field(
            name="📊 Porcentaje",
            value=f"{percentage}%",
            inline=True
        )

        embed.add_field(
            name="🕒 Última asistencia",
            value=format_date(row["last_attendance"]),
            inline=False
        )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="inactive")
    async def inactive(self, ctx, days: int = 14):
        if days < 1 or days > 365:
            await ctx.reply(
                embed=error_embed(
                    "Los días deben estar entre 1 y 365."
                ),
                mention_author=False
            )
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await self.bot.db.get_inactive_players(
            cutoff.isoformat()
        )

        embed = discord.Embed(
            title=f"😴 Sin attendance durante {days} días",
            description=(
                "Usuarios enlazados que no aparecen en battleboards "
                f"registradas durante los últimos **{days} días**."
            ),
            color=discord.Color.orange()
        )

        if not rows:
            embed.add_field(
                name="Resultado",
                value="Todos tienen attendance reciente.",
                inline=False
            )
        else:
            lines = []

            for row in rows:
                last_seen = format_date(row["last_attendance"])

                lines.append(
                    f"<@{row['discord_id']}> — "
                    f"`{row['albion_player_name']}`\n"
                    f"└ Última: **{last_seen}** · "
                    f"{row['attended_battles'] or 0}/"
                    f"{row['tracked_battles'] or 0}"
                )

            for index, chunk in enumerate(chunk_lines(lines), start=1):
                title = "Jugadores"

                if index > 1:
                    title += f" ({index})"

                embed.add_field(
                    name=title,
                    value=chunk,
                    inline=False
                )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="battles")
    async def battles(self, ctx):
        rows = await self.bot.db.get_recent_battle_reports(limit=10)

        embed = discord.Embed(
            title="⚔️ Últimas battleboards registradas",
            color=discord.Color.dark_gold()
        )

        if not rows:
            embed.description = "Todavía no hay battleboards registradas."
        else:
            lines = []

            for row in rows:
                lines.append(
                    f"[Battle {row['battle_id']}]({row['battle_url']}) — "
                    f"**{row['attendees'] or 0}/"
                    f"{row['registered_players'] or 0}** presentes"
                )

            embed.description = "\n".join(lines)

        await ctx.reply(embed=embed, mention_author=False)

    @battle.error
    async def battle_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(
                embed=error_embed(
                    "Necesitas el permiso **Gestionar servidor** "
                    "para registrar battleboards."
                ),
                mention_author=False
            )
            return

        raise error


async def setup(bot):
    await bot.add_cog(AttendanceCog(bot))