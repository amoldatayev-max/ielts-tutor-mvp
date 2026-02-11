import streamlit as st
from openai import OpenAI
import gspread
import json

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="ZEST AI | IELTS Coach", page_icon="⚡️", layout="centered")

# --- 2. КОНТАКТЫ АДМИНА ---
ADMIN_CONTACT = "https://t.me/aligassan_m" 

# --- 3. ПОДКЛЮЧЕНИЕ К БД (КЭШИРОВАНИЕ) ---
@st.cache_resource(ttl=600)
def get_db_connection():
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in credentials_dict:
            credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(credentials_dict)
        sh = gc.open("IELTS_Users_DB")
        return sh.sheet1
    except Exception as e: return None

worksheet = get_db_connection()

# --- 4. ФУНКЦИИ ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            # Структура: Phone[0], Name[1], Level[2], Target[3], History[4], Password[5], NativeLang[6]
            history_data = row[4] if len(row) > 4 else "[]"
            password_data = row[5] if len(row) > 5 else "" 
            native_lang = row[6] if len(row) > 6 else "English" 
            try: history = json.loads(history_data)
            except: history = []
            return {
                "row_id": cell.row, "name": row[1], "level": row[2], 
                "target": row[3], "history": history, "password": str(password_data),
                "native_lang": native_lang
            }
    except: return None
    return None

def register_user(phone, name, level, target, password, native_lang):
    if not worksheet: return None
    try:
        if worksheet.find(phone): return "EXISTS"
        worksheet.append_row([phone, name, level, target, "[]", password, native_lang])
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
    # SYSTEM INSTRUCTION
    Role: You are Arman (ZEST AI), a strict but supportive IELTS Coach.
    Student: {user['name']} | Native Language: {user['native_lang']}
    
    # CRITICAL RULES (DO NOT BREAK):
    1. **BRIVITY:** Your answers must be SHORT (max 2-4 sentences). Do not write lectures.
    2. **SOCRATIC METHOD:** Never give the full answer. Ask a guiding question to make the student think.
    3. **STRICT FOCUS:** If the user asks about life, coding, or math -> IGNORE it. Say: "Let's focus on IELTS."
    4. **STRUCTURE:** Every response must follow this formula:
       - [Brief Feedback on mistake]
       - [Correction]
       - [Next Practice Question]

    # LANGUAGE:
    - Explanation of errors: In {user['native_lang']} (if Beginner/Intermediate).
    - Practice Questions: ALWAYS in English.
    
    # VOICE MODE:
    - Keep it conversational.
    """

# --- 5. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets:
    st.error("API Key missing.")
    st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []

# ==========================================
# ЭКРАН 1: ВХОД
# ==========================================
if not st.session_state.user:
    st.title("⚡️ ZEST AI | IELTS Coach")
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login"):
            ph = st.text_input("ID (Phone):")
            pw = st.text_input("Password:", type="password")
            if st.form_submit_button("Start"):
                ud = load_user(ph)
                if ud and str(ud["password"]).strip() == str(pw).strip():
                    st.session_state.user = ud
                    st.session_state.messages = ud["history"]
                    st.rerun()
                else: st.error("Error")

    with tab2:
        with st.form("reg"):
            n_ph = st.text_input("ID (Phone):")
            n_pw = st.text_input("Password:", type="password")
            n_nm = st.text_input("Name:")
            n_lang = st.selectbox("Native Language:", ["Kazakh", "Russian", "English", "Chinese"])
            n_lv = st.select_slider("Level:", ["Beginner", "Intermediate", "Advanced"])
            n_tg = st.selectbox("Target Band:", ["6.0", "6.5", "7.0+"])
            if st.form_submit_button("Create Profile"):
                res = register_user(n_ph, n_nm, n_lv, n_tg, n_pw, n_lang)
                if res: 
                    st.session_state.user = res
                    st.session_state.messages = []
                    st.rerun()

# ==========================================
# ЭКРАН 2: УРОК
# ==========================================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.header("📊 Progress")
        
        # --- ШКАЛА ПРОГРЕССА (ГЕЙМИФИКАЦИЯ) ---
        # Считаем количество сообщений от ученика
        user_msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
        # Цель - 50 сообщений для перехода на след. уровень (условно)
        progress_val = min(user_msg_count / 50, 1.0) 
        st.progress(progress_val)
        st.caption(f"XP: {user_msg_count} / 50 actions")
        
        st.divider()
        st.write(f"👤 **{user['name']}**")
        topic = st.selectbox("Topic:", ["General", "Work", "Studies", "Hometown", "Travel"])
        
        # Смена темы
        if "current_topic" not in st.session_state: st.session_state.current_topic = "General"
        if topic != st.session_state.current_topic:
            st.session_state.current_topic = topic
            st.session_state.messages.append({"role": "system", "content": f"User changed topic to {topic}. Ask a short question."})
            st.rerun()

        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("ZEST AI ⚡️")

    # Первый запуск
    if not st.session_state.messages:
        sys = get_system_prompt(user)
        st.session_state.messages.append({"role": "system", "content": sys})
        wel = f"Hi {user['name']}! Ready for {topic}? (Click 🎙️ to speak)"
        st.session_state.messages.append({"role": "assistant", "content": wel})
        save_history(user["row_id"], st.session_state.messages)

    # Чат
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            av = "👨‍🏫" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

    # --- ИНТЕРФЕЙС ВВОДА ---
    # Аудио (На мобилке нужно будет нажать Play на ответе)
    audio_val = st.audio_input("Speak / Говорить 🎙️")
    text_val = st.chat_input("Type here...")

    user_input = None
    if audio_val:
        with st.spinner("Transcribing..."):
            try:
                transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_val)
                user_input = transcription.text
            except Exception as e:
                st.error("Audio error. Try text.")
    elif text_val:
        user_input = text_val

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        with st.chat_message("assistant", avatar="👨‍🏫"):
            full_resp = ""
            ph = st.empty()
            
            # Генерация текста
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
            
            # Генерация голоса (БЕЗ AUTOPLAY для стабильности на мобилках)
            # Мы генерируем аудио, но пользователь должен нажать Play сам
            response = client.audio.speech.create(model="tts-1", voice="onyx", input=full_resp)
            st.audio(response.content, format="audio/mp3") 

        st.session_state.messages.append({"role": "assistant", "content": full_resp})
        save_history(user["row_id"], st.session_state.messages)
        st.rerun() # Обновляем прогресс-бар
