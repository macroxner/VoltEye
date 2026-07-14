import discord
from discord.ext import commands

from config import DISCORD_TOKEN, COMMAND_PREFIX, BOMB_NAME, BOT_NAME
from services.database import Database
from services.albion_api import AlbionAPI


class VoltEyeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            help_command=None
        )

        self.db = Database()
        self.albion = AlbionAPI()

    async def setup_hook(self):
        await self.db.init()

        for extension in [
            "cogs.link",
            "cogs.stats",
            "cogs.leaderboard",
            "cogs.graphs",
            "cogs.feed",
            "cogs.attendance",
        ]:
            await self.load_extension(extension)

    async def on_ready(self):
        await self.change_presence(
            activity=discord.Game(name=f"⚡ {BOMB_NAME} battlefield")
        )

        print(f"✅ {self.user} conectado correctamente.")
        print(f"⚡ {BOT_NAME} listo para {BOMB_NAME}.")


bot = VoltEyeBot()


@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="⚡ VoltEye Commands",
        description="Sistema de inteligencia PvP para Voltage.",
        color=discord.Color.yellow()
    )

    embed.add_field(name="🔗 Enlazar tu cuenta", value=f"`{COMMAND_PREFIX}link NombreAlbion`", inline=False)
    embed.add_field(name="🔗 Enlazar a otro usuario", value=f"`{COMMAND_PREFIX}link @usuario NombreAlbion`", inline=False)
    embed.add_field(name="❌ Desenlazar", value=f"`{COMMAND_PREFIX}unlink`", inline=False)
    embed.add_field(name="📊 Stats", value=f"`{COMMAND_PREFIX}stats` o `{COMMAND_PREFIX}stats @usuario`", inline=False)
    embed.add_field(name="🏆 Enlazados", value=f"`{COMMAND_PREFIX}linked`", inline=False)
    embed.add_field(name="👑 MVP del día", value=f"`{COMMAND_PREFIX}mvp`", inline=False)
    embed.add_field(
        name="⚔️ Registrar battleboard",
        value=f"`{COMMAND_PREFIX}battle enlace`",
        inline=False
    )

    embed.add_field(
        name="📋 Attendance",
        value=(
            f"`{COMMAND_PREFIX}attendance`\n"
            f"`{COMMAND_PREFIX}attendance @usuario`"
        ),
        inline=False
    )

    embed.add_field(
        name="😴 Inactivos",
        value=f"`{COMMAND_PREFIX}inactive 14`",
        inline=False
    )

    embed.add_field(
        name="📚 Battleboards registradas",
        value=f"`{COMMAND_PREFIX}battles`",
        inline=False
    )

    await ctx.reply(embed=embed, mention_author=False)


bot.run(DISCORD_TOKEN)