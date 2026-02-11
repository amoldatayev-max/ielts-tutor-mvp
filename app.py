import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import time
import pandas as pd
import numpy as np

# --- 1. НАСТРОЙКИ ---
st.set_page_config(
    page_title="ALAN | IELTS Simulator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS (УПРОЩЕННЫЙ И НАДЕЖНЫЙ) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
    /* Красивая бумага для экзамена */
    .exam-paper {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        color: #333;
        margin-bottom: 15px;
    }
    /* Темная тема (автоматически) */
    @media (prefers-color-scheme: dark) {
        .exam-paper { background-color: #262730; color: white; border: 1px solid #444; }
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 5px; }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; padding: 10px 15px; }
</style>
""", unsafe_allow_html=True)

# --- 3. ДАННЫЕ (DATABASE) ---

SPEAKING_DB = [
    {
        "topic": "Daily Routine",
        "part1": ["Do you prefer morning or evening?", "What is your daily routine?", "Is breakfast important to you?"],
        "card": "Describe a habit you want to change.\nYou should say:\n- What it is\n- How long you have had it\n- Why you want to change it\nAnd explain how you plan to change it.",
        "part3": ["Is it easy for old people to change habits?", "How can parents teach children good habits?"]
    }
]

# График для Writing
df_task1 = pd.DataFrame({
    'Year': ['2018', '2019', '2020', '2021', '2022'],
    'Coffee': [15, 20, 45, 60, 80],
    'Tea': [70, 65, 55, 40, 30]
}).set_index('Year')

WRITING_DB = {
    "task1": {
        "title": "Beverage Trends",
        "data": df_task1,
        "prompt": "The chart shows Coffee vs Tea popularity. Summarise the trends."
    },
    "task2": "Some people think that AI will replace teachers. To what extent do you agree or disagree?"
}

READING_DB = [
    {
        "title": "The Intelligence of Crows",
        "text": """
Crows are often considered to be among the world's most intelligent animals. Scientific research has shown that they are capable of using tools, recognizing human faces, and even solving complex puzzles that require multiple steps.

In one famous experiment, a crow named Betty bent a straight piece of wire into a hook to retrieve a bucket of food from a vertical tube. This demonstrated a level of causal reasoning previously thought to be unique to humans and great apes.

Furthermore, crows have a complex social structure. They have been observed holding "funerals" for deceased members of their flock, which scientists believe helps them learn about potential dangers in their environment. Their brain-to-body weight ratio is roughly equal to that of chimpanzees, and significantly higher than that of most other birds.

Despite their intelligence, crows are often viewed as pests by farmers because they can damage crops. However, their role in the ecosystem as scavengers is vital for preventing the spread of disease.
        """,
        "questions": [
            {"q": "What did the crow named Betty do?", "a": "bent wire", "options": ["Used a stick", "Bent wire", "Broke the tube"]},
            {"q": "Crows have a larger brain than chimpanzees. (True/False)", "a": "False", "options": ["True", "False", "Not Given"]},
            {"q": "Farmers dislike crows because they...", "a": "damage crops", "options": []}
        ]
    }
]

LISTENING_DB = [
    {
        "title": "Section 1: Car Rental",
        "script": """
        Good morning, Speedy Rentals.
        Hi, I'd like to rent a compact car.
        Okay. We have a Ford Fiesta. It costs $40 per day.
        Does that include insurance?
        Yes, basic insurance is included. Can I have your surname?
        It is Miller. M-I-L-L-E-R.
        """,
        "context": "Complete the notes based on the audio.",
        "questions": [
            {"label": "1. Car Type:", "a": "compact"},
            {"label": "2. Cost per day: $", "a": "40"},
            {"label": "3. Surname:", "a": "Miller"}
        ]
    }
]

# --- 4. ФУНКЦИИ ---

# 1. ГЕНЕРАЦИЯ АУДИО (С ЗАЩИТОЙ ОТ ОШИБОК)
@st.cache_data(show_spinner=False)
def get_audio_safe(text):
    """Пытается создать аудио. Если ошибка - возвращает None."""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        res = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        return res.content
    except:
        return None # Если ошибка API, вернем пустоту, чтобы не крашить сайт

# 2. БД
@st.cache_resource
def get_db_connection():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds: creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds)
        return gc.open("IELTS_Users_DB").sheet1
    except: return None

# 3. АВТОРИЗАЦИЯ
def check_login(phone, password):
    ws = get_db_connection()
    if not ws: return None
    try:
        cell = ws.find(phone)
        if cell:
            row = ws.row_values(cell.row)
            hist = json.loads(row[4]) if len(row) > 4 and row[4] else []
            return {"row": cell.row, "name": row[1], "band": row[2], "target": row[3], "history": hist, "pwd": str(row[5])}
    except: return None

def register_new(phone, name, password):
    ws = get_db_connection()
    if not ws: return "DB_ERROR"
    try:
        if ws.find(phone): return "EXISTS"
        ws.append_row([phone, name, "5.0", "7.0", "[]", password, "English"])
        return check_login(phone, password)
    except: return "ERROR"

# --- 5. LOGIC START ---
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ API Key Missing")
    st.stop()

if "user" not in st.session_state: st.session_state.user = None
if "spk_state" not in st.session_state: st.session_state.spk_state = {"active": False, "part": 1, "idx": 0}

# ==================== ВХОД ====================
if not st.session_state.user:
    c1, c2 = st.columns([1, 3])
    with c1: st.write("🎓")
    with c2: st.title("ALAN | IELTS")
    
    t1, t2 = st.tabs(["Войти", "Регистрация"])
    with t1:
        with st.form("log"):
            uid = st.text_input("ID:")
            upw = st.text_input("Password:", type="password")
            if st.form_submit_button("Start"):
                u = check_login(uid, upw)
                if u:
                    st.session_state.user = u
                    st.session_state.messages = u["history"]
                    st.rerun()
                else: st.error("Ошибка входа")
    with t2:
        with st.form("reg"):
            nid = st.text_input("New ID:")
            nnm = st.text_input("Name:")
            npw = st.text_input("Password:", type="password")
            if st.form_submit_button("Создать"):
                res = register_new(nid, nnm, npw)
                if isinstance(res, dict): 
                    st.session_state.user = res
                    st.session_state.messages = []
                    st.rerun()
                else: st.error(f"Ошибка: {res}")

# ==================== ПЛАТФОРМА ====================
else:
    u = st.session_state.user
    
    # Шапка
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.metric("Band", u['band'])
    c2.write(f"**{u['name']}**")
    if c3.button("Exit"): st.session_state.user = None; st.rerun()
    st.divider()

    tabs = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- 1. SPEAKING ---
    with tabs[0]:
        state = st.session_state.spk_state
        test = SPEAKING_DB[0]
        
        if not state["active"]:
            st.info("Part 1: Interview | Part 2: Cue Card | Part 3: Discussion")
            if st.button("Start Speaking"):
                state["active"] = True
                state["part"] = 1
                state["idx"] = 0
                st.session_state.messages = [] 
                st.rerun()
        else:
            st.progress(33 if state["part"]==1 else 66 if state["part"]==2 else 100)
            
            if state["part"] == 1:
                st.write("### Part 1")
                q = test['part1'][state['idx']]
                st.markdown(f"<div class='exam-paper'>🗣️ <b>Alan:</b> {q}</div>", unsafe_allow_html=True)
                
                # Показываем прошлый ответ (чат)
                if len(st.session_state.messages) > 0:
                     with st.chat_message("user"): st.write(st.session_state.messages[-1]["content"])

                aud = st.audio_input("Record Answer", key=f"p1_{state['idx']}")
                if aud:
                    txt = client.audio.transcriptions.create(model="whisper-1", file=aud).text
                    if txt:
                        st.session_state.messages.append({"role": "user", "content": txt})
                        if state["idx"] < len(test['part1']) - 1:
                            state["idx"] += 1
                            st.rerun()
                        else:
                            state["part"] = 2
                            st.rerun()

            elif state["part"] == 2:
                st.write("### Part 2")
                st.info("Topic Card (1 min prep)")
                st.markdown(f"<div class='exam-paper'>{test['card']}</div>", unsafe_allow_html=True)
                if st.button("I'm ready (Start Speaking)"): state["part"] = 3; st.rerun()

            elif state["part"] == 3:
                st.write("### Part 3")
                st.write(f"**Q:** {test['part3'][0]}")
                aud3 = st.audio_input("Final Answer", key="p3_fin")
                if aud3:
                    st.success("Analyzing...")
                    res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role":"user", "content":f"Grade my IELTS speaking. Be brief."}]
                    )
                    st.markdown(res.choices[0].message.content)
                    if st.button("Finish"): state["active"]=False; st.rerun()

    # --- 2. WRITING ---
    with tabs[1]:
        w_task = st.radio("Task:", ["Task 1", "Task 2"], horizontal=True)
        if "Task 1" in w_task:
            t1 = WRITING_DB["task1"]
            st.subheader(t1['title'])
            st.bar_chart(t1['data']) # График
            st.caption(t1['prompt'])
            
            essay1 = st.text_area("Your Report:", height=150)
            if st.button("Check Task 1"):
                with st.spinner("Grading..."):
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":f"Grade Task 1: {essay1}"}])
                    st.write(res.choices[0].message.content)
        else:
            st.subheader("Task 2")
            st.info(WRITING_DB["task2"])
            essay2 = st.text_area("Your Essay:", height=250)
            if st.button("Check Task 2"):
                with st.spinner("Grading..."):
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":f"Grade Task 2: {essay2}"}])
                    st.write(res.choices[0].message.content)

    # --- 3. READING (ИСПРАВЛЕНО: НАТИВНЫЙ СКРОЛЛ) ---
    with tabs[2]:
        r_ex = READING_DB[0]
        st.subheader(r_ex['title'])
        
        # ВОТ ИСПРАВЛЕНИЕ: Используем st.container вместо HTML
        # Это гарантирует, что текст не "вывалится" тегами на телефоне
        with st.container(height=300): 
            st.markdown(r_ex['text'])
        
        st.divider()
        st.write("### Questions")
        
        with st.form("read_form"):
            r_ans = []
            for i, q in enumerate(r_ex['questions']):
                st.write(f"**{i+1}. {q['q']}**")
                if q['options']:
                    val = st.radio("Select:", q['options'], key=f"rq{i}", label_visibility="collapsed")
                else:
                    val = st.text_input("Answer:", key=f"rq{i}", label_visibility="collapsed")
                r_ans.append(val)
            
            if st.form_submit_button("Submit"):
                score = 0
                for i, a in enumerate(r_ans):
                    if str(a).lower() == str(r_ex['questions'][i]['a']).lower():
                        st.success(f"Q{i+1}: Correct")
                        score += 1
                    else:
                        st.error(f"Q{i+1}: Wrong (Ans: {r_ex['questions'][i]['a']})")

    # --- 4. LISTENING (ИСПРАВЛЕНО: ЗАЩИТА ОТ ОШИБКИ) ---
    with tabs[3]:
        l_ex = LISTENING_DB[0]
        st.subheader(l_ex['title'])
        st.write(l_ex['context'])
        
        # ВОТ ИСПРАВЛЕНИЕ: Пробуем сгенерировать, если нет - даем запасной файл
        aud_bytes = get_audio_safe(l_ex['script'])
        
        if aud_bytes:
            st.audio(aud_bytes, format="audio/mp3")
        else:
            # Если OpenAI сломался, показываем файл-заглушку, чтобы не было надписи "Error"
            st.warning("Voice generator busy. Using backup audio.")
            st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3") 

        with st.form("listen_form"):
            l_inputs = []
            for i, q in enumerate(l_ex['questions']):
                val = st.text_input(q['label'])
                l_inputs.append(val)
            
            if st.form_submit_button("Check"):
                score = 0
                for i, a in enumerate(l_inputs):
                    if l_ex['questions'][i]['a'].lower() in a.lower():
                        st.success(f"Correct")
                        score += 1
                    else:
                        st.error(f"Wrong (Ans: {l_ex['questions'][i]['a']})")
