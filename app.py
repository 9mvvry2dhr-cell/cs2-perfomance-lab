from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

from src.database.connection import init_db
from src.services.demo_service import DemoService
from src.services.coach_service import CoachService
from src.database.matches import get_all_matches, get_player_history

# Инициализируем БД
init_db()

st.set_page_config(
    page_title="CS2 Performance Lab",
    page_icon="🎮",
    layout="wide"
)

# --- Боковая панель: Массовая загрузка демо ---
st.sidebar.title("CS2 Performance Lab")
st.sidebar.subheader("Загрузка матчей")

uploaded_files = st.sidebar.file_uploader(
    "Выберите один или несколько .dem файлов", 
    type=["dem"], 
    accept_multiple_files=True
)

if st.sidebar.button("Обработать демо", type="primary"):
    if uploaded_files:
        temp_dir = Path("temp_demos")
        temp_dir.mkdir(exist_ok=True)
        
        success_count = 0
        error_count = 0
        
        progress_bar = st.sidebar.progress(0)
        status_text = st.sidebar.empty()

        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Парсинг {idx + 1}/{len(uploaded_files)}: {uploaded_file.name}")
            temp_file_path = temp_dir / uploaded_file.name

            try:
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                DemoService.process_demo_file(temp_file_path)
                success_count += 1
            except Exception as e:
                st.sidebar.error(f"Ошибка в {uploaded_file.name}: {e}")
                error_count += 1
            finally:
                if temp_file_path.exists():
                    temp_file_path.unlink()
            
            progress_bar.progress((idx + 1) / len(uploaded_files))

        status_text.empty()
        progress_bar.empty()

        if success_count > 0:
            st.sidebar.success(f"Успешно обработано матчей: {success_count}")
        if error_count == 0:
            st.rerun()
    else:
        st.sidebar.warning("Пожалуйста, выберите хотя бы один файл .dem")

# --- Основной дашборд ---
st.title("🎯 Общая аналитика формы")

matches = get_all_matches()

if not matches:
    st.info("В базе данных пока нет сохранённых матчей. Загрузите `.dem` файлы через боковое меню.")
else:
    player_names = sorted(
        list({player.name for match in matches for player in match.players})
    )

    selected_player = st.selectbox("Выберите игрока для анализа:", options=player_names)

    if selected_player:
        history_data = get_player_history(selected_player)

        if history_data:
            df_history = pd.DataFrame(history_data)

            # Расчёт сводных показателей
            total_matches = len(df_history)
            avg_kd = round(df_history["kd"].mean(), 2)
            avg_adr = round(df_history["adr"].mean(), 1)
            
            total_kills = df_history["kills"].sum()
            total_hs = sum(
                round((row["hs_percent"] / 100) * row["kills"]) 
                for _, row in df_history.iterrows()
            )
            avg_hs_pct = round((total_hs / max(1, total_kills)) * 100, 1)

            # Карточки метрик
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Матчей сыграно", total_matches)
            m2.metric("Средний K/D", avg_kd)
            m3.metric("Средний ADR", avg_adr)
            m4.metric("Попаданий в голову (% HS)", f"{avg_hs_pct}%")

            st.divider()

            # --- Модуль AI Coach / Персональный тренер ---
            st.subheader("🤖 AI Coach: Вердикт и Рекомендации")
            
            coach_analysis = CoachService.analyze_player_performance(history_data)
            
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown("##### 🟢 Сильные стороны")
                for item in coach_analysis.get("strengths", []):
                    st.success(item)

            with c2:
                st.markdown("##### 🔴 Слабые места")
                for item in coach_analysis.get("weaknesses", []):
                    st.error(item)

            with c3:
                st.markdown("##### 💡 План улучшения")
                for item in coach_analysis.get("recommendations", []):
                    st.info(item)

            st.divider()

            # Интерактивные графики динамики формы (Plotly)
            st.subheader("📈 Динамика формы")
            
            if len(df_history) < 2:
                st.info("💡 Загрузите ещё хотя бы 1 матч, чтобы увидеть график динамики показателей.")
            else:
                df_history["played_at_dt"] = pd.to_datetime(df_history["played_at"])
                df_history = df_history.sort_values(by="played_at_dt").reset_index(drop=True)
                df_history["match_num"] = [f"Матч {i+1}" for i in range(len(df_history))]

                col1, col2 = st.columns(2)

                with col1:
                    fig_adr = px.line(
                        df_history, 
                        x="match_num", 
                        y="adr", 
                        markers=True,
                        title="Тренд ADR",
                        hover_data={"match_num": False, "map_name": True, "played_at": True}
                    )
                    fig_adr.update_traces(line_color="#00A3FF", marker_size=8)
                    fig_adr.update_xaxes(title_text="")
                    fig_adr.update_yaxes(title_text="ADR")
                    st.plotly_chart(fig_adr, use_container_width=True)

                with col2:
                    fig_kd = px.line(
                        df_history, 
                        x="match_num", 
                        y="kd", 
                        markers=True,
                        title="Тренд K/D",
                        hover_data={"match_num": False, "map_name": True, "played_at": True}
                    )
                    fig_kd.update_traces(line_color="#FF6B00", marker_size=8)
                    fig_kd.update_xaxes(title_text="")
                    fig_kd.update_yaxes(title_text="K/D")
                    st.plotly_chart(fig_kd, use_container_width=True)

            st.divider()

    # --- Таблица истории матчей ---
    st.subheader("История матчей")
    
    match_list = []
    for m in matches:
        match_list.append({
            "ID Матча": m.match_id,
            "Карта": m.map_name,
            "Дата": m.played_at.strftime("%Y-%m-%d %H:%M"),
            "Счёт (CT:T)": f"{m.score_ct}:{m.score_t}",
            "Победители": m.winner_side
        })
    
    st.dataframe(pd.DataFrame(match_list), use_container_width=True)