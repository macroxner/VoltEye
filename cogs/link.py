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
        # Permite:
        # !link NombreAlbion
        # !link @usuario NombreAlbion
        if member is None:
            member = ctx.author

        if albion_name is None:
            await ctx.reply(
                embed=error_embed(
                    "Uso correcto:\n"
                    f"`{COMMAND_PREFIX}link NombreAlbion`\n"
                    f"`{COMMAND_PREFIX}link @usuario NombreAlbion`"
                ),
                mention_author=False
            )
            return

        async with ctx.typing():
            try:
                player = await self.bot.albion.search_player(albion_name)
            except Exception as error:
                print(
                    "Error buscando jugador en Albion: "
                    f"{type(error).__name__}: {error}"
                )

                await ctx.reply(
                    embed=error_embed(
                        "No he podido conectar con la API de Albion."
                    ),
                    mention_author=False
                )
                return

        if not player:
            await ctx.reply(
                embed=error_embed(
                    f"No he encontrado ningún jugador llamado "
                    f"**{albion_name}**."
                ),
                mention_author=False
            )
            return

        player_id = player.get("Id")
        player_name = player.get("Name")

        if not player_id or not player_name:
            await ctx.reply(
                embed=error_embed(
                    "La API encontró al jugador, pero devolvió datos incompletos."
                ),
                mention_author=False
            )
            return

        previous_link = await self.bot.db.get_player_by_discord_id(
            member.id
        )

        await self.bot.db.link_player(
            discord_id=member.id,
            discord_name=str(member),
            player_id=player_id,
            player_name=player_name
        )

        # Al enlazar o cambiar de personaje, elimina cualquier kill o muerte
        # antigua asociada a ese Discord. A partir de ese momento solo se
        # guardarán estadísticas procesadas mediante !battles.
        await self.bot.db.delete_player_events(member.id)

        if previous_link:
            description = (
                f"{member.mention} ahora está enlazado con "
                f"**{player_name}**.\n\n"
                "Sus estadísticas anteriores se han reiniciado. "
                "A partir de ahora solo contarán las battleboards enviadas "
                "con `!battles`."
            )
        else:
            description = (
                f"{member.mention} ahora está enlazado con "
                f"**{player_name}**.\n\n"
                "Sus kills y muertes empezarán en cero y solo aumentarán "
                "mediante battleboards procesadas con `!battles`."
            )

        await ctx.reply(
            embed=success_embed(
                "✅ Cuenta enlazada",
                description
            ),
            mention_author=False
        )

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        linked = await self.bot.db.get_player_by_discord_id(
            ctx.author.id
        )

        if not linked:
            await ctx.reply(
                embed=error_embed(
                    "No tienes ninguna cuenta enlazada."
                ),
                mention_author=False
            )
            return

        # Borra también sus estadísticas para que no queden datos huérfanos.
        await self.bot.db.delete_player_events(ctx.author.id)
        await self.bot.db.unlink_player(ctx.author.id)

        await ctx.reply(
            embed=success_embed(
                "✅ Cuenta desenlazada",
                (
                    f"Has desenlazado "
                    f"**{linked['albion_player_name']}** correctamente.\n"
                    "También se han eliminado sus kills y muertes guardadas."
                )
            ),
            mention_author=False
        )


async def setup(bot):
    await bot.add_cog(LinkCog(bot))