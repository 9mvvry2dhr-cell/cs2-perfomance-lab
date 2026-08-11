import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.parsing.demo_parser import DemoParser
from src.database.connection import init_db, SessionLocal
from src.database.repository import MatchRepository
from src.database.models import MatchModel, PlayerModel

def main():
    print("🚀 Инициализируем базу данных...")
    init_db()

    found_demos = list(PROJECT_ROOT.rglob("*.dem"))
    if not found_demos:
        print("❌ Демо-файлы не найдены.")
        return

    demo_path = found_demos[0]
    print(f"📁 Парсим демо: {demo_path.name}")

    parser = DemoParser(str(demo_path))
    parsed_match = parser.parse()

    print("💾 Сохраняем матч в SQLite...")
    session = SessionLocal()
    repo = MatchRepository(session)
    repo.save_match(parsed_match)

    print("✅ Матч успешно сохранен!")

    # Проверяем чтение из БД
    saved_match = session.query(MatchModel).filter_by(match_id=parsed_match.match_id).first()
    print(f"\n📊 Чтение из БД:")
    print(f"Матч: {saved_match.match_id} | Карта: {saved_match.map_name} | Игроков: {len(saved_match.players)}")
    
    session.close()

if __name__ == "__main__":
    main()