import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ (ТУРБО) ---
st.set_page_config(page_title="ALAN | ZEST AI", page_icon="⚡️", layout="centered")

# --- 2. CSS: СТЕЛС-РЕЖИМ И ИНТЕРФЕЙС ---
stealth_css = """
<style>
    /* 1. УБИРАЕМ ВСЕ НАДПИСИ STREAMLIT */
    #MainMenu {visibility: hidden;} /* Меню справа сверху */
    footer {visibility: hidden;}    /* Надпись внизу */
    header {visibility: hidden;}    /* Красная полоска сверху */
    .stDeployButton {display:none;} /* Кнопка Deploy */
    
    /* 2. МИКРОФОН (ЗАКРЕПЛЕН ВНИЗУ) */
    [data-testid="stAudioInput"] {
        position: fixed;
        bottom: 90px;
        z-index: 999;
        left: 0; right: 0;
        margin: 0 auto;
        width: 100%;
        max-width: 44rem;
        background-color: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 8px;
        box-shadow: 0px -4px 10px rgba(0,0,0,0.05);
        border: 1px solid #eee;
    }
    
    /* Темная тема для микрофона */
    @media (prefers-color-scheme: dark) {
        [data-testid="stAudioInput"] {
            background-color: rgba(38, 39, 48, 0.95);
            border: 1px solid #333;
        }
    }
    
    /* Отступ чтобы чат не проваливался под кнопки */
    .stMainBlockContainer { padding-bottom: 200px; }
</style>
"""
st.markdown(stealth_css, unsafe_allow_html=True)

# --- 3. БД (БЫСТРОЕ ПОДКЛЮЧЕНИЕ) ---
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
        ("Ubiquitous", "Вездесущий (Everywhere)"),
        ("Ephemeral", "Мимолетный (Short-lived)"),
        ("Eloquent", "Красноречивый (Persuasive)"),
        ("Resilient", "Устойчивый (Strong)"),
        ("Meticulous", "Тщательный (Careful)"),
        ("Inevitable", "Неизбежный (Unavoidable)")
    ]
    return random.choice(words)

# --- 5. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets: st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ЛОГИКА ---
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
            n_la = st.selectbox("Language:", ["Kazakh", "Russian", "English", "Chinese", "Hindi", "Spanish"])
            n_lv = st.select_slider("Level:", ["Beginner", "Intermediate", "Advanced"])
            n_tg = st.selectbox("Target Band:", ["6.0", "6.5", "7.0+"])
            if st.form_submit_button("Create Profile"):
                r = register_user(n_ph, n_nm, n_lv, n_tg, n_pw, n_la)
                if r: 
                    st.session_state.user = r
                    st.session_state.messages = []
                    st.rerun()

# ==================== ЧАТ ====================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.info(f"💡 **Word of the Day:**\n\n### {st.session_state.wod[0]}\n_{st.session_state.wod[1]}_")
        st.divider()
        st.caption(f"👤 {user['name']}")
        
        if st.button("🧹 New Topic (Clear)"):
            st.session_state.messages = []
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("ALAN ⚡️")

    # --- СИСТЕМНЫЙ МОЗГ (TURBO MODE) ---
    if not st.session_state.messages:
        sys = f"""
        Role: IELTS Coach ALAN.
        User Lang: {user['native_lang']}.
        
        RULES FOR SPEED:
        1. MAX 2 SENTENCES per reply. Be extremely concise.
        2. IF ERROR: Correct it immediately.
        3. IF NO ERROR: Ask next question.
        4. Explain grammar in {user['native_lang']}. Practice in English.
        """
        st.session_state.messages.append({"role": "system", "content": sys})
        st.session_state.messages.append({"role": "assistant", "content": f"Hi {user['name']}! Ready? Press 🎙️."})

    # --- ИСТОРИЯ ---
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            av = "👨‍💻" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

    # --- ВВОД ---
    audio_val = st.audio_input("Speak 🎙️")
    text_val = st.chat_input("Type...")

    user_in = None
    if audio_val:
        # Убрал spinner с текстом, чтобы не мелькало
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
            
            # ИСПОЛЬЗУЕМ GPT-4o-MINI ДЛЯ СКОРОСТИ
            stream = client.chat.completions.create(
                model="gpt-4o-mini", # <-- TURBO SPEED
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
                # Опционально: alloy быстрее грузится чем onyx, но onyx солиднее. Оставим onyx.
                response = client.audio.speech.create(model="tts-1", voice="onyx", input=full_resp)
                st.audio(response.content, format="audio/mp3")
            except: pass

        st.session_state.messages.append({"role": "assistant", "content": full_resp})
        save_history(user["row_id"], st.session_state.messages)
