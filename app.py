import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import re # Для поиска уровня в тексте

# --- 1. КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="ZEST AI | ALAN 8.1", page_icon="⚡️", layout="wide")

# CSS для скрытия мусора и красивых плашек
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stMetric { border: 1px solid #444; padding: 10px; border-radius: 10px; background: #1e1e1e; }
</style>
""", unsafe_allow_html=True)

# --- 2. БАЗА ДАННЫХ (БЕЗОПАСНАЯ) ---
@st.cache_resource(ttl=600)
def get_db_connection():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds:
            creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds)
        return gc.open("IELTS_Users_DB").sheet1
    except Exception as e:
        st.error(f"Database Connection Failed: {e}")
        return None

worksheet = get_db_connection()

# --- 3. ЛОГИКА ДАННЫХ ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            # Фикс для пустой истории
            hist_str = row[4] if len(row) > 4 else "[]"
            try: h = json.loads(hist_str)
            except: h = []
            return {
                "row_id": cell.row, "name": row[1], "band": row[2], 
                "target": row[3], "history": h, "password": str(row[5]), "native_lang": row[6]
            }
    except: return None

def sync_data(row_id, band=None, history=None):
    if not worksheet: return
    try:
        if band: worksheet.update_cell(row_id, 3, str(band))
        if history: worksheet.update_cell(row_id, 5, json.dumps(history, ensure_ascii=False))
    except Exception as e:
        st.toast(f"⚠️ Sync Error: {e}", icon="❌")

# Функция безопасного извлечения балла из текста ИИ
def extract_band(text):
    match = re.search(r"\[(?:BAND|ESTIMATED BAND):\s*([\d\.]+)\]", text, re.IGNORECASE)
    return match.group(1) if match else None

# --- 4. КОНТЕНТ (ЗАДАНИЯ) ---
READING_TASK = {
    "title": "The Impact of Urbanization",
    "text": "Urbanization refers to the population shift from rural to urban areas...",
    "questions": ["Q1: Does urbanization decrease city density? (True/False)", "Q2: Mention one cause of migration."],
    "answers": ["false", "work"]
}

# --- 5. OPENAI ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []

# ==================== ЭКРАН ВХОДА ====================
if not st.session_state.user:
    st.title("⚡️ ZEST AI | ALAN")
    with st.form("auth"):
        ph = st.text_input("ID (Phone):")
        pw = st.text_input("Password:", type="password")
        if st.form_submit_button("Enter Academy"):
            u = load_user(ph)
            if u and u["password"] == pw:
                st.session_state.user = u
                st.session_state.messages = u["history"]
                st.rerun()
            else: st.error("Access Denied. Check your ID/Password.")

# ==================== ПЛАТФОРМА ====================
else:
    user = st.session_state.user
    
    # --- TOP DASHBOARD ---
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.metric("Current Band", user['band'])
    with c2:
        st.subheader(f"Welcome, {user['name']}!")
        st.caption(f"Target: {user['target']} | Lang: {user['native_lang']}")
    with c3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()
    
    st.divider()

    # --- СЕКЦИИ ---
    t_speak, t_write, t_read, t_listen = st.tabs(["🎙️ Speaking", "📝 Writing", "📖 Reading", "🎧 Listening"])

    # --- 🎙️ SPEAKING COACH ---
    with t_speak:
        st.write("### IELTS Speaking Simulator")
        
        for msg in st.session_state.messages[-6:]:
            if msg["role"] != "system":
                av = "👨‍💻" if msg["role"] == "assistant" else "👤"
                with st.chat_message(msg["role"], avatar=av):
                    st.markdown(msg["content"])

        audio_val = st.audio_input("Golos / Voice")
        
        if audio_val:
            u_text = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
            st.session_state.messages.append({"role": "user", "content": u_text})
            
            with st.chat_message("assistant", avatar="👨‍💻"):
                prompt = f"Act as IELTS Coach ALAN. 1. Brief Feedback. 2. Next Q. 3. End with [BAND: X.X] if level changed."
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": prompt}] + st.session_state.messages[-5:]
                )
                ai_text = resp.choices[0].message.content
                
                # Безопасное обновление балла
                new_b = extract_band(ai_text)
                if new_b:
                    user['band'] = new_b
                    sync_data(user['row_id'], band=new_b)
                    st.toast(f"🎉 Band Updated to {new_b}!", icon="🔥")
                    ai_text = re.sub(r"\[.*?\]", "", ai_text).strip() # Убираем тех.тег из текста

                st.markdown(ai_text)
                v = client.audio.speech.create(model="tts-1", voice="onyx", input=ai_text)
                st.audio(v.content, format="audio/mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
                sync_data(user['row_id'], history=st.session_state.messages)
                st.rerun()

    # --- 📝 WRITING GRADER ---
    with t_write:
        st.write("### Task 2 Essay Grader")
        st.info("Topic: Discuss the pros and cons of remote working.")
        essay = st.text_area("Your Essay:", height=250)
        if st.button("Check Essay"):
            if essay:
                with st.spinner("Analyzing..."):
                    res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": f"Grade this IELTS essay: {essay}"}]
                    )
                    st.markdown(res.choices[0].message.content)

    # --- 📖 READING TEST ---
    with t_read:
        st.write(f"### {READING_TASK['title']}")
        st.write(READING_TASK['text'])
        st.divider()
        a1 = st.radio(READING_TASK['questions'][0], ["True", "False"])
        a2 = st.text_input(READING_TASK['questions'][1])
        
        if st.button("Submit Reading"):
            score = 0
            if a1.lower() == READING_TASK['answers'][0]: score += 1
            if READING_TASK['answers'][1] in a2.lower(): score += 1
            
            b = "8.0" if score == 2 else "5.5" if score == 1 else "4.0"
            st.success(f"Score: {score}/2. Estimated Band: {b}")
            user['band'] = b
            sync_data(user['row_id'], band=b)

    # --- 🎧 LISTENING ---
    with t_listen:
        st.write("### Listening Practice")
        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
        ans_l = st.text_input("What was the key word from the audio?")
        if st.button("Check Listening"):
            st.toast("Logic is working. Alan is checking...", icon="🎧")
