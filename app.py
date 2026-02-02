import streamlit as st
from openai import OpenAI

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Coach Alex", page_icon="🇬🇧", layout="centered")

# --- ПРОВЕРКА КЛЮЧА ---
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Пожалуйста, добавьте API Key в настройки Streamlit (Secrets).")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ ---
if "step" not in st.session_state:
    st.session_state.step = "registration"
if "user_info" not in st.session_state:
    st.session_state.user_info = {}
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- ЭТАП 1: АНКЕТА ---
if st.session_state.step == "registration":
    st.title("🇬🇧 IELTS Coach Alex")
    st.markdown("Привет! Я Алекс, твой персональный тренер. Давай познакомимся, чтобы я составил программу.")

    with st.form("registration_form"):
        name = st.text_input("Как тебя зовут?", placeholder="Например: Max")
        
        st.write("📊 **Твой текущий уровень**")
        level = st.select_slider(
            "Выбери уровень:",
            options=["Beginner (A1-A2)", "Intermediate (B1-B2)", "Advanced (C1-C2)"]
        )
        
        target = st.selectbox("Какая цель по IELTS?", ["Band 6.0", "Band 6.5", "Band 7.0", "Band 7.5", "Band 8.0+"])
        
        submitted = st.form_submit_button("Start Training 🚀")

        if submitted and name:
            st.session_state.user_info = {"name": name, "level": level, "target": target}
            st.session_state.step = "chat"
            st.rerun()

# --- ЭТАП 2: ЧАТ С "АЛЕКСОМ" ---
elif st.session_state.step == "chat":
    user = st.session_state.user_info
    
    # Сайдбар
    with st.sidebar:
        st.header(f"Student: {user['name']}")
        st.write(f"🎯 Goal: {user['target']}")
        if st.button("Reset Progress"):
            st.session_state.step = "registration"
            st.session_state.messages = []
            st.rerun()

    st.title("Chat with Alex 🇬🇧")

    # --- ЖИВОЙ ПРОМПТ (СЕКРЕТ ЧЕЛОВЕЧНОСТИ) ---
    system_prompt = f"""
    Role: You are Alex, a friendly and energetic IELTS coach from London. 
    Student: {user['name']} (Level: {user['level']}, Target: {user['target']}).

    TONE & STYLE:
    - Be HUMAN! Use conversational fillers like "Hmm", "Got it!", "Let's see", "Brilliant".
    - BE SHORT! Maximum 2-3 sentences per message. Treat this like a WhatsApp chat, not an email.
    - NO ROBOTIC PHRASES. Never say "As an AI" or "In conclusion".
    - BE SUPPORTIVE. If the student makes a mistake, say: "Close! But a native speaker would say..."

    INSTRUCTION:
    1. Start by explicitly asking what they want to practice today: Speaking, Writing ideas, or Vocabulary.
    2. Ask ONE question at a time. Wait for the answer.
    3. Keep it casual but educational.
    """

    # Первое сообщение (если чат пуст)
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "system", "content": system_prompt})
        welcome = f"Hi {user['name']}! Alex here. 👋 \n\nWow, aiming for {user['target']}? I love that ambition! Let's get to work.\n\nWhat do you want to crush today: **Speaking**, **Writing**, or just some **tricky Vocabulary**?"
        st.session_state.messages.append({"role": "assistant", "content": welcome})

    # Вывод переписки
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Обработка ввода
    if prompt := st.chat_input("Type your answer here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
                temperature=0.7  # <--- ВОТ ЭТО ДОБАВЛЯЕТ КРЕАТИВНОСТИ
            )
            response = st.write_stream(stream)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
