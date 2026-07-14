import aiohttp
from config import ALBION_API_BASE


class AlbionAPI:
    def __init__(self):
        self.base_url = ALBION_API_BASE

    async def get_battle(self, battle_id: str):
        return await self._get(f"/battles/{battle_id}")

    async def _get(self, endpoint: str, params: dict | None = None):
        url = f"{self.base_url}{endpoint}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                response.raise_for_status()
                return await response.json()

    async def search_player(self, player_name: str):
        data = await self._get("/search", {"q": player_name})
        players = data.get("players", [])

        if not players:
            return None

        exact_match = next(
            (
                player for player in players
                if player.get("Name", "").lower() == player_name.lower()
            ),
            None
        )

        return exact_match or players[0]

    async def get_player_info(self, player_id: str):
        return await self._get(f"/players/{player_id}")

    async def get_player_kills(self, player_id: str):
        return await self._get(f"/players/{player_id}/kills")

    async def get_player_deaths(self, player_id: str):
        return await self._get(f"/players/{player_id}/deaths")

    async def get_recent_events(self, limit: int = 51):
        return await self._get("/events", {"limit": limit})

    async def get_battle(self, battle_id: str):
        return await self._get(f"/battles/{battle_id}")

    async def get_basic_stats(self, player_id: str):
        info = await self.get_player_info(player_id)
        kills = await self.get_player_kills(player_id)
        deaths = await self.get_player_deaths(player_id)

        lifetime = info.get("LifetimeStatistics", {})
        pvp = lifetime.get("PvP", {})

        return {
            "id": info.get("Id"),
            "name": info.get("Name", "Desconocido"),
            "guild": info.get("GuildName") or "Sin guild",
            "alliance": info.get("AllianceName") or "Sin alianza",
            "kill_fame": pvp.get("KillFame", 0),
            "death_fame": pvp.get("DeathFame", 0),
            "recent_kills_api": kills,
            "recent_deaths_api": deaths,
        }