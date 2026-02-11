import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="ALAN | ZEST AI", page_icon="⚡️", layout="centered")

# --- 2. ПРОСТОЙ СТИЛЬ (БЕЗ РИСКА) ---
# Убираем только логотип Streamlit, не трогаем кнопки
stealth_css = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
"""
st.markdown(stealth_css, unsafe_allow_html=True)

# --- 3. БД ---
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

def get_wod():
    words = [
        ("Ubiquitous", "Вездесущий"), ("Ephemeral", "Мимолетный"),
        ("Eloquent", "Красноречивый"), ("Resilient", "Устойчивый"),
        ("Meticulous", "Тщательный"), ("Inevitable", "Неизбежный")
    ]
    return random.choice(words)

# --- 5. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets: st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []
if "wod" not in st.session_state: st.session_state.wod = get_wod()

# ==================== ВХОД ====================
if not st.session_state.user:
    st.title("⚡️ ALAN | ZEST AI")
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
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
            n_la = st.selectbox("Lang:", ["Kazakh", "Russian", "English", "Chinese"])
            n_lv = st.select_slider("Lvl:", ["Beginner", "Intermediate", "Advanced"])
            n_tg = st.selectbox("Target:", ["6.0", "6.5", "7.0+"])
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
        st.info(f"💡 Word: **{st.session_state.wod[0]}**")
        if st.button("🧹 Clear Chat"):
            st.session_state.messages = []
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("ALAN ⚡️")

    # Инициализация
    if not st.session_state.messages:
        sys = f"Role: IELTS Coach ALAN. User Lang: {user['native_lang']}. Rules: Brief (2 sentences). Correct errors. Ask questions."
        st.session_state.messages.append({"role": "system", "content": sys})
        st.session_state.messages.append({"role": "assistant", "content": f"Hi {user['name']}! Ready? (Press 🎙️)"})

    # История
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            av = "👨‍💻" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

    # --- ВВОД (СТАНДАРТНЫЙ) ---
    st.write("---") # Разделитель
    
    # 1. Микрофон (Обычный, без магии CSS)
    audio_val = st.audio_input("Golos / Voice 🎙️")
    
    # 2. Текст (Всегда внизу)
    text_val = st.chat_input("Type here...")

    user_in = None
    if audio_val:
        try: user_in = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
        except: st.error("Mic error")
    elif text_val:
        user_in = text_val

    # --- ОТВЕТ ---
    if user_in:
        st.session_state.messages.append({"role": "user", "content": user_in})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_in)

        with st.chat_message("assistant", avatar="👨‍💻"):
            full_resp = ""
            ph = st.empty()
            
            # Текст
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_resp += chunk.choices[0].delta.content
                    ph.markdown(full_resp + " ▌")
            ph.markdown(full_resp)
            
            # Аудио (Добавлен key!)
            try:
                response = client.audio.speech.create(model="tts-1", voice="onyx", input=full_resp)
                # Уникальный ключ заставляет плеер перерисовываться заново
                st.audio(response.content, format="audio/mp3", key=f"audio_msg_{len(st.session_state.messages)}")
            except: pass

        st.session_state.messages.append({"role": "assistant", "content": full_resp})
        save_history(user["row_id"], st.session_state.messages)
