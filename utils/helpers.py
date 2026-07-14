from datetime import datetime, timezone, timedelta


def format_number(value: int | float | None) -> str:
    if value is None:
        return "0"

    return f"{int(value):,}".replace(",", ".")


def calculate_ratio(kills: int | float, deaths: int | float) -> float:
    if deaths <= 0:
        return round(kills, 2)

    return round(kills / deaths, 2)


def now_utc():
    return datetime.now(timezone.utc)


def start_of_today_utc_iso():
    now = now_utc()
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return start.isoformat()


def start_of_week_utc_iso():
    now = now_utc()
    start = now - timedelta(days=7)
    return start.isoformat()


def clean_albion_timestamp(timestamp: str):
    if not timestamp:
        return now_utc().isoformat()

    return timestamp.replace("Z", "+00:00")

def get_event_id(event: dict) -> str:
    event_id = event.get("EventId")

    if event_id:
        return str(event_id)

    killer = event.get("Killer", {}).get("Name", "unknown")
    victim = event.get("Victim", {}).get("Name", "unknown")
    timestamp = event.get("TimeStamp", "unknown")

    return f"{killer}-{victim}-{timestamp}"


def get_weapon_from_event(event: dict) -> str:
    equipment = event.get("Killer", {}).get("Equipment", {})
    main_hand = equipment.get("MainHand") or {}

    return main_hand.get("Type") or "Desconocida"


def get_killer_name(event: dict) -> str:
    return event.get("Killer", {}).get("Name") or "Desconocido"


def get_victim_name(event: dict) -> str:
    return event.get("Victim", {}).get("Name") or "Desconocido"


def calculate_longest_killstreak(events) -> int:
    current = 0
    best = 0

    for event in events:
        if event["event_type"] == "kill":
            current += 1
            best = max(best, current)
        elif event["event_type"] == "death":
            current = 0

    return best