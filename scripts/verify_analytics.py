import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import SessionLocal
from src.database.models import PlayerModel
from src.services.player_analytics import PlayerAnalyticsService


def main():
  session = SessionLocal()
  analytics_service = PlayerAnalyticsService(session)

  # Ищем игрока по никнейму, чтобы динамически получить Steam ID
  TARGET_NICKNAME = "kbn_san"
  target_player = (
      session.query(PlayerModel)
      .filter(PlayerModel.name == TARGET_NICKNAME)
      .first()
  )

  if not target_player:
    print(
        f"❌ Игрок с никнеймом '{TARGET_NICKNAME}' не найден в базе данных."
    )
    session.close()
    return

  # Передаем найденный Steam ID в сервис аналитики
  steam_id = target_player.steam_id
  summary = analytics_service.get_player_summary(steam_id)

  print("=" * 60)
  print(f"📊 СВОДНЫЙ ПРОФИЛЬ ИГРОКА: {summary['nickname']}")
  print(f"🆔 Steam ID: {summary['steam_id']}")
  print("=" * 60)
  print(
      f"🎮 Сыграно матчей: {summary['matches_played']} | Всего раундов:"
      f" {summary['rounds_played']}"
  )
  print(
      f"⚔️ K/D Ratio: {summary['kd_ratio']} ({summary['total_kills']}/"
      f"{summary['total_deaths']}/{summary['total_assists']})"
  )
  print(f"💥 Средний ADR: {summary['avg_adr']}")
  print(
      f"💣 HE Урон: {summary['total_he_damage']} | Molotov Урон:"
      f" {summary['total_molotov_damage']}"
  )
  print(
      f"⚡ Ослеплено врагов: {summary['total_enemies_flashed']}"
      f" ({summary['total_flash_duration']} сек)"
  )
  print(
      f"🎯 Entry K/D: {summary['entry_kd']} ({summary['entry_kills']}/"
      f"{summary['entry_deaths']})"
  )
  print(f"🏆 Клатчей выиграно: {summary['clutches_won']}")
  print("=" * 60)

  session.close()


if __name__ == "__main__":
  main()