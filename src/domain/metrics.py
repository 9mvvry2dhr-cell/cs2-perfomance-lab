def calculate_kd(kills: int, deaths: int) -> float:
    """Расчет K/D ratio."""
    return round(kills / max(1, deaths), 2)


def calculate_adr(damage: float, rounds_played: int) -> float:
    """Расчет среднего урона за раунд."""
    if rounds_played <= 0:
        return 0.0
    return round(damage / rounds_played, 1)


def calculate_hs_percent(headshots: int, kills: int) -> float:
    """Расчет процента попаданий в голову."""
    if kills <= 0:
        return 0.0
    return round((headshots / kills) * 100, 1)