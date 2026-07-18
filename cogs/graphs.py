import discord
import matplotlib.pyplot as plt

from pathlib import Path
from discord.ext import commands

from config import COMMAND_PREFIX, BOT_NAME
from utils.embeds import error_embed


class GraphsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.output_dir = Path("data/graphs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @commands.command(name="graph")
    async def graph(
        self,
        ctx,
        member: discord.Member | None = None
    ):
        target = member or ctx.author

        linked = await self.bot.db.get_player_by_discord_id(
            target.id
        )

        if not linked:
            await ctx.reply(
                embed=error_embed(
                    "Ese usuario no tiene cuenta enlazada. "
                    f"Usa `{COMMAND_PREFIX}link NombreAlbion`."
                ),
                mention_author=False
            )
            return

        # Solo lee eventos almacenados en player_events.
        # Como ahora esa tabla se rellena únicamente mediante !battles,
        # la gráfica no incluirá historial externo de Albion.
        rows = await self.bot.db.get_daily_history(
            target.id
        )

        if not rows:
            await ctx.reply(
                embed=error_embed(
                    "Todavía no hay datos de battleboards suficientes "
                    "para generar una gráfica."
                ),
                mention_author=False
            )
            return

        days = [
            row["day"]
            for row in rows
        ]

        kills = [
            row["kills"] or 0
            for row in rows
        ]

        deaths = [
            row["deaths"] or 0
            for row in rows
        ]

        file_path = self.output_dir / f"graph_{target.id}.png"

        try:
            plt.figure(figsize=(10, 5))

            plt.plot(
                days,
                kills,
                marker="o",
                label="Kills"
            )

            plt.plot(
                days,
                deaths,
                marker="o",
                label="Deaths"
            )

            plt.title(
                f"{BOT_NAME} | Evolución de "
                f"{linked['albion_player_name']}"
            )

            plt.xlabel("Día")
            plt.ylabel("Cantidad")
            plt.xticks(rotation=45)
            plt.legend()
            plt.tight_layout()
            plt.savefig(file_path)
            plt.close()

            await ctx.reply(
                file=discord.File(
                    file_path,
                    filename=f"graph_{target.id}.png"
                ),
                mention_author=False
            )

        except Exception as error:
            plt.close()

            print(
                "Error generando gráfica: "
                f"{type(error).__name__}: {error}"
            )

            await ctx.reply(
                embed=error_embed(
                    "No se pudo generar la gráfica."
                ),
                mention_author=False
            )

        finally:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass


async def setup(bot):
    await bot.add_cog(GraphsCog(bot))