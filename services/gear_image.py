import aiohttp
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import quote


class GearImageBuilder:
    def __init__(self):
        self.output_dir = Path("data/killboards")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.bg = (214, 184, 150)
        self.text = (25, 20, 18)
        self.muted = (70, 60, 55)

        try:
            self.font_big = ImageFont.truetype("arial.ttf", 28)
            self.font = ImageFont.truetype("arial.ttf", 18)
            self.font_small = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            self.font_big = ImageFont.load_default()
            self.font = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def item_url(self, item: dict):
        if not item:
            return None

        item_type = item.get("Type")
        quality = item.get("Quality", 1)

        if not item_type:
            return None

        return f"https://render.albiononline.com/v1/item/{quote(item_type)}.png?quality={quality}"

    async def download_image(self, session, item: dict, size=64):
        url = self.item_url(item)

        if not url:
            return None

        try:
            async with session.get(url, timeout=15) as response:
                if response.status != 200:
                    return None

                data = await response.read()
                img = Image.open(BytesIO(data)).convert("RGBA")
                return img.resize((size, size))
        except Exception:
            return None

    def get_value(self, item: dict | None):
        if not item:
            return 0

        value = item.get("EstimatedMarketValue")

        if value is None:
            return 0

        return int(value)

    def total_character_value(self, character: dict):
        total = 0

        equipment = character.get("Equipment") or {}
        inventory = character.get("Inventory") or []

        for item in equipment.values():
            total += self.get_value(item)

        for item in inventory:
            total += self.get_value(item)

        return total

    def format_number(self, value):
        return f"{int(value):,}".replace(",", ".")

    def draw_text_center(self, draw, xy, text, font, fill):
        x, y = xy
        box = draw.textbbox((0, 0), text, font=font)
        w = box[2] - box[0]
        draw.text((x - w / 2, y), text, font=font, fill=fill)

    async def paste_item(self, base, draw, session, item, x, y, size=64):
        img = await self.download_image(session, item, size=size)

        if img:
            base.alpha_composite(img, (x, y))
        else:
            draw.rounded_rectangle(
                (x, y, x + size, y + size),
                radius=8,
                fill=(185, 155, 125)
            )

        if item and item.get("Count") and item.get("Count") > 1:
            count = str(item.get("Count"))
            draw.rounded_rectangle(
                (x + size - 28, y + size - 22, x + size - 2, y + size - 2),
                radius=4,
                fill=(20, 20, 20)
            )
            draw.text((x + size - 25, y + size - 20), count, font=self.font_small, fill=(255, 255, 255))

    async def draw_character(self, base, draw, session, character, x, y, title):
        name = character.get("Name", "Desconocido")
        guild = character.get("GuildName") or ""

        self.draw_text_center(draw, (x + 135, y), name, self.font_big, self.text)
        self.draw_text_center(draw, (x + 135, y + 32), guild, self.font, self.text)

        equipment = character.get("Equipment") or {}

        positions = {
            "Head": (x + 95, y + 75),
            "Armor": (x + 95, y + 155),
            "Shoes": (x + 95, y + 235),

            "MainHand": (x + 15, y + 155),
            "OffHand": (x + 175, y + 155),

            # Intercambiadas
            "Bag": (x + 15, y + 75),
            "Cape": (x + 175, y + 75),

            "Mount": (x + 95, y + 320),

            # Intercambiadas
            "Food": (x + 175, y + 235),
            "Potion": (x + 15, y + 235),
        }

        for slot, pos in positions.items():
            await self.paste_item(base, draw, session, equipment.get(slot), pos[0], pos[1], 84)

    async def draw_inventory(self, base, draw, session, inventory, start_x, start_y, title):
        draw.text((start_x, start_y), title, font=self.font, fill=self.text)

        x = start_x
        y = start_y + 30

        max_items = 24

        for index, item in enumerate((inventory or [])[:max_items]):
            col = index % 8
            row = index // 8

            await self.paste_item(
                base,
                draw,
                session,
                item,
                x + col * 70,
                y + row * 70,
                60
            )

    async def build_event_image(self, event: dict, event_type: str):
        killer = event.get("Killer", {})
        victim = event.get("Victim", {})

        width = 1050
        height = 760

        base = Image.new("RGBA", (width, height), self.bg)
        draw = ImageDraw.Draw(base)

        async with aiohttp.ClientSession() as session:
            await self.draw_character(base, draw, session, killer, 40, 25, "Killer")
            await self.draw_character(base, draw, session, victim, 740, 25, "Victim")

            killer_value = self.total_character_value(killer)
            victim_value = self.total_character_value(victim)

            center_x = width // 2

            draw.ellipse((center_x - 45, 190, center_x + 45, 280), fill=(50, 45, 45))
            self.draw_text_center(draw, (center_x, 214), "☠", self.font_big, (255, 255, 255))

            title = "KILL" if event_type == "kill" else "DEATH"
            self.draw_text_center(draw, (center_x, 295), title, self.font_big, self.text)

            fame = event.get("TotalVictimKillFame", 0)
            self.draw_text_center(draw, (center_x, 345), f"Fame: {self.format_number(fame)}", self.font, self.text)

            if killer_value > 0:
                self.draw_text_center(draw, (center_x, 380), f"Killer value: {self.format_number(killer_value)}", self.font_small, self.muted)
            else:
                self.draw_text_center(draw, (center_x, 380), "Killer value: no disponible", self.font_small, self.muted)

            if victim_value > 0:
                self.draw_text_center(draw, (center_x, 405), f"Victim value: {self.format_number(victim_value)}", self.font_small, self.muted)
            else:
                self.draw_text_center(draw, (center_x, 405), "Victim value: no disponible", self.font_small, self.muted)

            await self.draw_inventory(
                base,
                draw,
                session,
                victim.get("Inventory") or [],
                210,
                500,
                "LOOT"
            )

        event_id = event.get("EventId") or f"{killer.get('Name')}_{victim.get('Name')}"
        file_path = self.output_dir / f"{event_type}_{event_id}.png"

        base.convert("RGB").save(file_path, quality=95)
        return file_path