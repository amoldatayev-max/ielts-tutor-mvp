import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="ALAN | ZEST AI", page_icon="⚡️", layout="centered")

# --- 2. CSS: СТЕЛС-РЕЖИМ + ФИКС ИНТЕРФЕЙСА ---
stealth_css = """
<style>
    /* 1. СКРЫВАЕМ БРЕНДИНГ STREAMLIT */
    #MainMenu {visibility: hidden;} /* Меню справа сверху */
    footer {visibility: hidden;}    /* Надпись "Made with Streamlit" */
    header {visibility: hidden;}    /* Красная полоска сверху */
    .stDeployButton {display:none;} /* Кнопка Deploy */
    
    /* 2. МИКРОФОН (ПЛАВАЮЩИЙ БЛОК) */
    /* Мы поднимаем его на 160px вверх, чтобы он точно не налез на текст */
    [data-testid="stAudioInput"] {
        position: fixed;
        bottom: 160px; 
        z-index: 999;
        left: 0; 
        right: 0;
        margin: 0 auto;
        width: 100%;
        max-width: 44rem; /* Ограничение ширины */
        
        /* Дизайн плашки микрофона */
        background-color: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 10px;
        box-shadow: 0px -5px 20px rgba(0,0,0,0.1);
        border: 1px solid #eee;
    }
    
    /* Темная тема для микрофона */
    @media (prefers-color-scheme: dark) {
        [data-testid="stAudioInput"] {
            background-color: rgba(38, 39, 48, 0.95);
            border: 1px solid #333;
        }
    }
    
    /* 3. ОТСТУП ДЛЯ ЧАТА */
    /* Добавляем пустое место внизу, чтобы сообщения не прятались за микрофоном */
    .stMainBlockContainer {
        padding-bottom: 280px; 
    }
</style>
"""
st.markdown(stealth_css, unsafe_allow_html=True)

# --- 3. ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ (КЭШ) ---
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

# --- 5. OPENAI SETUP ---
if "OPENAI_API_KEY" not in st.secrets: st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []
if "wod" not in st.session_state: st.session_state.wod = get_wod()

# ==================== ЭКРАН 1: ВХОД / РЕГИСТРАЦИЯ ====================
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
                else: st.error("Incorrect Login")

    with tab2:
        with st.form("reg"):
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
        st.info(f"💡 **Word of the Day:**\n\n### {st.session_state.wod[0]}\n_{st.session_state.wod[1]}_")
        st.divider()
        st.caption(f"👤 **{user['name']}**")
        
        # Кнопки управления
        if st.button("🧹 New Topic (Clear)"):
            st.session_state.messages = []
            st.rerun()
            
        if st.button("🚪 Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("ALAN ⚡️")

    # --- МОЗГ АЛАНА (TURBO PROMPT) ---
    if not st.session_state.messages:
        sys = f"""
        Role: IELTS Coach ALAN.
        Student: {user['name']}. Native Lang: {user['native_lang']}.
        
        RULES:
        1. BE CONCISE. Max 2-3 sentences.
        2. IF ERROR: Correct it immediately.
        3. IF NO ERROR: Ask next question.
        4. Explain grammar in {user['native_lang']} if needed.
        5. NEVER give long lectures.
        """
        st.session_state.messages.append({"role": "system", "content": sys})
        st.session_state.messages.append({"role": "assistant", "content": f"Hi {user['name']}! I'm ALAN. Ready? Press 🎙️."})

    # --- ВЫВОД ИСТОРИИ ЧАТА ---
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            av = "👨‍💻" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

    # --- ИНТЕРФЕЙС ВВОДА ---
    
    # 1. АУДИО (Висит в воздухе благодаря CSS)
    audio_val = st.audio_input
