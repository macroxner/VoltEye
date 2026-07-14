import discord
from discord.ext import commands, tasks

from services.gear_image import GearImageBuilder

from config import (
    KILL_FEED_CHANNEL_ID,
    BATTLEBOARD_CHANNEL_ID,
    ALLIANCE_NAME,
    ALLIANCE_TAG,
    BATTLEBOARD_MIN_FAME,
    FEED_INTERVAL_SECONDS,
)

from utils.embeds import (
    kill_feed_embed,
    death_feed_embed,
    battleboard_embed,
    alliance_in_character,
)

from utils.helpers import (
    get_event_id,
    clean_albion_timestamp,
    get_weapon_from_event,
    get_killer_name,
    get_victim_name,
)


class FeedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gear_builder = GearImageBuilder()

        self.feed_loop.change_interval(seconds=FEED_INTERVAL_SECONDS)
        self.feed_loop.start()

    def cog_unload(self):
        self.feed_loop.cancel()

    async def sync_linked_player(self, linked, kill_channel):
        stats = await self.bot.albion.get_basic_stats(linked["albion_player_id"])

        for event in stats["recent_kills_api"]:
            event_id = get_event_id(event)
            post_key = f"kill:{linked['albion_player_id']}:{event_id}"

            await self.bot.db.save_event(
                linked["discord_id"],
                linked["albion_player_id"],
                linked["albion_player_name"],
                event_id,
                "kill",
                clean_albion_timestamp(event.get("TimeStamp")),
                event.get("TotalVictimKillFame", 0),
                get_weapon_from_event(event),
                get_killer_name(event),
                get_victim_name(event),
            )

            if kill_channel and not await self.bot.db.has_posted(post_key):
                image_path = await self.gear_builder.build_event_image(event, "kill")
                embed = kill_feed_embed(linked["albion_player_name"], event)
                embed.set_image(url=f"attachment://{image_path.name}")

                await kill_channel.send(
                    embed=embed,
                    file=discord.File(image_path, filename=image_path.name)
                )
                await self.bot.db.mark_posted(post_key)

        for event in stats["recent_deaths_api"]:
            event_id = get_event_id(event)
            post_key = f"death:{linked['albion_player_id']}:{event_id}"

            await self.bot.db.save_event(
                linked["discord_id"],
                linked["albion_player_id"],
                linked["albion_player_name"],
                event_id,
                "death",
                clean_albion_timestamp(event.get("TimeStamp")),
                event.get("TotalVictimKillFame", 0),
                get_weapon_from_event(event),
                get_killer_name(event),
                get_victim_name(event),
            )

            if kill_channel and not await self.bot.db.has_posted(post_key):
                image_path = await self.gear_builder.build_event_image(event, "death")
                embed = death_feed_embed(linked["albion_player_name"], event)
                embed.set_image(url=f"attachment://{image_path.name}")

                await kill_channel.send(
                    embed=embed,
                    file=discord.File(image_path, filename=image_path.name)
                )
                await self.bot.db.mark_posted(post_key)

    async def scan_battleboards(self, battle_channel):
        if not battle_channel:
            return

        if not ALLIANCE_NAME and not ALLIANCE_TAG:
            print("No hay ALLIANCE_NAME ni ALLIANCE_TAG configurado.")
            return

        events = await self.bot.albion.get_recent_events(limit=51)

        for event in events:
            battle_id = event.get("BattleId")
            fame = event.get("TotalVictimKillFame", 0)

            if not battle_id or fame < BATTLEBOARD_MIN_FAME:
                continue

            killer = event.get("Killer", {})
            victim = event.get("Victim", {})

            if not (
                alliance_in_character(killer, ALLIANCE_NAME, ALLIANCE_TAG)
                or alliance_in_character(victim, ALLIANCE_NAME, ALLIANCE_TAG)
            ):
                continue

            post_key = f"battleboard:{battle_id}"

            if await self.bot.db.has_posted(post_key):
                continue

            await battle_channel.send(
                embed=battleboard_embed(str(battle_id), event)
            )

            await self.bot.db.mark_posted(post_key)

    @tasks.loop(seconds=120)
    async def feed_loop(self):
        if not self.bot.is_ready():
            return

        kill_channel = self.bot.get_channel(KILL_FEED_CHANNEL_ID)
        battle_channel = self.bot.get_channel(BATTLEBOARD_CHANNEL_ID)

        linked_players = await self.bot.db.get_all_linked_players()

        for linked in linked_players:
            try:
                await self.sync_linked_player(linked, kill_channel)
            except Exception as error:
                print(f"Error feed {linked['albion_player_name']}: {error}")

        try:
            await self.scan_battleboards(battle_channel)
        except Exception as error:
            print(f"Error battleboard scanner: {error}")

    @feed_loop.before_loop
    async def before_feed_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(FeedCog(bot))