import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="ZEST AI | ALAN Coach", page_icon="⚡️", layout="centered")

# --- 2. CSS МАГИЯ (ПРИКЛЕИВАЕМ МИКРОФОН ВНИЗ) ---
# Этот код делает так, что микрофон всегда висит над строкой ввода
sticky_mic_css = """
<style>
    /* Скрываем меню Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Приклеиваем блок аудио вниз */
    [data-testid="stAudioInput"] {
        position: fixed;
        bottom: 80px; /* Отступ снизу (над текстовым полем) */
        z-index: 1000;
        width: 100%;
        max-width: 44rem; /* Ограничение ширины как у чата */
        background-color: transparent; /* Прозрачный фон */
        margin: 0 auto;
        left: 0;
        right: 0;
    }
    
    /* Добавляем пустое место внизу чата, чтобы сообщения не прятались под микрофоном */
    .stMainBlockContainer {
        padding-bottom: 150px;
    }
</style>
"""
st.markdown(sticky_mic_css, unsafe_allow_html=True)

# --- 3. ПОДКЛЮЧЕНИЕ БД ---
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

# --- 4. ФУНКЦИИ ---
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

# --- 5. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets: st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ЛОГИКА ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []
if "wod" not in st.session_state: st.session_state.wod = get_word_of_the_day()

# ==================== ВХОД ====================
if not st.session_state.user:
    st.title("⚡️ ZEST AI | ALAN")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        with st.form("login"):
            ph = st.text_input("ID:")
            pw = st.text_input("Pass:", type="password")
            if st.form_submit_button("Go"):
                ud = load_user(ph)
                if ud and str(ud["password"]).strip() == str(pw).strip():
                    st.session_state.user = ud
                    st.session_state.messages = ud["history"]
                    st.rerun()
                else: st.error("Error")
    with tab2:
        with st.form("reg"):
            n_ph = st.text_input("ID:")
            n_pw = st.text_input("Pass:", type="password")
            n_nm = st.text_input("Name:")
            n_la = st.selectbox("Lang:", ["Kazakh", "Russian", "English", "Chinese", "Hindi", "Spanish"])
            n_lv = st.select_slider("Lvl:", ["Beginner", "Intermediate", "Advanced"])
            n_tg = st.selectbox("Band:", ["6.0", "6.5", "7.0+"])
            if st.form_submit_button("Create"):
                r = register_user(n_ph, n_nm, n_lv, n_tg, n_pw, n_la)
                if r: 
                    st.session_state.user = r
                    st.session_state.messages = []
                    st.rerun()

# ==================== ЧАТ ====================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.info(f"💡 **Word of the Day:**\n\n**{st.session_state.wod[0]}**\n_{st.session_state.wod[1]}_")
        
        user_msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
        st.progress(min(user_msg_count / 50, 1.0))
        st.caption(f"XP: {user_msg_count} actions")
        
        st.divider()
        st.caption(f"User: {user['name']}")
        
        chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
        st.download_button("📥 Download Lesson", chat_text, file_name="lesson.txt")
        
        st.divider()
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("ZEST AI | ALAN ⚡️")

    # Инициализация сообщений
    if not st.session_state.messages:
        sys = f"Role: IELTS Coach ALAN. Student Lang: {user['native_lang']}. Style: Socratic, Brief (2-3 sentences). Explain errors in Native Lang, practice in English. Strict Focus on IELTS."
        st.session_state.messages.append({"role": "system", "content": sys})
        st.session_state.messages.append({"role": "assistant", "content": f"Hello {user['name']}! I am ALAN. Ready to practice? (Press 🎙️)"})

    # Вывод истории (Убираем аватарки для экономии места на мобильных, или оставляем)
    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] != "system":
            av = "👨‍💻" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

    # --- ВВОД ---
    # ВАЖНО: Мы ставим аудио-инпут, а CSS (в начале кода) сам притянет его вниз
    audio_val = st.audio_input("Speak / Говорить 🎙️")
    
    # Текстовый ввод всегда приклеен к самому низу
    text_val = st.chat_input("Type here...")

    user_in = None
    if audio_val:
        with st.spinner("Listening..."):
            try: user_in = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
            except: st.error("Mic error")
    elif text_val:
        user_in = text_val

    # ОБРАБОТКА
    if user_in:
        st.session_state.messages.append({"role": "user", "content": user_in})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_in)

        with st.chat_message("assistant", avatar="👨‍💻"):
            full_resp = ""
            ph = st.empty()
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
            
            # ЗВУК
            try:
                response = client.audio.speech.create(model="tts-1", voice="onyx", input=full_resp)
                st.caption("🔊 ALAN'S VOICE:")
                st.audio(response.content, format="audio/mp3")
            except Exception as e:
                st.error("Audio error")

        st.session_state.messages.append({"role": "assistant", "content": full_resp})
        save_history(user["row_id"], st.session_state.messages)
