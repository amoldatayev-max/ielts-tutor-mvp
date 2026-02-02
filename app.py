import streamlit as st
from openai import OpenAI

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Personal Coach", page_icon="🚀", layout="centered")

# --- ПРОВЕРКА КЛЮЧА ---
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Пожалуйста, добавьте API Key в настройки Streamlit (Secrets).")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ (ПАМЯТИ) ---
if "step" not in st.session_state:
    st.session_state.step = "registration" # Начальный этап - регистрация
if "user_info" not in st.session_state:
    st.session_state.user_info = {}
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- ЭТАП 1: АНКЕТА И ДИАГНОСТИКА ---
if st.session_state.step == "registration":
    st.title("🚀 Твой путь к IELTS начинается здесь")
    st.markdown("Чтобы ИИ-тренер составил персональную программу, ответьте на пару вопросов.")

    with st.form("registration_form"):
        # Личные данные
        name = st.text_input("Как к вам обращаться?", placeholder="Например: Алексей")
        contact = st.text_input("Телефон или Ник в Telegram", placeholder="@username или +7...")
        
        # Диагностика (без тестов, просто самооценка)
        st.divider()
        st.write("📊 **Диагностика уровня**")
        
        years_exp = st.slider("Сколько лет вы учите английский?", 0, 15, 2)
        
        level = st.selectbox(
            "Как вы оцениваете свой текущий уровень?",
            ["Beginner (A1-A2) - Могу рассказать о себе", 
             "Intermediate (B1-B2) - Смотрю сериалы, но делаю ошибки", 
             "Advanced (C1-C2) - Свободно говорю, нужна шлифовка"]
        )
        
        target_score = st.selectbox("Какая цель по IELTS?", ["5.5", "6.0", "6.5", "7.0", "7.5", "8.0+"])

        submitted = st.form_submit_button("Начать тренировку 🎓")

        if submitted:
            if not name or not contact:
                st.error("Пожалуйста, заполните имя и контакты.")
            else:
                # Сохраняем данные пользователя
                st.session_state.user_info = {
                    "name": name,
                    "contact": contact,
                    "years": years_exp,
                    "level": level,
                    "target": target_score
                }
                st.session_state.step = "chat" # Переключаем на чат
                st.rerun() # Перезагружаем страницу

# --- ЭТАП 2: ЧАТ С ПЕРСОНАЛЬНЫМ ТРЕНЕРОМ ---
elif st.session_state.step == "chat":
    user = st.session_state.user_info
    
    # Боковая панель с профилем
    with st.sidebar:
        st.header("👤 Профиль студента")
        st.write(f"**Имя:** {user['name']}")
        st.write(f"**Уровень:** {user['level']}")
        st.write(f"**Цель:** Band {user['target']}")
        if st.button("Начать заново"):
            st.session_state.step = "registration"
            st.session_state.messages = []
            st.rerun()

    st.title(f"Тренировка для {user['name']}")

    # --- ГЛАВНЫЙ МОЗГ (SYSTEM PROMPT) ---
    # Мы генерируем промпт динамически, подставляя данные из анкеты
    system_prompt = f"""
    Ты - персональный тренер по IELTS. Твоего студента зовут {user['name']}.
    Его самооценка уровня: {user['level']}. Опыт: {user['years']} лет.
    Его цель: IELTS Band {user['target']}.

    ТВОЯ ЗАДАЧА:
    Вести студента по всем частям экзамена (Speaking, Writing, Vocabulary).
    Не нужно читать лекции. Обучение должно идти через ПРАКТИКУ.

    АЛГОРИТМ РАБОТЫ (СТРОГО):
    1. Начни с приветствия и предложи выбрать тему или навык (например: Speaking Part 1, Essay ideas, Vocabulary).
    2. ЗАДАВАЙ ТОЛЬКО ОДИН ВОПРОС ЗА РАЗ. Не вываливай списки.
    3. Жди ответа студента.
    4. ДАЙ ОБРАТНУЮ СВЯЗЬ (Feedback Loop):
       - Сначала похвали за то, что получилось.
       - Потом укажи на ошибку (грамматика/лексика).
       - Покажи, как сказать это на уровень {user['target']} (Better version).
    5. Задай СЛЕДУЮЩИЙ вопрос, чуть сложнее, если студент справился, или проще, если нет.
    
    Стиль общения: Поддерживающий коуч, но требовательный к качеству.
    Если студент пишет на русском - отвечай на русском, но проси перевести на английский.
    """

    # Инициализация истории (если пусто)
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "system", "content": system_prompt})
        # Приветственное сообщение от бота, чтобы начать диалог первым
        welcome_msg = f"Привет, {user['name']}! Я вижу, твоя цель — {user['target']}. Давай не будем терять время. С чего хочешь начать: Speaking (разговор), Writing (эссе) или проверим твой словарный запас?"
        st.session_state.messages.append({"role": "assistant", "content": welcome_msg})

    # Вывод чата
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Ввод пользователя
    if prompt := st.chat_input("Ваш ответ..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Генерация ответа ИИ
        with st.chat_message("assistant"):
            stream = client.chat.completions.create(
                model="gpt-4o", # Убедитесь, что у вас есть доступ, или смените на gpt-3.5-turbo
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
            )
            response = st.write_stream(stream)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
