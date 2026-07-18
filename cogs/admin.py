from discord.ext import commands
import discord


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="resetstats")
    @commands.has_permissions(administrator=True)
    async def resetstats(self, ctx):
        embed = discord.Embed(
            title="⚠️ Reset de VoltEye",
            description=(
                "Voy a borrar:\n\n"
                "• Todas las kills\n"
                "• Todas las muertes\n"
                "• Attendance\n"
                "• Battleboards registradas\n"
                "• Historial de eventos\n\n"
                "**Las cuentas enlazadas NO se borrarán.**\n\n"
                "Escribe `CONFIRMAR` para continuar."
            ),
            color=discord.Color.orange()
        )

        await ctx.send(embed=embed)

        def check(message):
            return (
                message.author.id == ctx.author.id
                and message.channel.id == ctx.channel.id
                and message.content == "CONFIRMAR"
            )

        try:
            await self.bot.wait_for(
                "message",
                check=check,
                timeout=30
            )
        except TimeoutError:
            await ctx.send("❌ Reset cancelado por tiempo agotado.")
            return

        await self.bot.db.reset_all_data_except_links()

        linked = await self.bot.db.get_all_linked_players()

        await ctx.send(
            embed=discord.Embed(
                title="✅ VoltEye reseteado",
                description=(
                    "Se han eliminado todos los datos históricos.\n\n"
                    f"🔗 **Usuarios enlazados conservados:** {len(linked)}\n\n"
                    "A partir de ahora las estadísticas empezarán desde cero."
                ),
                color=discord.Color.green()
            )
        )


async def setup(bot):
    await bot.add_cog(AdminCog(bot))