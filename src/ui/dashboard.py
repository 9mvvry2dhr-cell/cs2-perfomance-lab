import streamlit as st
from src.database.matches import get_all_matches
from src.domain.metrics import calculate_player_aggregates
from src.ui.components.metric_cards import render_metric_cards


def render_dashboard() -> None:
    """Отображает главный экран аналитики."""
    st.header("🎯 Общая аналитика формы")

    # 1. Получаем все матчи из БД
    matches = get_all_matches()

    if not matches:
        st.info("В базе данных пока нет сохранённых матчей. Загрузите `.dem` файл через боковое меню!")
        return

    # 2. Собираем уникальных игроков
    player_names = {}
    for m in matches:
        for p in m.players:
            player_names[p.steam_id] = p.name

    if not player_names:
        # Если игроков нет в структуре, считаем общее число матчей
        aggregated_stats = calculate_player_aggregates([], total_matches=len(matches))
        render_metric_cards(aggregated_stats)
    else:
        # 3. Выпадающий список выбора игрока
        selected_steam_id = st.selectbox(
            "Выберите игрока для анализа:",
            options=list(player_names.keys()),
            format_func=lambda x: player_names[x]
        )

        # 4. Фильтруем статистику под выбранного игрока
        selected_player_stats = []
        player_matches_count = 0

        for m in matches:
            player_in_match = [p for p in m.players if p.steam_id == selected_steam_id]
            if player_in_match:
                selected_player_stats.extend(player_in_match)
                player_matches_count += 1

        # 5. Расчет метрик
        aggregated_stats = calculate_player_aggregates(
            selected_player_stats, 
            total_matches=player_matches_count
        )
        render_metric_cards(aggregated_stats)

    st.markdown("---")
    st.subheader("История матчей")
    
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