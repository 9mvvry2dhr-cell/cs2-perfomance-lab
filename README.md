# CS2 Performance Lab

CS2 Performance Lab — backend для детерминированного анализа матчей Counter-Strike 2.

Проект принимает `.dem`-файлы, парсит их, считает проверенные игровые метрики,
формирует детерминированные findings, сохраняет результат в PostgreSQL
и отдаёт его через FastAPI.

## Главный принцип

> Анализируем данные, а не гадаем.

Приоритеты проекта:

1. Достоверность данных
2. Воспроизводимость расчётов
3. Понятная аналитика
4. UI и AI-объяснения

AI должен объяснять уже проверенные данные, а не придумывать статистику.

## Текущий pipeline

```text
Загрузка .dem
    ↓
Локальное хранилище demo
    ↓
Analysis Job в PostgreSQL
    ↓
Worker
    ↓
demoparser2
    ↓
DemoParser / DTO
    ↓
Метрики
    ↓
Findings
    ↓
MatchAnalysis
    ↓
PostgreSQL
    ↓
FastAPI
```

## Требования

- Python 3.12
- PostgreSQL
- Git

Проверенное окружение разработки: Python 3.12.0.

## Установка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
```

## Конфигурация

Обязательная переменная окружения: `DATABASE_URL`.

Дополнительные переменные:

```text
DEMO_STORAGE_DIR=data/uploads
ANALYSIS_WORKER_POLL_SECONDS=2.0
```

`.env.example` содержит пример конфигурации. Приложение не загружает `.env` автоматически.

## База данных

```powershell
alembic upgrade head
alembic current
```

## Запуск API

```powershell
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Проверки: `GET /health` и `GET /ready`.

## Запуск worker

```powershell
python -m src.workers.runner
```

## Тесты

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Проверенный baseline: **148 tests, OK**.

Golden demo задаётся через `CS2_GOLDEN_MIRAGE_DEMO` и в Git не хранится.

## Что ещё не готово для production

- восстановление зависших `processing` jobs
- автоматическое удаление raw `.dem`
- retention policy
- deduplication по SHA256
- улучшение транзакционной целостности
- object storage
- CI
- deployment
- monitoring и observability
