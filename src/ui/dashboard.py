import streamlit as st
from src.database.matches import get_all_matches
from src.domain.metrics import calculate_player_aggregates
from src.ui.components.metric_cards import render_metric_cards


def render_dashboard() -> None:
    """Отображает главный экран аналитики."""
    st.header("🎯 Общая аналитика формы")

    # 1. Получаем все матчи из базы данных
    matches = get_all_matches()

    if not matches:
        st.info("В базе данных пока нет сохранённых матчей. Загрузите `.dem` файл через боковое меню!")
        return

    # 2. Извлекаем статистику игроков (сейчас у нас 1 фейковый игрок на матч в парсере)
    all_player_stats = []
    for m in matches:
        all_player_stats.extend(m.players)

    # 3. Считаем математику
    aggregated_stats = calculate_player_aggregates(all_player_stats)

    # 4. Рендерим карточки
    render_metric_cards(aggregated_stats)

    st.markdown("---")
    st.subheader("История матчей")
    
    # Таблица со списком матчей
    match_data = []
    for m in matches:
        match_data.append({
            "ID Матча": m.match_id,
            "Карта": m.map_name,
            "Дата": m.played_at.strftime("%Y-%m-%d %H:%M"),
            "Счёт (CT:T)": f"{m.score_ct}:{m.score_t}",
            "Победители": m.winner_side,
        })
    
    st.dataframe(match_data, use_container_width=True)