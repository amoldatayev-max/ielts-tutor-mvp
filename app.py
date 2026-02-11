import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="ZEST AI | ALAN Coach", page_icon="⚡️", layout="centered")

# --- 2. CSS: ИСПРАВЛЕНИЕ ИНТЕРФЕЙСА ---
# Этот блок поднимает микрофон ВЫШЕ текстового поля
sticky_style = """
<style>
    /* Скрываем стандартное меню Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* НАСТРОЙКА МИКРОФОНА (плавающий блок) */
    [data-testid="stAudioInput"] {
        position: fixed;
        bottom: 130px; /* Высота над полом (над полем ввода текста) */
        z-index: 999;
        left: 0;
        right: 0;
        margin-left: auto;
        margin-right: auto;
        width: 100%;
        max-width: 44rem; /* Ширина как у основной колонки */
        
        /* Фон плашки микрофона (чтобы не сливался) */
        background-color: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 10px;
        box-shadow: 0px -2px 10px rgba(0,0,0,0.1);
    }
    
    /* Темная тема для микрофона */
    @media (prefers-color-scheme: dark) {
        [data-testid="stAudioInput"] {
            background-color: rgba(38, 39, 48, 0.95);
            border: 1px solid #444;
        }
    }
    
    /* Отступ снизу для чата, чтобы последние сообщения не прятались */
    .stMainBlockContainer {
        padding-bottom: 250px;
    }
</style>
"""
st.markdown(sticky_style, unsafe_allow_html=True)

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
    except: return None

worksheet = get_db_connection()

# --- 4. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            hist = row[4] if len(row) > 4 else "[]"
            pwd = row[5] if len(row) > 5 else "" 
            lang = row[6] if len(row) > 6 else "English" 
            try: h = json.loads(hist)
            except: h = []
            return {"row_id": cell.row, "name": row[1], "level": row[2], "target": row[3], "history": h, "password": str(pwd), "native_lang": lang}
    except: return None

def register_user(phone, name, level, target, password, native_lang):
    if not worksheet: return None
    try:
        if worksheet.find(phone): return "EXISTS"
        worksheet.append_row([phone, name, level, target, "[]", password, native_lang])
        return load_user(phone)
    except: return None

def save_history(row_id, messages):
    if not worksheet: return
    try: worksheet.update_cell(row_id, 5, json.dumps(messages, ensure_ascii=False))
    except: pass

def get_word_of_the_day():
    words = [
        ("Ubiquitous", "Вездесущий (Everywhere)"),
        ("Ephemeral", "Мимолетный (Short-lived)"),
        ("Eloquent", "Красноречивый (Persuasive)"),
        ("Resilient", "Устойчивый (Strong)"),
        ("Meticulous", "Тщательный (Careful)"),
        ("Inevitable", "Неизбежный (Unavoidable)"),
        ("Alleviate", "Облегчить (Make easier)")
    ]
    return random.choice(words)

# --- 5. НАСТРОЙКА OPENAI ---
if "OPENAI_API_KEY" not in st.secrets: st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ИНИЦИАЛИЗАЦИЯ СЕССИИ ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []
if "wod" not in st.session_state: st.session_state.wod = get_word_of_the_day()

# ==================== ЭКРАН 1: ВХОД / РЕГИСТРАЦИЯ ====================
if not st.session_state.user:
    st.title("⚡️ ZEST AI | ALAN")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login"):
            ph = st.text_input("ID (Phone):")
            pw = st.text_input("Password:", type="password")
            if st.form_submit_button("Start Learning"):
                ud = load_user(ph)
                if ud and str(ud["password"]).strip() == str(pw).strip():
                    st.session_state.user = ud
                    st.session_state.messages = ud["history"]
                    st.rerun()
                else: st.error("Incorrect ID or Password")
    
    with tab2:
        with st.form("reg"):
            st.caption("Create New Profile")
            n_ph = st.text_input("ID (Phone):")
            n_pw = st.text_input("Password:", type="password")
            n_nm = st.text_input("Name:")
            n_la = st.selectbox("Native Language:", ["Kazakh", "Russian", "English", "Chinese", "Hindi", "Spanish"])
            n_lv = st.select_slider("Level:", ["Beginner", "Intermediate", "Advanced"])
            n_tg = st.selectbox("Target Band:", ["6.0", "6.5", "7.0+"])
            
            if st.form_submit_button("Create Profile"):
                r = register_user(n_ph, n_nm, n_lv, n_tg, n_pw, n_la)
                if r: 
                    st.session_state.user = r
                    st.session_state.messages = []
                    st.rerun()

# ==================== ЭКРАН 2: ЧАТ С АЛАНОМ ====================
else:
    user = st.session_state.user
    
    # --- БОКОВАЯ ПАНЕЛЬ ---
    with st.sidebar:
        st.info(f"💡 **Word of the Day:**\n\n**{st.session_state.wod[0]}**\n_{st.session_state.wod[1]}_")
        
        # Прогресс
        user_msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
        st.progress(min(user_msg_count / 50, 1.0))
        st.caption(f"XP: {user_msg_count} actions")
        
        st.divider()
        st.caption(f"Student: **{user['name']}**")
        st.caption(f"Language: **{user['native_lang']}**")
        
        # Скачивание
        chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
        st.download_button("📥 Download Lesson", chat_text, file_name="lesson.txt")
        
        st.divider()
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("ZEST AI | ALAN ⚡️")

    # --- ИНИЦИАЛИЗАЦИЯ ЧАТА (ПРОМПТ) ---
    if not st.session_state.messages:
        sys = f"""
        Role: IELTS Coach ALAN. 
        Student Name: {user['name']}. 
        Native Language: {user['native_lang']}. 
        Style: Socratic, Brief (2-3 sentences max). 
        Rules: 
        1. Explain errors in Native Lang ({user['native_lang']}).
        2. Keep practice questions in English.
        3. Strict Focus on IELTS.
        4. Never end the conversation.
        """
        st.session_state.messages.append({"role": "system", "content": sys})
        st.session_state.messages.append({"role": "assistant", "content": f"Hello {user['name']}! I am ALAN. Ready to practice? (Press 🎙️ to speak)"})

    # --- ВЫВОД ИСТОРИИ ---
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            # Иконки: Алан (Компьютер/Ментор) и Ученик
            av = "👨‍💻" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

    # --- ЗОНА ВВОДА (МИКРОФОН + ТЕКСТ) ---
    # Микрофон (приклеен CSS стилем выше)
    audio_val = st.audio_input("Speak / Говорить 🎙️")
    
    # Текстовое поле (всегда внизу страницы)
    text_val = st.chat_input("Type your answer here...")

    user_in = None
    
    # Логика: Если есть аудио - берем его, иначе текст
    if audio_val:
        with st.spinner("Alan is listening..."):
            try: user_in = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
            except: st.error("Microphone error. Try typing.")
    elif text_val:
        user_in = text_val

    # --- ОБРАБОТКА ОТВЕТА ---
    if user_in:
        # 1. Показываем сообщение пользователя
        st.session_state.messages.append({"role": "user", "content": user_in})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_in)

        # 2. Алан думает и пишет
        with st.chat_message("assistant", avatar="👨‍💻"):
            full_resp = ""
            ph = st.empty()
            
            # Стрим текста
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_resp += chunk.choices[0].delta.content
                    ph.markdown(full_resp + " ▌")
            ph.markdown(full_resp)
            
            # 3. Алан говорит (TTS)
            # ВАЖНО: Используем уникальный ключ (key), чтобы плеер не исчезал
            try:
                response = client.audio.speech.create(model="tts-1", voice="onyx", input=full_resp)
                st.caption("🔊 ALAN'S VOICE:")
                st.audio(response.content, format="audio/mp3")
            except Exception as e:
                st.warning("Voice unavailable right now.")

        # 4. Сохраняем (БЕЗ RERUN!)
        st.session_state.messages.append({"role": "assistant", "content": full_resp})
        save_history(user["row_id"], st.session_state.messages)
