import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="ALAN | IELTS Universe", page_icon="⚡️", layout="wide")

# CSS: Скрываем лишнее, делаем красивые карточки
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: rgba(255, 255, 255, 0.05); 
        border-radius: 5px; 
        padding: 10px 20px;
    }
    .status-box {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #333;
        background: linear-gradient(45deg, #1e1e1e, #2d2d2d);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. БД (Google Sheets) ---
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
            return {
                "row_id": cell.row, "name": row[1], "band": row[2], 
                "target": row[3], "history": json.loads(row[4] if len(row) > 4 else "[]"), 
                "password": str(row[5]), "native_lang": row[6]
            }
    except: return None

def update_user_data(row_id, band=None, history=None):
    if not worksheet: return
    try:
        if band: worksheet.update_cell(row_id, 3, str(band))
        if history: worksheet.update_cell(row_id, 5, json.dumps(history, ensure_ascii=False))
    except: pass

# --- 4. OPENAI ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []

# ==================== ВХОД ====================
if not st.session_state.user:
    st.title("⚡️ ALAN | IELTS Universe")
    with st.form("login"):
        ph = st.text_input("ID (Phone):")
        pw = st.text_input("Password:", type="password")
        if st.form_submit_button("Start"):
            u = load_user(ph)
            if u and u["password"] == pw:
                st.session_state.user = u
                st.session_state.messages = u["history"]
                st.rerun()
            else: st.error("Access Denied")

# ==================== ПЛАТФОРМА ====================
else:
    user = st.session_state.user
    
    # --- ШАПКА (ВСЕГДА ВИДНО) ---
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.metric("Your IELTS Band", user['band'])
    with c2:
        st.markdown(f"### Welcome back, {user['name']}! 👋")
        st.caption(f"Target Score: {user['target']} | Native Language: {user['native_lang']}")
    with c3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()
    
    st.divider()

    # --- СЕКЦИИ (TABS) ---
    t_speak, t_write, t_read, t_listen = st.tabs(["🎙️ Speaking", "📝 Writing", "📖 Reading", "🎧 Listening"])

    # --- 🎙️ SPEAKING ---
    with t_speak:
        st.subheader("Speaking Practice: Part 1 (Warm up)")
        
        # История
        for msg in st.session_state.messages[-6:]:
            if msg["role"] != "system":
                with st.chat_message(msg["role"], avatar="👨‍💻" if msg["role"]=="assistant" else "👤"):
                    st.markdown(msg["content"])

        audio_val = st.audio_input("Record your answer", key="speak_mic")
        
        if audio_val:
            user_in = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
            st.session_state.messages.append({"role": "user", "content": user_in})
            
            with st.chat_message("assistant"):
                prompt = f"You are ALAN. Analyze: '{user_in}'. 1. Feedback. 2. Next Question. 3. Final: [ESTIMATED BAND: X.X]"
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt}] + st.session_state.messages[-5:])
                text = resp.choices[0].message.content
                
                if "[ESTIMATED BAND:" in text:
                    new_b = text.split("[ESTIMATED BAND:")[1].split("]")[0].strip()
                    user['band'] = new_b
                    update_user_data(user['row_id'], band=new_b)
                
                st.markdown(text)
                v = client.audio.speech.create(model="tts-1", voice="onyx", input=text)
                st.audio(v.content, format="audio/mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": text})
                update_user_data(user['row_id'], history=st.session_state.messages)
                st.rerun()

    # --- 📝 WRITING ---
    with t_write:
        st.subheader("Writing Task 2: Essay")
        st.markdown("**Topic:** *Some people believe that school children should be allowed to use mobile phones in the classroom. Discuss both views and give your opinion.*")
        
        essay = st.text_area("Type your essay here (min 250 words):", height=300)
        if st.button("Check & Grade Essay"):
            with st.spinner("Alan is marking your paper..."):
                res = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": f"Grade this essay and provide detailed Band Score feedback: {essay}"}]
                )
                st.markdown(res.choices[0].message.content)

    # --- 📖 READING ---
    with t_read:
        st.subheader("Reading Test: Academic Passage")
        st.markdown("""
        **The Rise of Artificial Intelligence**
        AI is transforming the modern world... (Text Sample)
        
        **Questions:**
        1. Does AI improve productivity? (True/False/Not Given)
        2. Who invented the first AI concept?
        """)
        
        ans1 = st.radio("Q1 Answer:", ["True", "False", "Not Given"])
        ans2 = st.text_input("Q2 Answer:")
        
        if st.button("Check Reading Score"):
            # Логика простой проверки
            score = 0
            if ans1 == "True": score += 1
            if "turing" in ans2.lower(): score += 1
            
            band = "5.0" if score == 1 else "8.0" if score == 2 else "4.0"
            st.success(f"Your Reading Band for this task: {band}")
            update_user_data(user['row_id'], band=band)

    # --- 🎧 LISTENING ---
    with t_listen:
        st.subheader("Listening Drill")
        st.info("Listen to the recording and fill in the blanks.")
        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3") # Пример аудио
        
        q_listen = st.text_input("What was the speaker's phone number?")
        if st.button("Check Listening"):
            if "123" in q_listen:
                st.success("Correct! Band 9.0")
            else:
                st.error("Wrong. Try again. Current Band: 5.5")
