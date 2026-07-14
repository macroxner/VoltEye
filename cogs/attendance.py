import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils.embeds import error_embed
from utils.helpers import (
    clean_albion_timestamp,
    get_event_id,
    get_killer_name,
    get_victim_name,
    get_weapon_from_event,
)


BATTLE_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?(?:europe\.)?albionbb\.com/battles/(\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)


def parse_battle_id(value: str) -> str | None:
    value = value.strip()

    if value.isdigit():
        return value

    match = BATTLE_URL_PATTERN.match(value)
    return match.group(1) if match else None


def normalize_name(value: str | None) -> str:
    return (value or "").strip().casefold()


def parse_timestamp(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()

    cleaned = str(value).replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(cleaned)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def extract_battle_time(battle: dict) -> str:
    timestamp = (
        battle.get("startTime")
        or battle.get("StartTime")
        or battle.get("startTimeUtc")
        or battle.get("StartTimeUtc")
        or battle.get("endTime")
        or battle.get("EndTime")
        or battle.get("TimeStamp")
    )

    return parse_timestamp(timestamp)


def get_player_id(player: dict) -> str:
    return str(
        player.get("id")
        or player.get("Id")
        or player.get("playerId")
        or player.get("PlayerId")
        or ""
    )


def get_player_name(player: dict) -> str:
    return str(
        player.get("name")
        or player.get("Name")
        or player.get("playerName")
        or player.get("PlayerName")
        or ""
    )


def extract_battle_player_records(battle: dict) -> list[dict]:
    raw_players = battle.get("players") or battle.get("Players") or []

    if isinstance(raw_players, dict):
        records = []

        for key, value in raw_players.items():
            if not isinstance(value, dict):
                continue

            player = dict(value)

            if not get_player_id(player):
                player["id"] = key

            records.append(player)

        return records

    if isinstance(raw_players, list):
        return [player for player in raw_players if isinstance(player, dict)]

    return []


def extract_battle_players(battle: dict) -> tuple[set[str], set[str]]:
    player_ids: set[str] = set()
    player_names: set[str] = set()

    for player in extract_battle_player_records(battle):
        player_id = get_player_id(player)
        player_name = get_player_name(player)

        if player_id:
            player_ids.add(player_id)

        if player_name:
            player_names.add(normalize_name(player_name))

    return player_ids, player_names


def extract_embedded_events(battle: dict) -> list[dict]:
    """
    Algunas respuestas incluyen los eventos dentro de la propia batalla.
    Acepta distintos nombres de campo para que el código sea tolerante.
    """
    candidates = (
        battle.get("events"),
        battle.get("Events"),
        battle.get("killEvents"),
        battle.get("KillEvents"),
    )

    for candidate in candidates:
        if isinstance(candidate, list):
            return [event for event in candidate if isinstance(event, dict)]

        if isinstance(candidate, dict):
            return [
                event
                for event in candidate.values()
                if isinstance(event, dict)
            ]

    return []


def get_count(player: dict, *keys: str) -> int:
    for key in keys:
        value = player.get(key)

        if value is None:
            continue

        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue

    return 0


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

    @staticmethod
    def make_linked_maps(linked_players):
        by_id = {}
        by_name = {}

        for linked in linked_players:
            player_id = str(linked["albion_player_id"])
            player_name = normalize_name(linked["albion_player_name"])

            if player_id:
                by_id[player_id] = linked

            if player_name:
                by_name[player_name] = linked

        return by_id, by_name

    @staticmethod
    def find_linked_player(
        character: dict,
        linked_by_id: dict,
        linked_by_name: dict,
    ):
        player_id = get_player_id(character)
        player_name = normalize_name(get_player_name(character))

        if player_id and player_id in linked_by_id:
            return linked_by_id[player_id]

        if player_name and player_name in linked_by_name:
            return linked_by_name[player_name]

        return None

    async def get_battle_events(
        self,
        battle_id: str,
        battle_data: dict,
    ) -> list[dict]:
        embedded = extract_embedded_events(battle_data)

        if embedded:
            return embedded

        getter = getattr(self.bot.albion, "get_battle_events", None)

        if getter is None:
            return []

        try:
            events = await getter(battle_id)
        except Exception as error:
            print(
                f"No se pudieron obtener eventos detallados de la battle "
                f"{battle_id}: {type(error).__name__}: {error}"
            )
            return []

        if isinstance(events, list):
            return [event for event in events if isinstance(event, dict)]

        if isinstance(events, dict):
            nested = (
                events.get("events")
                or events.get("Events")
                or events.get("data")
            )

            if isinstance(nested, list):
                return [
                    event
                    for event in nested
                    if isinstance(event, dict)
                ]

        return []

    async def save_detailed_events(
        self,
        events: list[dict],
        linked_by_id: dict,
        linked_by_name: dict,
    ) -> dict:
        results = {}
        kills = 0
        deaths = 0

        for event in events:
            killer = event.get("Killer") or event.get("killer") or {}
            victim = event.get("Victim") or event.get("victim") or {}

            linked_killer = self.find_linked_player(
                killer,
                linked_by_id,
                linked_by_name,
            )
            linked_victim = self.find_linked_player(
                victim,
                linked_by_id,
                linked_by_name,
            )

            raw_event_id = get_event_id(event)

            if raw_event_id is None:
                continue

            event_id = str(raw_event_id)
            event_time = clean_albion_timestamp(
                event.get("TimeStamp")
                or event.get("timestamp")
            )
            fame = int(event.get("TotalVictimKillFame") or 0)
            weapon = get_weapon_from_event(event)
            killer_name = get_killer_name(event)
            victim_name = get_victim_name(event)

            if linked_killer:
                await self.bot.db.save_event(
                    linked_killer["discord_id"],
                    linked_killer["albion_player_id"],
                    linked_killer["albion_player_name"],
                    event_id,
                    "kill",
                    event_time,
                    fame,
                    weapon,
                    killer_name,
                    victim_name,
                )

                name = linked_killer["albion_player_name"]
                results.setdefault(name, {"kills": 0, "deaths": 0})
                results[name]["kills"] += 1
                kills += 1

            if linked_victim:
                await self.bot.db.save_event(
                    linked_victim["discord_id"],
                    linked_victim["albion_player_id"],
                    linked_victim["albion_player_name"],
                    event_id,
                    "death",
                    event_time,
                    fame,
                    weapon,
                    killer_name,
                    victim_name,
                )

                name = linked_victim["albion_player_name"]
                results.setdefault(name, {"kills": 0, "deaths": 0})
                results[name]["deaths"] += 1
                deaths += 1

        return {
            "players": results,
            "kills": kills,
            "deaths": deaths,
            "source": "events",
        }

    async def save_aggregate_player_stats(
        self,
        battle_id: str,
        battle_time: str,
        player_records: list[dict],
        linked_by_id: dict,
        linked_by_name: dict,
    ) -> dict:
        """
        Fallback: si la API no devuelve eventos individuales, usa los contadores
        de kills y muertes incluidos en cada jugador de la battleboard.
        """
        results = {}
        total_kills = 0
        total_deaths = 0

        for player in player_records:
            linked = self.find_linked_player(
                player,
                linked_by_id,
                linked_by_name,
            )

            if not linked:
                continue

            kill_count = get_count(
                player,
                "kills",
                "Kills",
                "killCount",
                "KillCount",
                "totalKills",
                "TotalKills",
                "killsCount",
                "KillsCount",
                "numberOfKills",
                "NumberOfKills",
            )
            death_count = get_count(
                player,
                "deaths",
                "Deaths",
                "deathCount",
                "DeathCount",
                "totalDeaths",
                "TotalDeaths",
                "deathsCount",
                "DeathsCount",
                "numberOfDeaths",
                "NumberOfDeaths",
            )

            player_name = linked["albion_player_name"]
            player_id = linked["albion_player_id"]

            results.setdefault(
                player_name,
                {"kills": 0, "deaths": 0},
            )
            results[player_name]["kills"] += kill_count
            results[player_name]["deaths"] += death_count

            for index in range(kill_count):
                await self.bot.db.save_event(
                    linked["discord_id"],
                    player_id,
                    player_name,
                    f"battle:{battle_id}:kill:{player_id}:{index + 1}",
                    "kill",
                    battle_time,
                    0,
                    None,
                    player_name,
                    None,
                )

            for index in range(death_count):
                await self.bot.db.save_event(
                    linked["discord_id"],
                    player_id,
                    player_name,
                    f"battle:{battle_id}:death:{player_id}:{index + 1}",
                    "death",
                    battle_time,
                    0,
                    None,
                    None,
                    player_name,
                )

            total_kills += kill_count
            total_deaths += death_count

        return {
            "players": results,
            "kills": total_kills,
            "deaths": total_deaths,
            "source": "player_totals",
        }

    async def save_attendance(
        self,
        battle_id: str,
        linked_players,
        participant_ids: set[str],
        participant_names: set[str],
    ) -> tuple[list[str], list[str]]:
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
                attended=attended,
            )

            line = (
                f"<@{linked['discord_id']}> — "
                f"`{linked['albion_player_name']}`"
            )

            if attended:
                present.append(line)
            else:
                absent.append(line)

        return present, absent

    @commands.command(name="battles", aliases=["battle"])
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def battles(
        self,
        ctx: commands.Context,
        battle_url: str | None = None,
    ):
        """
        Procesa una battleboard y actualiza:
        - attendance;
        - kills y muertes de jugadores enlazados;
        - mensaje resumen.

        Uso:
        !battles https://europe.albionbb.com/battles/400379087
        """
        if not battle_url:
            await ctx.reply(
                embed=error_embed(
                    "Uso: `!battles URL`\n"
                    "Ejemplo: "
                    "`!battles https://europe.albionbb.com/battles/400379087`"
                ),
                mention_author=False,
            )
            return

        battle_id = parse_battle_id(battle_url)

        if not battle_id:
            await ctx.reply(
                embed=error_embed(
                    "El enlace no parece una battleboard válida de AlbionBB."
                ),
                mention_author=False,
            )
            return

        if await self.bot.db.battle_exists(battle_id):
            await ctx.reply(
                embed=error_embed(
                    f"La battleboard `{battle_id}` ya fue procesada."
                ),
                mention_author=False,
            )
            return

        processing_message = await ctx.reply(
            f"⏳ Procesando battleboard `{battle_id}`...",
            mention_author=False,
        )

        try:
            battle_data = await self.bot.albion.get_battle(battle_id)

            if not isinstance(battle_data, dict):
                raise ValueError(
                    "La API no devolvió un objeto válido para la batalla."
                )

            player_records = extract_battle_player_records(battle_data)
            participant_ids, participant_names = extract_battle_players(
                battle_data
            )

            if not participant_ids and not participant_names:
                raise ValueError(
                    "La batalla existe, pero no se pudieron leer "
                    "sus participantes."
                )

            battle_time = extract_battle_time(battle_data)
            linked_players = await self.bot.db.get_all_linked_players()
            linked_by_id, linked_by_name = self.make_linked_maps(
                linked_players
            )

            # Los totales de kills y muertes se leen directamente de los
            # jugadores de la battleboard. El endpoint de eventos puede devolver
            # datos incompletos o no coincidir con los participantes enlazados.
            event_results = await self.save_aggregate_player_stats(
                battle_id,
                battle_time,
                player_records,
                linked_by_id,
                linked_by_name,
            )

            # Solo intentamos leer eventos detallados para diagnóstico futuro.
            # No se usan para calcular los contadores, evitando resultados 0
            # cuando Albion devuelve una lista parcial o con otro formato.
            detailed_events = await self.get_battle_events(
                battle_id,
                battle_data,
            )

            print(
                f"Battle {battle_id}: {len(player_records)} jugadores, "
                f"{len(detailed_events)} eventos detallados, "
                f"{event_results['kills']} kills y "
                f"{event_results['deaths']} muertes registradas."
            )

            await self.bot.db.save_battle_report(
                battle_id=battle_id,
                battle_url=battle_url,
                battle_time=battle_time,
                submitted_by=ctx.author.id,
            )

            present, absent = await self.save_attendance(
                battle_id,
                linked_players,
                participant_ids,
                participant_names,
            )

            total = len(linked_players)
            attendance_rate = (
                round((len(present) / total) * 100, 1)
                if total > 0
                else 0
            )

            embed = discord.Embed(
                title=f"⚔️ Battleboard procesada — {battle_id}",
                url=battle_url,
                description=(
                    f"**Presentes:** {len(present)}/{total}\n"
                    f"**Ausentes:** {len(absent)}\n"
                    f"**Attendance:** {attendance_rate}%\n"
                    f"**Kills registradas:** {event_results['kills']}\n"
                    f"**Muertes registradas:** {event_results['deaths']}\n\n"
                    "Solo se han contabilizado personajes enlazados "
                    "con VoltEye."
                ),
                color=discord.Color.gold(),
            )

            player_results = event_results["players"]

            if player_results:
                result_lines = []

                ordered = sorted(
                    player_results.items(),
                    key=lambda item: (
                        item[1]["kills"],
                        -item[1]["deaths"],
                        item[0].casefold(),
                    ),
                    reverse=True,
                )

                for player_name, stats in ordered:
                    result_lines.append(
                        f"**{player_name}** — "
                        f"⚔️ {stats['kills']} · "
                        f"💀 {stats['deaths']}"
                    )

                for index, chunk in enumerate(
                    chunk_lines(result_lines),
                    start=1,
                ):
                    title = "📊 Kills y muertes"

                    if index > 1:
                        title += f" ({index})"

                    embed.add_field(
                        name=title,
                        value=chunk,
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="📊 Kills y muertes",
                    value=(
                        "No se encontraron kills ni muertes de "
                        "jugadores registrados."
                    ),
                    inline=False,
                )

            if present:
                for index, chunk in enumerate(
                    chunk_lines(present),
                    start=1,
                ):
                    title = "✅ Registrados presentes"

                    if index > 1:
                        title += f" ({index})"

                    embed.add_field(
                        name=title,
                        value=chunk,
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="✅ Registrados presentes",
                    value="Ninguno",
                    inline=False,
                )

            if absent:
                for index, chunk in enumerate(
                    chunk_lines(absent),
                    start=1,
                ):
                    title = "❌ Registrados ausentes"

                    if index > 1:
                        title += f" ({index})"

                    embed.add_field(
                        name=title,
                        value=chunk,
                        inline=False,
                    )

            source_text = (
                "eventos detallados"
                if event_results["source"] == "events"
                else "totales de jugadores"
            )

            embed.set_footer(
                text=(
                    f"Datos de estadísticas: {source_text}. "
                    "La misma battleboard no puede procesarse dos veces."
                )
            )

            await processing_message.edit(
                content=None,
                embed=embed,
            )

        except Exception as error:
            print(
                f"Error procesando battle {battle_id}: "
                f"{type(error).__name__}: {error}"
            )

            await processing_message.edit(
                content=None,
                embed=error_embed(
                    "No se pudo procesar la battleboard.\n"
                    f"`{type(error).__name__}: {error}`"
                ),
            )

    @commands.command(name="attendance")
    async def attendance(
        self,
        ctx,
        member: discord.Member | None = None,
    ):
        target = member or ctx.author
        linked = await self.bot.db.get_player_by_discord_id(target.id)

        if not linked:
            await ctx.reply(
                embed=error_embed(
                    f"{target.mention} no tiene una cuenta enlazada."
                ),
                mention_author=False,
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
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="✅ Asistencias",
            value=str(attended),
            inline=True,
        )
        embed.add_field(
            name="❌ Ausencias",
            value=str(missed),
            inline=True,
        )
        embed.add_field(
            name="📊 Porcentaje",
            value=f"{percentage}%",
            inline=True,
        )
        embed.add_field(
            name="🕒 Última asistencia",
            value=format_date(row["last_attendance"]),
            inline=False,
        )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="inactive")
    async def inactive(self, ctx, days: int = 14):
        if days < 1 or days > 365:
            await ctx.reply(
                embed=error_embed(
                    "Los días deben estar entre 1 y 365."
                ),
                mention_author=False,
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
            color=discord.Color.orange(),
        )

        if not rows:
            embed.add_field(
                name="Resultado",
                value="Todos tienen attendance reciente.",
                inline=False,
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

            for index, chunk in enumerate(
                chunk_lines(lines),
                start=1,
            ):
                title = "Jugadores"

                if index > 1:
                    title += f" ({index})"

                embed.add_field(
                    name=title,
                    value=chunk,
                    inline=False,
                )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="battlelist")
    async def battlelist(self, ctx):
        rows = await self.bot.db.get_recent_battle_reports(limit=10)

        embed = discord.Embed(
            title="⚔️ Últimas battleboards registradas",
            color=discord.Color.dark_gold(),
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

    @battles.error
    async def battles_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(
                embed=error_embed(
                    "Necesitas el permiso **Gestionar servidor** "
                    "para registrar battleboards."
                ),
                mention_author=False,
            )
            return

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(
                embed=error_embed(
                    f"Espera {error.retry_after:.1f} segundos antes "
                    "de procesar otra battleboard."
                ),
                mention_author=False,
            )
            return

        raise error


async def setup(bot):
    await bot.add_cog(AttendanceCog(bot))
