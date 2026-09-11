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