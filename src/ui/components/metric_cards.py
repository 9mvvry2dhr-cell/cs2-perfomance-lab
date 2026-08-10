import streamlit as st
from typing import Dict, Any


def render_metric_cards(stats: Dict[str, Any]) -> None:
    """Отображает блок с ключевыми метриками игрока."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Матчей сыграно", value=int(stats.get("total_matches", 0)))

    with col2:
        st.metric(label="Средний K/D", value=float(stats.get("avg_kd", 0.0)))

    with col3:
        st.metric(label="Средний ADR", value=float(stats.get("avg_adr", 0.0)))

    with col4:
        st.metric(label="Попаданий в голову (% HS)", value=f"{stats.get('avg_hs', 0.0)}%")