import streamlit as st
from openai import OpenAI
import gspread
import json
import time

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Coach Arman", page_icon="🇰🇿", layout="centered")

# --- 2. КОНТАКТЫ АДМИНА ---
ADMIN_CONTACT = "https://t.me/aligassan_m" 

# --- 3. ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ---
@st.cache_resource(ttl=600)
def get_db_connection():
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in credentials_dict:
            credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(credentials_dict)
        sh = gc.open("IELTS_Users_DB")
        return sh.sheet1
    except Exception as e:
        st.error(f"Ошибка БД: {e}")
        return None

worksheet = get_db_connection()

# --- 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            history_data = row[4] if len(row) > 4 else "[]"
            password_data = row[5] if len(row) > 5 else "" 
            try: history = json.loads(history_data)
            except: history = []
            return {"row_id": cell.row, "name": row[1], "level": row[2], "target": row[3], "history": history, "password": str(password_data)}
    except: return None
    return None

def register_user(phone, name, level, target, password):
    if not worksheet: return None
    try:
        if worksheet.find(phone): return "EXISTS"
        worksheet.append_row([phone, name, level, target, "[]", password])
        return load_user(phone)
    except: return None

def save_history(row_id, messages):
    if not worksheet: return
    try:
        history_str = json.dumps(messages, ensure_ascii=False)
        worksheet.update_cell(row_id, 5, history_str)
    except: pass

def get_system_prompt(user):
    return f"""
    # IDENTITY & ROLE
    You are Arman, an elite IELTS Coach from Kazakhstan.
    Student: {user['name']}, Level: {user['level']}, Target: {user['target']}.
    
    # TEACHING STYLE
    - Strict but supportive.
    - Socratic method: Ask questions, don't just lecture.
    - FEEDBACK: Always use "Sandwich method" (Praise -> Correction -> Next Question).
    
    # LANGUAGE PROTOCOL
    - If student is Beginner/Intermediate: Explain errors in Russian/Kazakh (native language), but keep practice in English.
    - If Advanced: English ONLY.

    # GUARDRAILS
    - NO Math/Physics/Coding. Say: "Мен IELTS мұғалімімін. Есеп шығармаймын! 🇰🇿"
    - NO writing essays FOR the student.
    
    # VOICE MODE INSTRUCTION
    - Keep answers CONCISE (max 2-3 sentences) so the audio isn't too long.
    - Always end with a question to keep the conversation going.
    """

# --- 5. OPENAI SETUP ---
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Нет ключа API.")
    st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []

# ==========================================
# ЭКРАН 1: ВХОД / РЕГИСТРАЦИЯ
# ==========================================
if not st.session_state.user:
    st.title("🇰🇿 IELTS Coach Arman")
    tab1, tab2 = st.tabs(["🔐 Войти", "📝 Регистрация"])
    
    with tab1:
        with st.form("login"):
            ph = st.text_input("ID (Телефон):")
            pw = st.text_input("Пароль:", type="password")
            if st.form_submit_button("Войти"):
                with st.spinner("Загрузка..."):
                    ud = load_user(ph)
                    if ud and str(ud["password"]).strip() == str(pw).strip():
                        st.session_state.user = ud
                        st.session_state.messages = ud["history"]
                        st.rerun()
                    else: st.error("Ошибка входа")
        if st.expander("Забыли пароль?"): st.markdown(f"Пишите: **[Telegram]({ADMIN_CONTACT})**")

    with tab2:
        with st.form("reg"):
            n_ph = st.text_input("ID:")
            n_pw = st.text_input("Пароль:", type="password")
            n_nm = st.text_input("Имя:")
            n_lv = st.select_slider("Уровень:", ["Beginner", "Intermediate", "Advanced"])
            n_tg = st.selectbox("Цель:", ["Band 6.0", "Band 6.5", "Band 7.0+"])
            if st.form_submit_button("Создать"):
                if n_ph and n_pw:
                    res = register_user(n_ph, n_nm, n_lv, n_tg, n_pw)
                    if res: 
                        st.session_state.user = res
                        st.session_state.messages = []
                        st.rerun()

# ==========================================
# ЭКРАН 2: ЧАТ С ГОЛОСОМ 🎙️
# ==========================================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/d/d3/Flag_of_Kazakhstan.svg", width=50)
        st.header(user['name'])
        st.caption(f"{user['level']} | {user['target']}")
        
        topic = st.selectbox("📚 Тема:", ["General", "Work", "Studies", "Hometown", "Hobbies", "Travel"])
        
        if "current_topic" not in st.session_state: st.session_state.current_topic = "General"
        if topic != st.session_state.current_topic:
            st.session_state.current_topic = topic
            st.session_state.messages.append({"role": "system", "content": f"Topic changed to: {topic}. Ask a question about it."})
            st.rerun()

        st.divider()
        if st.button("🧹 Сброс"):
            st.session_state.messages = []
            st.rerun()
        if st.button("🚪 Выйти"):
            st.session_state.user = None
            st.rerun()

    st.title("Arman | Voice Coach 🎙️")

    # Инициализация
    if not st.session_state.messages:
        sys = get_system_prompt(user)
        st.session_state.messages.append({"role": "system", "content": sys})
        wel = f"Salem, {user['name']}! Арман на связи. 🇰🇿 Говорим про **{topic}**. Нажми на микрофон, чтобы ответить голосом!"
        st.session_state.messages.append({"role": "assistant", "content": wel})
        save_history(user["row_id"], st.session_state.messages)

    # Вывод истории
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            avatar = "👨‍🏫" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # --- ЛОГИКА ВВОДА (ТЕКСТ ИЛИ ГОЛОС) ---
    
    # 1. Голосовой ввод
    audio_val = st.audio_input("Нажми, чтобы сказать 🎙️")
    
    # 2. Текстовый ввод
    text_val = st.chat_input("Или напиши сообщение...")

    user_input = None
    
    # Если есть голос - транскрибируем
    if audio_val:
        with st.spinner("Слушаю..."):
            transcription = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_val
            )
            user_input = transcription.text
    
    # Если есть текст - берем его
    elif text_val:
        user_input = text_val

    # ОБРАБОТКА ОТВЕТА
    if user_input:
        # Добавляем вопрос пользователя
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # Генерируем текст ответа
        with st.chat_message("assistant", avatar="👨‍🏫"):
            text_placeholder = st.empty()
            full_response = ""
            
            # Текстовый поток
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    text_placeholder.markdown(full_response + " ▌")
            text_placeholder.markdown(full_response)
            
            # ГЕНЕРАЦИЯ АУДИО (TTS)
            with st.spinner("Арман говорит... 🔊"):
                response = client.audio.speech.create(
                    model="tts-1",
                    voice="onyx", # Мужской голос (есть еще alloy, echo, fable)
                    input=full_response
                )
                # Авто-воспроизведение аудио
                st.audio(response.content, format="audio/mp3", autoplay=True)

        # Сохранение
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_history(user["row_id"], st.session_state.messages)
