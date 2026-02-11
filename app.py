import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import time
import pandas as pd
import numpy as np

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(
    page_title="ALAN | IELTS Simulator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. УМНОЕ КЕШИРОВАНИЕ (ЭКОНОМИЯ ДЕНЕГ) ---
@st.cache_data(show_spinner=False)
def generate_ielts_audio(text, voice="alloy"):
    """Генерирует аудио 1 раз и запоминает его."""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.audio.speech.create(model="tts-1", voice=voice, input=text)
        return response.content
    except: return None

@st.cache_resource
def get_db():
    """Подключение к БД с защитой от сбоев."""
    try:
        creds = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds: creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds)
        return gc.open("IELTS_Users_DB").sheet1
    except: return None

# --- 3. CSS (ПРОФЕССИОНАЛЬНЫЙ ВИД) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .exam-paper {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        color: #333;
        margin-bottom: 20px;
    }
    .question-label { font-weight: bold; color: #444; margin-top: 10px; }
    .correct-badge { background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }
    .wrong-badge { background-color: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)

# --- 4. КОНТЕНТ (DATABASE) ---

# SPEAKING
SPEAKING_DB = [
    {
        "topic": "Work & Studies",
        "part1": ["Do you work or are you a student?", "Why did you choose this field?", "Do you prefer working alone or in a team?"],
        "card": "Describe a job you would like to do in the future.\nYou should say:\n- What it is\n- What skills you need\n- Why you want to do it\nAnd explain if it is difficult to get this job.",
        "part3": ["Is salary the most important factor in a job?", "How has the job market changed in your country?"]
    }
]

# WRITING (С ГЕНЕРАТОРОМ ДАННЫХ)
df_task1 = pd.DataFrame({
    'Year': ['2000', '2005', '2010', '2015', '2020'],
    'Online Sales': [10, 25, 45, 70, 95],
    'Retail Sales': [90, 85, 75, 60, 40]
}).set_index('Year')

WRITING_DB = {
    "task1": {
        "type": "Bar Chart",
        "data": df_task1,
        "prompt": "The chart shows the percentage of sales from Online vs Retail stores over a 20-year period."
    },
    "task2": "Many people believe that video games have a negative effect on children. Others argue that they can be educational. Discuss both views."
}

# READING
READING_DB = [
    {
        "title": "The Bees",
        "text": """
        Honey bees are social insects that live in colonies. The colony is highly organized, with three castes: the queen, drones, and workers. 
        The queen is the only fertile female and can lay up to 2,000 eggs per day. Drones are male bees whose sole purpose is to mate with the queen. 
        Worker bees are sterile females who perform all the labor, including cleaning the hive, feeding larvae, and foraging for nectar.
        Interestingly, bees communicate through a 'waggle dance' to indicate the location of food sources.
        """,
        "questions": [
            {"q": "How many eggs can a queen lay per day?", "a": "2000", "options": []},
            {"q": "Worker bees are male. (True/False)", "a": "False", "options": ["True", "False", "Not Given"]},
            {"q": "What do bees use to communicate food location?", "a": "waggle dance", "options": []}
        ]
    }
]

# LISTENING (SCRIPT)
LISTENING_DB = [
    {
        "title": "Section 1: Gym Membership",
        "script": """
        Good morning, FitLife Gym. How can I help you?
        Hi, I'd like to ask about membership prices.
        Sure. Our basic monthly fee is $30.
        Okay, that sounds reasonable. And what is the joining fee?
        It is usually $50, but we have a discount today, so it is only $25.
        Great! Can I sign up now? My name is David Jones.
        """,
        "context": "Complete the notes below based on the phone conversation.",
        "questions": [
            {"label": "1. Monthly Fee: $", "a": "30"},
            {"label": "2. Discounted Joining Fee: $", "a": "25"},
            {"label": "3. Applicant Name: David _____", "a": "Jones"}
        ]
    }
]

# --- 5. LOGIC & AUTH ---
def get_user(phone):
    ws = get_db()
    if not ws: return None
    try:
        cell = ws.find(phone)
        if cell:
            row = ws.row_values(cell.row)
            hist = json.loads(row[4]) if len(row) > 4 else []
            return {"row": cell.row, "name": row[1], "band": row[2], "target": row[3], "history": hist, "pwd": str(row[5])}
    except: return None

def register_user(phone, name, password):
    ws = get_db()
    if not ws: return "DB_ERROR"
    try:
        if ws.find(phone): return "EXISTS"
        ws.append_row([phone, name, "5.0", "7.0", "[]", password, "English"])
        return get_user(phone)
    except: return "ERROR"

if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ API Key Not Found")
    st.stop()

if "user" not in st.session_state: st.session_state.user = None
if "spk_state" not in st.session_state: st.session_state.spk_state = {"active": False, "part": 1, "idx": 0}

# ==================== ВХОД / РЕГИСТРАЦИЯ ====================
if not st.session_state.user:
    c1, c2 = st.columns([1,2])
    c1.image("https://cdn-icons-png.flaticon.com/512/2997/2997274.png", width=120)
    c2.title("ALAN | IELTS Simulator")
    
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        with st.form("log"):
            id_ = st.text_input("ID:")
            pw = st.text_input("Pass:", type="password")
            if st.form_submit_button("Enter"):
                u = get_user(id_)
                if u and u["pwd"] == pw:
                    st.session_state.user = u
                    st.session_state.messages = u["history"]
                    st.rerun()
                else: st.error("Wrong ID/Pass")
    with t2:
        with st.form("reg"):
            nid = st.text_input("New ID:")
            nnm = st.text_input("Name:")
            npw = st.text_input("Create Pass:", type="password")
            if st.form_submit_button("Register"):
                res = register_user(nid, nnm, npw)
                if res in ["EXISTS", "ERROR", "DB_ERROR"]: st.error(f"Error: {res}")
                else: 
                    st.session_state.user = res
                    st.session_state.messages = []
                    st.rerun()

# ==================== ПЛАТФОРМА ====================
else:
    u = st.session_state.user
    
    # Header
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.metric("Band Score", u['band'])
    c2.markdown(f"### Student: **{u['name']}**")
    if c3.button("Logout"): st.session_state.user = None; st.rerun()
    st.divider()

    tabs = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- 1. SPEAKING (ROBUST STATE MACHINE) ---
    with tabs[0]:
        state = st.session_state.spk_state
        test = SPEAKING_DB[0]
        
        if not state["active"]:
            st.info("Full IELTS Speaking Test (Part 1, 2, 3)")
            if st.button("Start Test"):
                state["active"] = True
                state["part"] = 1
                state["idx"] = 0
                st.session_state.messages = [] # Сброс чата для нового теста
                st.rerun()
        else:
            # Отображаем прогресс
            st.progress(33 if state["part"]==1 else 66 if state["part"]==2 else 100)
            
            if state["part"] == 1:
                st.subheader("Part 1: Interview")
                q = test['part1'][state['idx']]
                st.markdown(f"<div class='exam-paper'>🗣️ <b>Examiner:</b> {q}</div>", unsafe_allow_html=True)
                
                # Chat History display
                for m in st.session_state.messages[-3:]:
                     with st.chat_message(m["role"]): st.write(m["content"])

                audio = st.audio_input("Your Answer", key=f"p1_{state['idx']}")
                if audio:
                    txt = client.audio.transcriptions.create(model="whisper-1", file=audio).text
                    st.session_state.messages.append({"role": "user", "content": txt})
                    
                    # Продвижение вперед
                    if state["idx"] < len(test['part1']) - 1:
                        state["idx"] += 1
                        st.rerun()
                    else:
                        state["part"] = 2
                        st.rerun()

            elif state["part"] == 2:
                st.subheader("Part 2: Cue Card")
                st.warning("You have 1 minute to prepare.")
                st.markdown(f"<div class='exam-paper'>{test['card']}</div>", unsafe_allow_html=True)
                if st.button("I'm ready (Start Speaking)"): state["part"] = 3; st.rerun()

            elif state["part"] == 3:
                st.subheader("Part 3: Discussion")
                st.write(f"Question: {test['part3'][0]}")
                final_aud = st.audio_input("Final Answer", key="p3_fin")
                if final_aud:
                    st.success("Test Complete! Analyzing...")
                    with st.spinner("AI is grading..."):
                         res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":"Grade my speaking session based on IELTS criteria."}])
                         st.markdown(res.choices[0].message.content)
                    if st.button("Finish"): state["active"] = False; st.rerun()

    # --- 2. WRITING (BETTER CHARTS) ---
    with tabs[1]:
        w_mode = st.radio("Select Task:", ["Task 1 (Graph)", "Task 2 (Essay)"], horizontal=True)
        
        if "Task 1" in w_mode:
            task = WRITING_DB["task1"]
            st.subheader("Academic Writing Task 1")
            
            # Используем Bar Chart для профессионального вида
            st.bar_chart(task['data']) 
            st.caption(task['prompt'])
            
            w_ans = st.text_area("Report (150 words):", height=200)
            if st.button("Evaluate Task 1"):
                with st.spinner("Grading..."):
                    fb = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":f"Grade Task 1: {w_ans}"}])
                    st.write(fb.choices[0].message.content)
        else:
            prompt = WRITING_DB["task2"]
            st.subheader("Writing Task 2")
            st.info(prompt)
            w_essay = st.text_area("Essay (250 words):", height=300)
            if st.button("Evaluate Task 2"):
                with st.spinner("Grading..."):
                    fb = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":f"Grade Task 2: {w_essay}"}])
                    st.write(fb.choices[0].message.content)

    # --- 3. READING (SMART FEEDBACK) ---
    with tabs[2]:
        r_test = READING_DB[0]
        st.subheader(r_test['title'])
        st.markdown(f"<div class='exam-paper'>{r_test['text']}</div>", unsafe_allow_html=True)
        
        r_score = 0
        with st.form("read_f"):
            user_r_ans = []
            for i, q in enumerate(r_test['questions']):
                st.write(f"**{i+1}. {q['q']}**")
                if q['options']:
                    val = st.radio("Select:", q['options'], key=f"rq{i}", label_visibility="collapsed")
                else:
                    val = st.text_input("Answer:", key=f"rq{i}", label_visibility="collapsed")
                user_r_ans.append(val)
            
            if st.form_submit_button("Submit Answers"):
                st.write("### 📊 Results")
                for i, ans in enumerate(user_r_ans):
                    corr = r_test['questions'][i]['a']
                    # Умное сравнение (без учета регистра и пробелов)
                    if str(ans).strip().lower() == str(corr).strip().lower():
                        st.markdown(f"{i+1}. <span class='correct-badge'>Correct</span>", unsafe_allow_html=True)
                        r_score += 1
                    else:
                        st.markdown(f"{i+1}. <span class='wrong-badge'>Wrong</span> (Correct: {corr})", unsafe_allow_html=True)
                st.info(f"Total: {r_score}/{len(r_test['questions'])}")

    # --- 4. LISTENING (CACHED AUDIO) ---
    with tabs[3]:
        l_test = LISTENING_DB[0]
        st.subheader(l_test['title'])
        st.write(f"Context: {l_test['context']}")
        
        # ГЕНЕРАЦИЯ АУДИО (С КЕШЕМ!)
        audio_data = generate_ielts_audio(l_test['script'])
        if audio_data:
            st.audio(audio_data, format="audio/mp3")
        else:
            st.error("Audio generation failed.")

        with st.form("list_f"):
            l_inputs = []
            for i, q in enumerate(l_test['questions']):
                val = st.text_input(q['label'])
                l_inputs.append(val)
            
            if st.form_submit_button("Check Listening"):
                l_score = 0
                st.write("### 📊 Results")
                for i, ans in enumerate(l_inputs):
                    corr = l_test['questions'][i]['a']
                    if corr.lower() in ans.lower():
                        st.markdown(f"{i+1}. <span class='correct-badge'>Correct</span>", unsafe_allow_html=True)
                        l_score += 1
                    else:
                        st.markdown(f"{i+1}. <span class='wrong-badge'>Wrong</span> (Expected: {corr})", unsafe_allow_html=True)
                st.info(f"Total: {l_score}/{len(l_test['questions'])}")
