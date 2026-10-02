# CS2 Performance Lab — Project Handoff

Updated: 2026-10-02

Этот файл нужен, чтобы продолжить разработку с другим AI, другим разработчиком
или после долгого перерыва без необходимости восстанавливать весь контекст.

## Project

CS2 Performance Lab — сервис анализа CS2 `.dem`.

Основной flow:

Steam login
→ upload demo
→ analysis job
→ worker
→ parser
→ metrics
→ PostgreSQL
→ API
→ frontend

Domain:
https://cs2lab.ru

## Stack

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL 17
- Docker Compose
- Caddy
- Vanilla HTML / CSS / JS
- Steam OpenID
- OpenAI API for AI Coach

## Server

Project:

/opt/cs2-performance-lab

Staging:

compose.staging.yml
deploy/staging.env

ВАЖНО:
deploy/staging.env содержит секреты и не должен попадать в Git.

## Docker

Использовать:

docker compose \
  --env-file deploy/staging.env \
  -f compose.staging.yml \
  ...

Health:

docker compose \
  --env-file deploy/staging.env \
  -f compose.staging.yml \
  exec -T api \
  python -c \
  'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/ready").read().decode())'

Ожидается:

{"status":"ready"}

## Deploy frontend / API

Frontend запекается в API image.

После изменений frontend/index.html или src/api:

docker compose \
  --env-file deploy/staging.env \
  -f compose.staging.yml \
  build api

docker compose \
  --env-file deploy/staging.env \
  -f compose.staging.yml \
  up -d --no-deps api

## Deploy worker

После изменений worker/parser/metrics:

docker compose \
  --env-file deploy/staging.env \
  -f compose.staging.yml \
  build worker

docker compose \
  --env-file deploy/staging.env \
  -f compose.staging.yml \
  up -d --no-deps worker

## Auth

Steam OpenID.

Routes:

/auth/steam/login
/auth/steam/callback
/auth/logout
/me

Production identity должна идти через Steam session.

CURRENT_USER_STEAM_ID — только development fallback.

## Match sources

Premier и FACEIT считаются отдельно.

Не смешивать историю Premier и FACEIT.

FACEIT поддерживает .dem.zst.

## Free product

Free analytics сейчас заморожена.

В Free:

- demo analysis
- K/D
- ADR
- KAST
- Entry
- Utility
- Trades
- Clutches
- CT/T comparison
- Key Conclusion
- Player DNA
- Repeated Signals
- Match Story
- Смотреть первым

Не добавлять крупные новые блоки в Free без отдельного продуктового решения.

## Player DNA

История Premier / FACEIT разделена.

matches >= 10 означает зрелость профиля.

10 — threshold, а не обязательное точное окно матчей.

## Match Story

До 3 событий:

- Сильный момент
- Зона роста
- Ключевой эпизод

Watch-first priority:

growth
→ key
→ highlight
→ fallback

## Presence

Endpoints:

POST /presence/heartbeat
GET /presence/summary

Public UI:

N онлайн · N за 24ч

Online window около 90 секунд.

Heartbeat около 45 секунд.

Visitor identity основан на browser/localStorage visitor_id.

Incognito может считаться отдельным visitor.

IP/User-Agent в presence table не сохраняются.

## Founding Tester

Первые 10 участников.

Награда:

FOUNDING TESTER #N навсегда
+
30 дней Premium после релиза

Автоматическая выдача происходит после успешного анализа демки.

Worker вызывает:

claim_founding_tester()

Первый свободный slot выдаётся автоматически.

Один Steam ID не может получить два номера.

PostgreSQL concurrency защищена:

FOR UPDATE SKIP LOCKED
+
UNIQUE steam_id

Table:

founding_testers

Fields:

number
steam_id
awarded_at
premium_days

Slots:

1..10

## Founding Tester current state

#1 вручную выдан раннему тестеру maxabear.

Следующий автоматический пользователь получает #2.

На 2026-10-02:

claimed = 1
remaining = 9

Актуально проверить:

curl -sS https://cs2lab.ru/founding-testers/summary

## Founding Tester badge

/me возвращает:

founding_tester_number

Если номер есть, sidebar показывает:

★ FOUNDING TESTER #N

## Founding Admin

Protected endpoint:

GET /admin/founding-testers

Admin определяется через:

ADMIN_STEAM_ID

из deploy/staging.env.

Expected:

guest → 401
other Steam → 403
admin Steam → 200

Frontend admin card показывается только при 200.

Карточка содержит:

- claimed / total
- remaining
- Founding Tester number
- Steam ID
- awarded date
- premium_days

Нельзя делать Steam ID списка публичными.

## Premium future

Не создавать второй сайт.

Free и Premium должны жить в одном продукте.

Будущая модель примерно:

subscription_tier = free | premium
premium_until = timestamp | null

Premium candidates:

- deeper episode analysis
- 3 focus areas for next matches
- progress before/after
- style change tracking
- expanded repeated patterns
- multi-match AI Coach
- more frequent AI analysis

## Founding Premium promise

founding_testers.premium_days = 30

Это пока entitlement, а не активная подписка.

Когда появится Premium:

Founding Tester #1..#10
обязательно должны получить 30 дней Premium после релиза.

## AI

AI — слой поверх deterministic analytics.

Отсутствие OpenAI API не должно ломать базовый demo analysis.

Relevant env:

OPENAI_API_KEY
OPENAI_MODEL
AI_COACH_ENABLED
AI_OVERVIEW_COOLDOWN_DAYS

## Recent migrations

d2e4f6a8c1b3 — Match Story
f4a6c8e2d1b3 — Presence
b7d3e9a1c5f2 — Founding Tester

## Tests

Минимальный текущий suite:

python -m unittest \
  tests.unit.test_founding_tester_admin_api \
  tests.unit.test_analysis_job_repository \
  tests.unit.test_presence_api

Последний результат:

Ran 28 tests
OK

Перед большим release запускать полный pytest suite.

## Important infrastructure notes

Containers hardened:

read_only: true
user: 10001:10001
cap_drop: ALL
no-new-privileges

Не рассчитывать на запись в container root filesystem.

Frontend изменения требуют rebuild API.

Worker/source изменения требуют rebuild worker.

## Git safety

НЕ коммитить:

deploy/staging.env
.env
API keys
passwords
backups/

Не использовать бездумно:

git add .

Перед commit:

git status --short
git diff --check

Current working branch historically:

feature/staging-deploy

Всегда сначала проверить реальный branch.

## Product rules

1. Сначала factual data.
2. Потом deterministic interpretation.
3. Потом AI.
4. Не выдавать слабую выборку за устойчивый паттерн.
5. Не перегружать Free.
6. Делать маленькие изменения.
7. После изменения запускать тесты.
8. Не переписывать работающий проект с нуля.

## Next roadmap

1. Получить первых реальных Founding Testers.
2. Собрать feedback.
3. Исправить beta bugs.
4. Не расширять Free без необходимости.
5. Спроектировать subscriptions / entitlements.
6. Реализовать Premium поверх текущего продукта.
7. Учесть Founding Tester premium_days.
8. Подключить payment.
9. Подготовить production release.

## How to continue with another AI

Передать:

PROJECT_HANDOFF.md

и вывод:

git status --short
git log -10 --oneline --decorate

Затем давать одну конкретную задачу за раз:

задача
→ изменение
→ тест
→ deploy
→ проверка
→ следующая задача
