import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="ALAN | IELTS Platform", page_icon="⚡️", layout="wide")

# CSS для красивого отображения метрик и кнопок
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Стили для карточек в топе */
    .metric-container {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #333;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. БД ---
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
            return {
                "row_id": cell.row, "name": row[1], "band": row[2], 
                "target": row[3], "history": json.loads(hist), 
                "password": str(row[5]), "native_lang": row[6]
            }
    except: return None

def update_user_data(row_id, band=None, history=None):
    if not worksheet: return
    try:
        if band: worksheet.update_cell(row_id, 3, str(band))
        if history: worksheet.update_cell(row_id, 5, json.dumps(history, ensure_ascii=False))
    except: pass

def get_wod():
    words = [("Ubiquitous", "Вездесущий"), ("Eloquent", "Красноречивый"), ("Resilient", "Устойчивый"), ("Inevitable", "Неизбежный")]
    return random.choice(words)

# --- 4. OPENAI ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []
if "wod" not in st.session_state: st.session_state.wod = get_wod()

# ==================== ЭКРАН ВХОДА ====================
if not st.session_state.user:
    st.title("⚡️ ZEST AI | ALAN")
    with st.form("login_form"):
        ph = st.text_input("Phone Number (ID):")
        pw = st.text_input("Password:", type="password")
        if st.form_submit_button("Enter Platform"):
            u = load_user(ph)
            if u and u["password"] == pw:
                st.session_state.user = u
                st.session_state.messages = u["history"]
                st.rerun()
            else: st.error("Wrong ID or Password")

# ==================== ГЛАВНЫЙ ИНТЕРФЕЙС ====================
else:
    user = st.session_state.user
    
    # --- ШАПКА (ВИДНА ВСЕГДА) ---
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.metric(label="Current Band", value=user['band'], delta=f"Target: {user['target']}")
    
    with col2:
        st.info(f"💡 Word of Day: **{st.session_state.wod[0]}** ({st.session_state.wod[1]})")
        
    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    st.divider()

    # --- НАВИГАЦИЯ ПО СЕКЦИЯМ (ВСЕГДА ВИДНО) ---
    tab_speak, tab_write, tab_read, tab_listen = st.tabs([
        "🎙️ Speaking", "📝 Writing", "📖 Reading", "🎧 Listening"
    ])

    # --- 🎙️ СЕКЦИЯ: SPEAKING ---
    with tab_speak:
        st.subheader("IELTS Speaking Simulator")
        
        # Кнопка сброса внутри вкладки
        if st.button("🧹 Clear Chat History", key="clear_speak"):
            st.session_state.messages = []
            update_user_data(user['row_id'], history=[])
            st.rerun()

        # Вывод чата
        for msg in st.session_state.messages[-10:]:
            if msg["role"] != "system":
                with st.chat_message(msg["role"], avatar="👨‍💻" if msg["role"]=="assistant" else "👤"):
                    st.markdown(msg["content"])

        # Ввод
        audio_val = st.audio_input("Record your answer", key="mic_speak")
        text_val = st.chat_input("Or type to Alan...", key="text_speak")
        
        user_in = None
        if audio_val:
            user_in = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
        elif text_val:
            user_in = text_val

        if user_in:
            st.session_state.messages.append({"role": "user", "content": user_in})
            with st.chat_message("user"): st.markdown(user_in)

            with st.chat_message("assistant"):
                # Промпт для ИИ: учить и оценивать
                prompt = f"""You are ALAN, an IELTS examiner. Analyze user input: '{user_in}'.
                1. Provide brief feedback.
                2. Ask next logical question for IELTS Part 1 or 2.
                3. If the user improved, add [NEWBAND: X.X] to the end of your message. Be strict."""
                
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": prompt}] + st.session_state.messages[-5:]
                )
                full_text = resp.choices[0].message.content
                
                # Обновление Band Score
                if "[NEWBAND:" in full_text:
                    new_val = full_text.split("[NEWBAND:")[1].split("]")[0].strip()
                    user['band'] = new_val
                    full_text = full_text.split("[NEWBAND:")[0]
                    update_user_data(user['row_id'], band=new_val)
                    st.toast(f"🎉 Band Updated to {new_val}!", icon="🔥")
                
                st.markdown(full_text)
                
                # Озвучка
                voice = client.audio.speech.create(model="tts-1", voice="onyx", input=full_text)
                st.audio(voice.content, format="audio/mp3")

            st.session_state.messages.append({"role": "assistant", "content": full_text})
            update_user_data(user['row_id'], history=st.session_state.messages)

    # --- 📝 СЕКЦИЯ: WRITING ---
    with tab_write:
        st.subheader("Writing Task 2 Checker")
        topic = st.text_input("Essay Question Topic:")
        essay = st.text_area("Your Essay (min 250 words):", height=300)
        
        if st.button("Check Band Score"):
            if essay:
                with st.spinner("Analyzing criteria..."):
                    res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": f"Grade this IELTS essay based on 4 criteria and provide Band Score. Topic: {topic}. Essay: {essay}"}]
                    )
                    st.markdown(res.choices[0].message.content)
            else: st.warning("Please paste your essay first.")

    # --- 📖 СЕКЦИЯ: READING ---
    with tab_read:
        st.subheader("Daily Reading Practice")
        st.info("Reading tests are being updated. Check back tomorrow for a new Academic text!")
        # 

    # --- 🎧 СЕКЦИЯ: LISTENING ---
    with tab_listen:
        st.subheader("Listening Audio Drills")
        st.info("Audio sections will appear here. Alan is preparing the recordings.")
