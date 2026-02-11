import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="ZEST AI | IELTS Coach", page_icon="⚡️", layout="centered")

# --- 2. БАЗА ДАННЫХ ---
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

# --- 3. ФУНКЦИИ ---
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

# --- 4. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets: st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 5. ЛОГИКА ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []
if "wod" not in st.session_state: st.session_state.wod = get_word_of_the_day() # Word of Day init

# ==================== ВХОД ====================
if not st.session_state.user:
    st.title("⚡️ ZEST AI | IELTS")
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
            n_la = st.selectbox("Lang:", ["Kazakh", "Russian", "English", "Chinese", "Hindi"])
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
        # --- ФИШКА 1: СЛОВО ДНЯ ---
        st.info(f"💡 **Word of the Day:**\n\n**{st.session_state.wod[0]}**\n_{st.session_state.wod[1]}_")
        
        st.divider()
        st.caption(f"User: {user['name']}")
        
        # --- ФИШКА 2: СКАЧАТЬ ЧАТ ---
        chat_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages if m['role'] != 'system'])
        st.download_button("📥 Download Chat", chat_text, file_name="lesson.txt")
        
        st.divider()
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()

    st.title("ZEST AI ⚡️")
    
    # --- ФИШКА 3: НАСТРОЙКА ГОЛОСА ---
    with st.expander("⚙️ Audio Settings"):
        voice_speed = st.slider("Voice Speed:", 0.5, 1.5, 1.0, 0.1)

    if not st.session_state.messages:
        sys = f"Role: IELTS Coach Arman. Student Lang: {user['native_lang']}. Style: Socratic, Brief (2-3 sentences). Explain errors in Native Lang, practice in English. Strict Focus on IELTS."
        st.session_state.messages.append({"role": "system", "content": sys})
        st.session_state.messages.append({"role": "assistant", "content": f"Hi {user['name']}! Ready to practice? (Press 🎙️)"})

    for msg in st.session_state.messages:
        if msg["role"] != "system":
            av = "👨‍🏫" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=av):
                st.markdown(msg["content"])

    # ВВОД
    audio_val = st.audio_input("Speak / Говорить 🎙️")
    text_val = st.chat_input("Type...")

    user_in = None
    if audio_val:
        with st.spinner("👂..."):
            user_in = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
    elif text_val:
        user_in = text_val

    if user_in:
        st.session_state.messages.append({"role": "user", "content": user_in})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_in)

        with st.chat_message("assistant", avatar="👨‍🏫"):
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
            
            # --- ПРИМЕНЕНИЕ СКОРОСТИ ГОЛОСА ---
            resp_audio = client.audio.speech.create(model="tts-1", voice="onyx", input=full_resp, speed=voice_speed)
            st.audio(resp_audio.content, format="audio/mp3")

        st.session_state.messages.append({"role": "assistant", "content": full_resp})
        save_history(user["row_id"], st.session_state.messages)
        st.rerun()
