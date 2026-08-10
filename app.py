import streamlit as st
from src.config.settings import APP_TITLE, APP_ICON
from src.database.connection import init_db
from src.ui.sidebar import render_sidebar
from src.ui.dashboard import render_dashboard

# Настройка страницы
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
)

# 1. Инициализация БД при запуске
init_db()

# 2. Рендер боковой панели
render_sidebar()

# 3. Рендер главного экрана
render_dashboard()