import discord

from config import BOMB_NAME, BOT_NAME, ALBION_SERVER
from utils.helpers import format_number, calculate_ratio


def error_embed(message: str):
    return discord.Embed(
        title="❌ Error",
        description=message,
        color=discord.Color.red()
    )


def success_embed(title: str, message: str):
    return discord.Embed(
        title=title,
        description=message,
        color=discord.Color.green()
    )


def stats_embed(member: discord.Member, stats: dict, counters: dict):
    total_kills = counters["total_kills"]
    total_deaths = counters["total_deaths"]
    kd = calculate_ratio(total_kills, total_deaths)

    embed = discord.Embed(
        title=f"⚡ {BOT_NAME} | Player Stats",
        description=f"Estadísticas PvP registradas de **{stats['name']}**",
        color=discord.Color.yellow()
    )

    embed.add_field(name="👤 Discord", value=member.mention, inline=True)
    embed.add_field(name="🛡️ Guild", value=stats["guild"], inline=True)
    embed.add_field(name="🌍 Server", value=ALBION_SERVER.capitalize(), inline=True)

    embed.add_field(name="⚔️ Total Kills", value=format_number(total_kills), inline=True)
    embed.add_field(name="💀 Total Deaths", value=format_number(total_deaths), inline=True)
    embed.add_field(name="📈 K/D Ratio", value=str(kd), inline=True)

    embed.add_field(name="🏆 Kills esta semana", value=format_number(counters["kills_week"]), inline=True)
    embed.add_field(name="📅 Kills hoy", value=format_number(counters["kills_today"]), inline=True)
    embed.add_field(name="☠️ Deaths hoy", value=format_number(counters["deaths_today"]), inline=True)

    embed.add_field(name="🎯 Arma favorita", value=counters["favorite_weapon"], inline=True)

    embed.add_field(name="☠️ Te mata más", value=counters["top_killer"], inline=True)

    embed.add_field(name="⚡ Más eliminado", value=counters["top_victim"], inline=True)

    embed.add_field(name="🔥 Killstreak máxima", value=str(counters["longest_killstreak"]), inline=True)

    embed.add_field(name="🔥 Kill Fame", value=format_number(stats["kill_fame"]), inline=True)
    embed.add_field(name="💀 Death Fame", value=format_number(stats["death_fame"]), inline=True)

    embed.set_footer(text=f"{BOMB_NAME} Intelligence System")

    return embed


def linked_players_embed(rows):
    embed = discord.Embed(
        title=f"⚡ {BOT_NAME} | Linked Players",
        color=discord.Color.gold()
    )

    if not rows:
        embed.description = "Todavía no hay jugadores enlazados."
        return embed

    text = ""

    for index, row in enumerate(rows, start=1):
        text += f"**{index}.** `{row['albion_player_name']}` — <@{row['discord_id']}>\n"

    embed.description = text[:4000]
    return embed


def mvp_embed(row):
    embed = discord.Embed(
        title=f"👑 {BOT_NAME} | MVP del día",
        color=discord.Color.gold()
    )

    if not row:
        embed.description = "Todavía no hay kills registradas hoy."
        return embed

    embed.description = (
        f"El MVP de hoy es <@{row['discord_id']}> "
        f"con **{row['kills_today']} kills**.\n\n"
        f"Jugador: **{row['albion_player_name']}**"
    )

    return embed

def get_item_name(item: dict | None):
    if not item:
        return None

    return item.get("Type") or None


def get_item_value(item: dict | None):
    if not item:
        return 0

    return int(item.get("EstimatedMarketValue") or 0)


def format_items(items: list[str], empty_text="Sin objetos"):
    if not items:
        return empty_text

    text = "\n".join(items)

    if len(text) > 1024:
        text = text[:1000] + "\n..."

    return text


def extract_equipment(character: dict):
    equipment = character.get("Equipment", {})

    slots = {
        "MainHand": "🗡️ Mano",
        "OffHand": "🛡️ Offhand",
        "Head": "🪖 Cabeza",
        "Armor": "🥋 Pecho",
        "Shoes": "🥾 Botas",
        "Cape": "🧥 Capa",
        "Mount": "🐎 Montura",
        "Potion": "🧪 Poción",
        "Food": "🍖 Comida",
        "Bag": "🎒 Bolsa",
    }

    lines = []
    total_value = 0

    for key, label in slots.items():
        item = equipment.get(key)

        name = get_item_name(item)
        value = get_item_value(item)

        total_value += value

        if name:
            lines.append(f"{label}: `{name}`")

    return lines, total_value


def extract_inventory(character: dict):
    inventory = character.get("Inventory") or []

    lines = []
    total_value = 0

    for item in inventory:
        if not item:
            continue

        name = get_item_name(item)
        value = get_item_value(item)
        count = item.get("Count") or 1

        total_value += value

        if name:
            lines.append(f"`{name}` x{count}")

    return lines, total_value


def kill_feed_embed(player_name: str, event: dict):
    killer = event.get("Killer", {})
    victim = event.get("Victim", {})

    embed = discord.Embed(
        title="⚔️ Kill registrada",
        description=f"**{killer.get('Name', 'Desconocido')}** mató a **{victim.get('Name', 'Desconocido')}**",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🔥 Kill Fame",
        value=format_number(event.get("TotalVictimKillFame", 0)),
        inline=True
    )

    embed.add_field(
        name="👤 Jugador trackeado",
        value=player_name,
        inline=True
    )

    embed.set_footer(text=f"{BOT_NAME} Kill Feed")
    return embed


def death_feed_embed(player_name: str, event: dict):
    killer = event.get("Killer", {})
    victim = event.get("Victim", {})

    embed = discord.Embed(
        title="💀 Death registrada",
        description=f"**{victim.get('Name', 'Desconocido')}** murió contra **{killer.get('Name', 'Desconocido')}**",
        color=discord.Color.red()
    )

    embed.add_field(
        name="🔥 Fame perdido",
        value=format_number(event.get("TotalVictimKillFame", 0)),
        inline=True
    )

    embed.add_field(
        name="👤 Jugador trackeado",
        value=player_name,
        inline=True
    )

    embed.set_footer(text=f"{BOT_NAME} Death Feed")
    return embed


def battleboard_embed(event: dict):
    killer = event.get("Killer", {})
    victim = event.get("Victim", {})

    battle_id = event.get("BattleId")
    fame = event.get("TotalVictimKillFame", 0)

    embed = discord.Embed(
        title="🔥 Battleboard grande detectada",
        description=(
            f"**{killer.get('AllianceName') or killer.get('GuildName') or 'Desconocidos'}** "
            f"vs "
            f"**{victim.get('AllianceName') or victim.get('GuildName') or 'Desconocidos'}**"
        ),
        color=discord.Color.orange()
    )

    embed.add_field(name="⚔️ Killer", value=killer.get("Name", "Desconocido"), inline=True)
    embed.add_field(name="💀 Victim", value=victim.get("Name", "Desconocido"), inline=True)
    embed.add_field(name="🔥 Kill Fame", value=format_number(fame), inline=True)

    if battle_id:
        embed.add_field(
            name="📋 Battleboard",
            value=f"https://albiononline.com/killboard/battles/{battle_id}",
            inline=False
        )

    embed.set_footer(text=f"{BOT_NAME} Alliance Battleboard Scanner")

    return embed

def alliance_in_character(character: dict, alliance_name: str, alliance_tag: str):
    name = (character.get("AllianceName") or "").lower()
    tag = (character.get("AllianceTag") or "").lower()

    return (
        alliance_name and alliance_name in name
    ) or (
        alliance_tag and alliance_tag in tag
    )


def battleboard_embed(battle_id: str, event: dict):
    killer = event.get("Killer", {})
    victim = event.get("Victim", {})

    fame = event.get("TotalVictimKillFame", 0)

    killer_alliance = killer.get("AllianceName") or killer.get("AllianceTag") or killer.get("GuildName") or "Unknown"
    victim_alliance = victim.get("AllianceName") or victim.get("AllianceTag") or victim.get("GuildName") or "Unknown"

    url = f"https://europe.albionbattles.com/battles/{battle_id}"

    embed = discord.Embed(
        title=f"Albion battle {battle_id}",
        url=url,
        description=f"**{killer_alliance}** vs **{victim_alliance}**",
        color=discord.Color.blue()
    )

    embed.add_field(name="⚔️ Killer", value=killer.get("Name", "Desconocido"), inline=True)
    embed.add_field(name="💀 Victim", value=victim.get("Name", "Desconocido"), inline=True)
    embed.add_field(name="🔥 Fame", value=format_number(fame), inline=True)

    embed.add_field(
        name="🔗 Link",
        value=f"[Abrir battleboard]({url})",
        inline=False
    )

    embed.set_footer(text=f"{BOT_NAME} Battleboard Scanner")

    return embed