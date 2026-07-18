from discord.ext import commands


class FeedCog(commands.Cog):
    """
    El feed automático se ha desactivado.

    Las kills, muertes y attendance se procesan únicamente cuando
    se usa:
        !battles <URL>
    """

    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(FeedCog(bot))
