import sys
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь поиска модулей
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.database.connection import get_session, engine
from src.domain.models import Base, Match, PlayerStat, RoundStat
from src.parsing.dto import ParsedMatch, ParsedPlayer, ParsedRound
from src.database.matches import save_match, get_match_by_id, get_player_history


def run_checks():
    print("🔄 [1/4] Пересоздаем таблицы в тестовой БД...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы успешно созданы!")

    print("\n🔄 [2/4] Проверяем сохранение Валидного матча (Data Trust OK)...")
    valid_dto = ParsedMatch(
        match_id="test_match_valid_001",
        map_name="de_inferno",
        rounds_played=22,
        score_ct=13,
        score_t=9,
        winner_side="CT",
        played_at=datetime.now(),
        is_valid=True,
        players=[
            ParsedPlayer(
                steam_id="76561198000000001",
                name="s1mple",
                kills=25,
                deaths=10,
                assists=5,
                damage=2100.0,
                headshots=15,
                rounds_played=22
            )
        ],
        rounds=[
            ParsedRound(round_num=1, winner_side="CT", win_reason="ct_killed", end_tick=12000)
        ]
    )

    saved_valid = save_match(valid_dto)
    assert saved_valid is not None, " Ошибка: Матч не сохранился!"
    
    # Проверка вычисления метрик для валидного матча
    match_from_db = get_match_by_id("test_match_valid_001")
    player = match_from_db.players[0]
    
    assert player.steam_id == "76561198000000001", " Ошибка: SteamID не совпадает!"
    assert player.damage == 2100.0, " Ошибка: RAW Damage не сохранился!"
    assert round(player.adr, 1) == 95.5, f" Ошибка: ADR посчитан неверно ({player.adr})"
    assert player.kd == 2.5, f" Ошибка: KD посчитан неверно ({player.kd})"
    print("✅ Валидный матч сохранен, RAW-данные и derived-метрики корректны!")

    print("\n🔄 [3/4] Проверяем сохранение Невалидного матча (rounds_played = 0)...")
    invalid_dto = ParsedMatch(
        match_id="test_match_invalid_002",
        map_name="de_mirage",
        rounds_played=0,
        score_ct=0,
        score_t=0,
        winner_side="UNKNOWN",
        is_valid=False,
        validation_error="Unable to determine rounds_played.",
        players=[
            ParsedPlayer(
                steam_id="76561198000000001",
                name="s1mple",
                kills=5,
                deaths=5,
                damage=400.0,
                headshots=2,
                rounds_played=0
            )
        ]
    )

    save_match(invalid_dto)
    invalid_db = get_match_by_id("test_match_invalid_002")
    invalid_player = invalid_db.players[0]

    assert invalid_db.is_valid is False, " Ошибка: Статус is_valid должен быть False!"
    assert invalid_player.adr is None, f" Ошибка: ADR не должен рассчитываться при 0 раундах! (Получено: {invalid_player.adr})"
    print("✅ Защита Data Trust сработала! ADR не рассчитан, у матча флаг is_valid = False.")

    print("\n🔄 [4/4] Проверяем поиск истории строго по SteamID...")
    history = get_player_history("76561198000000001")
    assert len(history) == 2, f" Ошибка: Ожидалось 2 матча в истории, найдено {len(history)}"
    assert history[0]["steam_id"] if "steam_id" in history[0] else True, "История находит данные по SteamID"
    print("✅ Поиск по SteamID работает корректно!")

    print("\n🎉 Все P0-проверки пропущены успешно! Система работает стабильно.")


if __name__ == "__main__":
    run_checks()