import discord
from discord.ext import commands

from config import COMMAND_PREFIX
from utils.embeds import error_embed, success_embed


class LinkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="link")
    async def link(
        self,
        ctx,
        member: discord.Member | None = None,
        *,
        albion_name: str | None = None
    ):
        if member is None:
            member = ctx.author
            albion_name = albion_name

        if albion_name is None:
            await ctx.reply(
                embed=error_embed(
                    f"Uso correcto:\n"
                    f"`{COMMAND_PREFIX}link NombreAlbion`\n"
                    f"`{COMMAND_PREFIX}link @usuario NombreAlbion`"
                ),
                mention_author=False
            )
            return

        async with ctx.typing():
            try:
                player = await self.bot.albion.search_player(albion_name)
            except Exception:
                await ctx.reply(
                    embed=error_embed("No he podido conectar con la API de Albion."),
                    mention_author=False
                )
                return

        if not player:
            await ctx.reply(
                embed=error_embed(f"No he encontrado ningún jugador llamado **{albion_name}**."),
                mention_author=False
            )
            return

        player_id = player.get("Id")
        player_name = player.get("Name")

        await self.bot.db.link_player(
            discord_id=member.id,
            discord_name=str(member),
            player_id=player_id,
            player_name=player_name
        )

        await ctx.reply(
            embed=success_embed(
                "✅ Cuenta enlazada",
                f"{member.mention} ahora está enlazado con **{player_name}**."
            ),
            mention_author=False
        )

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        linked = await self.bot.db.get_player_by_discord_id(ctx.author.id)

        if not linked:
            await ctx.reply(
                embed=error_embed("No tienes ninguna cuenta enlazada."),
                mention_author=False
            )
            return

        await self.bot.db.unlink_player(ctx.author.id)

        await ctx.reply(
            embed=success_embed(
                "✅ Cuenta desenlazada",
                f"Has desenlazado **{linked['albion_player_name']}** correctamente."
            ),
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(LinkCog(bot))