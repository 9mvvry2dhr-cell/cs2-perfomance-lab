from typing import List, Dict, Any


class CoachService:
    """Генерирует персональные рекомендации и вердикт по игре."""

    @staticmethod
    def analyze_player_performance(history_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not history_data:
            return {}

        total_matches = len(history_data)
        
        # Считаем средние показатели
        avg_kd = sum(m["kd"] for m in history_data) / total_matches
        avg_adr = sum(m["adr"] for m in history_data) / total_matches
        
        total_kills = sum(m["kills"] for m in history_data)
        total_hs = sum(round((m["hs_percent"] / 100) * m["kills"]) for m in history_data)
        avg_hs_pct = (total_hs / max(1, total_kills)) * 100

        # Анализируем дуэли и размены (FK / FD)
        total_fk = sum(m.get("first_kills", 0) for m in history_data)
        total_fd = sum(m.get("first_deaths", 0) for m in history_data)
        opening_ratio = total_fk / max(1, total_fd) if (total_fk + total_fd) > 0 else 1.0

        strengths = []
        weaknesses = []
        recommendations = []

        # --- 1. Анализ стрельбы и урона ---
        if avg_adr >= 85:
            strengths.append(f"**Высокий импакт урона (ADR {avg_adr:.1f}):** Ты постоянно создаешь давление и наносишь много урона в раундах.")
        elif avg_adr < 70:
            weaknesses.append(f"**Низкий средний урон (ADR {avg_adr:.1f}):** Тебе не хватает подключаемости к дуэлям или плотности огня.")
            recommendations.append("Попробуй играть ближе к партнерам по команде для совместного приема позиций и ретейков.")

        if avg_hs_pct >= 55:
            strengths.append(f"**Отличный Crosshair Placement (%HS {avg_hs_pct:.1f}%):** Прицел держится на уровне головы, что обеспечивает быстрые фраги.")
        elif avg_hs_pct < 35:
            weaknesses.append(f"**Слабый процент попаданий в голову (%HS {avg_hs_pct:.1f}%):** Много спрея уходит в тело или ноги.")
            recommendations.append("Удели 10-15 минут на Prefire-картах или YPrac для тренировки контроля высоты прицела.")

        # --- 2. Анализ первыми дуэлей (Opening Duels) ---
        if opening_ratio >= 1.2:
            strengths.append(f"**Доминация в первых дуэлях (FK/FD {opening_ratio:.2f}):** Ты часто открываешь раунды в пользу своей команды.")
        elif opening_ratio <= 0.8 and (total_fk + total_fd) > 5:
            weaknesses.append(f"**Частые отдачи на старте (First Deaths {total_fd}):** Ты часто умираешь первым, оставляя команду в меньшинстве 4v5.")
            recommendations.append("Уменьши агрессивные пики без поддержки гранат или жди светошумовые флешки от напарников.")

        # --- 3. Стабильность K/D ---
        if avg_kd >= 1.2:
            strengths.append(f"**Высокая выживаемость (K/D {avg_kd:.2f}):** Ты эффективно размениваешься и грамотно выбираешь позиции.")
        elif avg_kd < 0.9:
            weaknesses.append(f"**Проблемы с разменами (K/D {avg_kd:.2f}):** Выходы на соперника происходят без поддержки или вне таймингов.")

        # Запасные дефолтные тексты
        if not strengths:
            strengths.append("**Стабильная база:** Ты показываешь средние, уверенные результаты без явных провалов.")
        if not weaknesses:
            weaknesses.append("**Явных критических ошибок не обнаружено:** Базовые показатели находятся на хорошем уровне.")
        if not recommendations:
            recommendations.append("Продолжай поддерживать текущий темп и увеличивай выборку сыгранных матчей.")

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
        }