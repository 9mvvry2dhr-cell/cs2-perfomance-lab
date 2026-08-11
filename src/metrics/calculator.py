class MetricsCalculator:
    @staticmethod
    def calculate_rating(kills: int, deaths: int, damage: float, rounds_played: int) -> float:
        if rounds_played <= 0:
            return 1.0

        # Базовые показатели за раунд
        kpr = kills / rounds_played
        dpr = deaths / rounds_played
        adr = damage / rounds_played

        # Приближенная формула HLTV 1.0 / 2.0
        impact = 2.13 * kpr + 0.42 * (kills / (deaths if deaths > 0 else 1)) - 0.41
        rating = (0.0073 * adr) + (0.3591 * kpr) - (0.5329 * dpr) + (0.2372 * impact) + 0.1587

        return round(max(0.0, rating), 2)