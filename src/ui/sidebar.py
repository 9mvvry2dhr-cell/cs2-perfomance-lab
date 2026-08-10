import streamlit as st
from pathlib import Path
import tempfile
from src.services.demo_service import DemoService


def render_sidebar() -> None:
    """Отображает боковую панель для загрузки файлов и фильтров."""
    st.sidebar.title("🎮 CS2 Performance Lab")
    st.sidebar.markdown("---")

    st.sidebar.subheader("Загрузка матча")
    uploaded_file = st.sidebar.file_uploader("Выберите .dem файл", type=["dem"])

    if uploaded_file is not None:
        if st.sidebar.button("Обработать демо", type="primary"):
            with st.spinner("Парсим матч и сохраняем данные..."):
                # Сохраняем во временный файл для передачи в парсер
                with tempfile.NamedTemporaryFile(delete=False, suffix=".dem") as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_path = Path(tmp_file.name)

                try:
                    match_data = DemoService.process_demo_file(tmp_path)
                    st.sidebar.success(f"Матч на карте {match_data.map_name} успешно добавлен!")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Ошибка при обработке: {e}")
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()  # Удаляем временный файл