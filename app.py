import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import time
import pandas as pd # Нужно для графиков
import numpy as np # Нужно для графиков

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="ALAN | Official IELTS Simulator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS STYLING ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .exam-paper {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        color: #333;
        margin-bottom: 20px;
    }
    .dark-mode .exam-paper { background-color: #262730; color: #fff; border: 1px solid #444; }
    .question-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-left: 5px solid #007bff;
        margin: 10px 0;
        border-radius: 5px;
        color: #000;
    }
    .correct { color: #00c853; font-weight: bold; }
    .wrong { color: #d50000; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE CONTENT ---
SPEAKING_DB = [
    {
        "topic": "Hometown",
        "part1": ["Where is your hometown?", "Is it a big city or a small place?", "Do you like living there?"],
        "card": "Describe a tourist attraction in your country.\nYou should say:\n- What it is\n- Where it is\n- What you can do there\nAnd explain why you recommend it.",
        "part3": ["Does tourism help the local economy?", "Why do some people prefer traveling abroad?"]
    }
]

# Генерируем данные для графика (чтобы не зависеть от картинок)
CHART_DATA = pd.DataFrame(
    np.array([[150, 200], [170, 180], [180, 160], [200, 140]]),
    columns=['Fish Consumption', 'Meat Consumption'],
    index=['1990', '1995', '2000', '2005']
)

WRITING_DB = {
    "task1": {
        "type": "Line Graph",
        "data": CHART_DATA, # Данные вместо картинки
        "prompt": "The graph below shows the consumption of fish and meat in a European country between 1990 and 2005. Summarise the information."
    },
    "task2": [
        "Some people believe that social media has a negative impact on social interaction. To what extent do you agree or disagree?"
    ]
}

READING_DB = [
    {
        "title": "The Sleep Cycle",
        "text": """
        Sleep is divided into two broad types: non-rapid eye movement (NREM) sleep and rapid eye movement (REM) sleep. NREM sleep is further divided into three stages. Stage 1 is a light sleep from which you can be easily awakened. Stage 2 is a deeper sleep where your heart rate slows. Stage 3 is deep sleep, crucial for physical recovery.
        REM sleep, on the other hand, is when most dreaming occurs. It is essential for cognitive functions such as memory consolidation and mood regulation. Lack of REM sleep can lead to difficulty concentrating.
        """,
        "questions": [
            {"q": "Which stage of sleep is most important for physical recovery?", "a": "Stage 3", "options": ["Stage 1", "Stage 2", "Stage 3"]},
            {"q": "Dreaming occurs mostly during NREM sleep. (True/False/Not Given)", "a": "False", "options": ["True", "False", "Not Given"]}
        ]
    }
]

# Сценарий для аудио (Алан сам его озвучит)
LISTENING_SCRIPT = """
Hello, City Library. How can I help you?
Hi, I would like to register for a library card.
Certainly. Can I have your surname, please?
Yes, it's Black. B-L-A-C-K.
Thank you, Mr. Black. And what is your address?
It's 24 Park Street.
"""

LISTENING_DB = [
    {
        "title": "Section 1: Library Registration",
        "script": LISTENING_SCRIPT, # Текст скрипта
        "context": "You will hear a student registering at a library. Listen and complete the form.",
        "questions": [
            {"label": "1. Surname:", "a": "Black"},
            {"label": "2. Address: 24 ______ Street", "a": "Park"}
        ]
    }
]

# --- 4. BACKEND LOGIC ---
@st.cache_resource(ttl=600)
def get_db():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds: creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds)
        return gc.open("IELTS_Users_DB").sheet1
    except: return None

worksheet = get_db()

def get_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            hist = json.loads(row[4]) if len(row) > 4 else []
            return {"row": cell.row, "name": row[1], "band": row[2], "target": row[3], "history": hist, "pwd": str(row[5])}
    except: return None

def register_user(phone, name, password):
    if not worksheet: return "DB_ERROR"
    try:
        if worksheet.find(phone): return "EXISTS"
        worksheet.append_row([phone, name, "5.0", "7.0", "[]", password, "English"])
        return get_user(phone)
    except: return "ERROR"

def sync_data(row_id, band):
    if worksheet: worksheet.update_cell(row_id, 3, str(band))

if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("API Key Missing.")
    st.stop()

if "user" not in st.session_state: st.session_state.user = None
if "speaking_state" not in st.session_state: st.session_state.speaking_state = {"active": False, "part": 0, "q_idx": 0, "test": None}

# ==================== AUTH SCREEN ====================
if not st.session_state.user:
    st.title("⚡️ ALAN | IELTS Simulator")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        with st.form("login"):
            ph = st.text_input("ID:")
            pw = st.text_input("Password:", type="password")
            if st.form_submit_button("Start"):
                u = get_user(ph)
                if u and u["pwd"] == pw:
                    st.session_state.user = u
                    st.session_state.messages = u["history"]
                    st.rerun()
                else: st.error("Invalid Login")
    with tab2:
        with st.form("reg"):
            n_ph = st.text_input("New ID:")
            n_nm = st.text_input("Name:")
            n_pw = st.text_input("Password:", type="password")
            if st.form_submit_button("Create Account"):
                res = register_user(n_ph, n_nm, n_pw)
                if res == "EXISTS": st.error("User exists")
                elif res == "ERROR": st.error("Error")
                else: 
                    st.session_state.user = res
                    st.session_state.messages = []
                    st.rerun()

# ==================== EXAM PLATFORM ====================
else:
    u = st.session_state.user
    
    # --- HEADER ---
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.metric("Band Score", u['band'], delta="Current Level")
    c2.markdown(f"### Student: {u['name']}")
    if c3.button("Logout", use_container_width=True): 
        st.session_state.user = None; st.rerun()
    st.divider()

    t_speak, t_write, t_read, t_listen = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- 1. SPEAKING ---
    with t_speak:
        state = st.session_state.speaking_state
        if not state["active"]:
            st.info("Part 1: Interview | Part 2: Cue Card | Part 3: Discussion")
            if st.button("Start Test"):
                state["active"] = True
                state["test"] = random.choice(SPEAKING_DB)
                state["part"] = 1
                state["q_idx"] = 0
                st.rerun()
        else:
            test = state["test"]
            if state["part"] == 1:
                st.subheader("Part 1")
                q = test['part1'][state['q_idx']]
                st.markdown(f"<div class='question-box'>🗣️ <b>Examiner:</b> {q}</div>", unsafe_allow_html=True)
                audio = st.audio_input("Record Answer")
                if audio:
                    txt = client.audio.transcriptions.create(model="whisper-1", file=audio).text
                    st.session_state.messages.append({"role": "user", "content": txt})
                    if state["q_idx"] < len(test['part1']) - 1:
                        state["q_idx"] += 1
                        st.rerun()
                    else:
                        state["part"] = 2
                        st.rerun()
            elif state["part"] == 2:
                st.subheader("Part 2 (Cue Card)")
                st.info(test['card'])
                if st.button("Start Speaking (2 mins)"): state["part"] = 3; st.rerun()
            elif state["part"] == 3:
                st.subheader("Part 3")
                st.write(f"Question: {test['part3'][0]}")
                if st.audio_input("Final Answer"):
                    st.success("Test Finished. Feedback generating...")
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":"Grade my speaking."}])
                    st.write(res.choices[0].message.content)
                    if st.button("Close"): state["active"]=False; st.rerun()

    # --- 2. WRITING (FIXED IMAGE) ---
    with t_write:
        mode = st.radio("Task:", ["Task 1", "Task 2"], horizontal=True)
        if mode == "Task 1":
            task = WRITING_DB["task1"]
            st.subheader(f"Task 1: {task['type']}")
            # РИСУЕМ ГРАФИК САМИ (ЧТОБЫ НЕ БЫЛО БИТЫХ КАРТИНОК)
            st.line_chart(task['data'])
            st.caption(task['prompt'])
            
            essay1 = st.text_area("Report:", height=200)
            if st.button("Grade Task 1"):
                with st.spinner("Checking..."):
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":f"Grade Task 1: {essay1}"}])
                    st.write(res.choices[0].message.content)
        else:
            prompt = random.choice(WRITING_DB["task2"])
            st.info(prompt)
            essay2 = st.text_area("Essay:", height=300)
            if st.button("Grade Task 2"):
                with st.spinner("Checking..."):
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":f"Grade Task 2: {essay2}"}])
                    st.write(res.choices[0].message.content)

    # --- 3. READING ---
    with t_read:
        exam = READING_DB[0]
        st.subheader(exam['title'])
        st.markdown(f"<div class='exam-paper'>{exam['text']}</div>", unsafe_allow_html=True)
        
        answers = []
        with st.form("read"):
            for i, q in enumerate(exam['questions']):
                st.write(f"**{i+1}. {q['q']}**")
                val = st.radio("Select:", q['options'], key=f"r{i}", label_visibility="collapsed")
                answers.append(val)
            if st.form_submit_button("Submit"):
                score = 0
                for i, ans in enumerate(answers):
                    if ans == exam['questions'][i]['a']: score += 1
                st.success(f"Score: {score}/{len(answers)}")

    # --- 4. LISTENING (REAL AUDIO GENERATION) ---
    with t_listen:
        test = LISTENING_DB[0]
        st.subheader(test['title'])
        st.write(f"Context: {test['context']}")
        
        # ГЕНЕРАЦИЯ АУДИО НА ЛЕТУ (ЧТОБЫ НЕ БЫЛО МУЗЫКИ)
        if "audio_bytes" not in st.session_state:
            with st.spinner("Generating Audio Track..."):
                response = client.audio.speech.create(
                    model="tts-1",
                    voice="alloy", # Голос диктора
                    input=test['script']
                )
                st.session_state.audio_bytes = response.content
        
        st.audio(st.session_state.audio_bytes, format="audio/mp3")
        
        l_ans = []
        with st.form("listen"):
            for i, q in enumerate(test['questions']):
                val = st.text_input(q['label'])
                l_ans.append(val)
            if st.form_submit_button("Check"):
                score = 0
                for i, ans in enumerate(l_ans):
                    if test['questions'][i]['a'].lower() in ans.lower(): score += 1
                st.success(f"Score: {score}/{len(l_ans)}")
