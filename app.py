import streamlit as st
from openai import OpenAI
import gspread
import json
import time

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Coach Arman", page_icon="🌍", layout="centered")

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
            # Структура: Phone[0], Name[1], Level[2], Target[3], History[4], Password[5], NativeLang[6]
            history_data = row[4] if len(row) > 4 else "[]"
            password_data = row[5] if len(row) > 5 else "" 
            # Если у старых юзеров нет языка, ставим English
            native_lang = row[6] if len(row) > 6 else "English" 
            
            try: history = json.loads(history_data)
            except: history = []
            
            return {
                "row_id": cell.row, 
                "name": row[1], 
                "level": row[2], 
                "target": row[3], 
                "history": history, 
                "password": str(password_data),
                "native_lang": native_lang
            }
    except: return None
    return None

def register_user(phone, name, level, target, password, native_lang):
    if not worksheet: return None
    try:
        if worksheet.find(phone): return "EXISTS"
        # Добавляем native_lang в конец
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
    # IDENTITY & ROLE
    You are Arman, an elite IELTS Coach.
    Student: {user['name']}, Level: {user['level']}, Target: {user['target']}.
    Student's Native Language: {user['native_lang']}
    
    # TEACHING STYLE
    - Strict but supportive.
    - Socratic method: Ask questions, don't just lecture.
    - FEEDBACK: Always use "Sandwich method" (Praise -> Correction -> Next Question).
    
    # GLOBAL LANGUAGE PROTOCOL (CRITICAL)
    - The student's native language is **{user['native_lang']}**.
    - IF Student is Beginner/Intermediate:
      - You MUST explain grammar rules and complex vocabulary in **{user['native_lang']}**.
      - Keep the practice questions in English.
      - If they are confused, translate the task into **{user['native_lang']}**.
    - IF Student is Advanced:
      - Speak ONLY English.

    # GUARDRAILS
    - NO Math/Physics/Coding. Refuse politely in {user['native_lang']}.
    - NO writing essays FOR the student.
    
    # VOICE MODE INSTRUCTION
    - Keep answers CONCISE (max 2-3 sentences).
    - Always end with a question.
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
    st.title("🌍 IELTS Coach Arman Global")
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    with tab1:
        with st.form("login"):
            ph = st.text_input("ID (Phone):")
            pw = st.text_input("Password:", type="password")
            if st.form_submit_button("Login"):
                with st.spinner("Logging in..."):
                    ud = load_user(ph)
                    if ud and str(ud["password"]).strip() == str(pw).strip():
                        st.session_state.user = ud
                        st.session_state.messages = ud["history"]
                        st.rerun()
                    else: st.error("Login failed")
        if st.expander("Forgot password?"): st.markdown(f"Contact Support: **[Telegram]({ADMIN_CONTACT})**")

    with tab2:
        with st.form("reg"):
            st.caption("Create your profile / Создать профиль")
            n_ph = st.text_input("ID (Phone):")
            n_pw = st.text_input("Password:", type="password")
            n_nm = st.text_input("Name / Имя:")
            
            # НОВЫЙ БЛОК: ВЫБОР ЯЗЫКА
            n_lang = st.selectbox(
                "Native Language / Родной язык:", 
                ["Kazakh", "Russian", "English", "Chinese (Mandarin)", "Hindi", "Spanish", "French", "Arabic", "Turkish"]
            )
            
            n_lv = st.select_slider("Level:", ["Beginner", "Intermediate", "Advanced"])
            n_tg = st.selectbox("Target Band:", ["6.0", "6.5", "7.0", "7.5", "8.0+"])
            
            if st.form_submit_button("Start Learning 🚀"):
                if n_ph and n_pw and n_nm:
                    res = register_user(n_ph, n_nm, n_lv, n_tg, n_pw, n_lang)
                    if res == "EXISTS": st.error("User exists.")
                    elif res: 
                        st.session_state.user = res
                        st.session_state.messages = []
                        st.rerun()
                else: st.warning("Fill all fields")

# ==========================================
# ЭКРАН 2: ЧАТ С ГОЛОСОМ 🎙️
# ==========================================
else:
    user = st.session_state.user
    
    with st.sidebar:
        # Логотип теперь нейтральный глобус или можно оставить флаг КЗ как бренд
        st.header(user['name'])
        st.caption(f"{user['native_lang']} Speaker")
        st.caption(f"{user['level']} | {user['target']}")
        
        topic = st.selectbox("Topic:", ["General", "Work", "Studies", "Hometown", "Hobbies", "Travel", "Technology"])
        
        if "current_topic" not in st.session_state: st.session_state.current_topic = "General"
        if topic != st.session_state.current_topic:
            st.session_state.current_topic = topic
            st.session_state.messages.append({"role": "system", "content": f"Topic changed to: {topic}. Ask a question."})
            st.rerun()

        st.divider()
        if st.button("🧹 Clear Chat"):
            st.session_state.messages = []
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("Arman | AI Coach 🎙️")

    # Инициализация
    if not st.session_state.messages:
        sys = get_system_prompt(user)
        st.session_state.messages.append({"role": "system", "content": sys})
        
        # Приветствие адаптируется под язык (просим GPT сгенерировать первое сообщение)
        # Но для скорости оставим универсальное на английском
        wel = f"Hello {user['name']}! I am Arman. I see your native language is **{user['native_lang']}**. \n\nLet's talk about **{topic}**. Press the microphone to speak!"
        st.session_state.messages.append({"role": "assistant", "content": wel})
        save_history(user["row_id"], st.session_state.messages)

    # Вывод истории
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            avatar = "👨‍🏫" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    # Ввод
    audio_val = st.audio_input("Speak / Говорить 🎙️")
    text_val = st.chat_input("Type message...")

    user_input = None
    if audio_val:
        with st.spinner("Listening..."):
            transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_val)
            user_input = transcription.text
    elif text_val:
        user_input = text_val

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        with st.chat_message("assistant", avatar="👨‍🏫"):
            text_placeholder = st.empty()
            full_response = ""
            
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
            
            with st.spinner("Speaking... 🔊"):
                response = client.audio.speech.create(
                    model="tts-1",
                    voice="onyx",
                    input=full_response
                )
                st.audio(response.content, format="audio/mp3", autoplay=True)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_history(user["row_id"], st.session_state.messages)
