import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import time
import pandas as pd
import numpy as np

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="ALAN | CD-IELTS Simulator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. ADVANCED CSS (COMPUTER-DELIVERED STYLE) ---
st.markdown("""
<style>
    /* Global Clean */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
    /* Split Screen for Reading */
    .scroll-text {
        height: 500px;
        overflow-y: scroll;
        padding: 20px;
        background: #f9f9f9;
        border: 1px solid #ddd;
        border-radius: 8px;
        font-family: 'Georgia', serif;
        line-height: 1.6;
    }
    .dark-mode .scroll-text { background: #333; color: #eee; border: 1px solid #555; }
    
    /* Feedback Box */
    .feedback-box {
        background-color: #e3f2fd;
        border-left: 5px solid #2196f3;
        padding: 15px;
        border-radius: 5px;
        margin-top: 10px;
        color: #0d47a1;
    }
    
    /* Tabs Design */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 16px; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE & CONTENT ---

# WRITING DATA
df_task1 = pd.DataFrame({
    'Year': ['2018', '2019', '2020', '2021', '2022'],
    'Coffee': [15, 20, 45, 60, 80],
    'Tea': [70, 65, 55, 40, 30]
}).set_index('Year')

WRITING_DB = {
    "task1": {
        "title": "Beverage Consumption Trends",
        "data": df_task1,
        "prompt": "The chart below shows the popularity of Coffee vs Tea over 5 years. Summarise the information by selecting and reporting the main features."
    },
    "task2": "In the future, nobody will buy printed newspapers or books because they will be able to read everything online without paying. To what extent do you agree or disagree with this statement?"
}

# READING DATA
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
            {"q": "Crows have a larger brain-to-body ratio than chimpanzees. (True/False/Not Given)", "a": "False", "options": ["True", "False", "Not Given"]},
            {"q": "Farmers dislike crows because they...", "a": "damage crops", "options": []}
        ]
    }
]

# LISTENING DATA
LISTENING_DB = [
    {
        "title": "Section 1: Car Rental Enquiry",
        "script": """
        Good morning, Speedy Car Rentals.
        Hi, I'd like to rent a car for the weekend.
        Certainly. What type of car are you looking for?
        Something small and economical. A compact car.
        Okay. We have a Ford Fiesta available. It is $40 per day.
        That sounds good. Does that include insurance?
        Yes, basic insurance is included. Can I have your name?
        It's Sarah Miller. M-I-L-L-E-R.
        """,
        "context": "Listen to the conversation and complete the booking form.",
        "questions": [
            {"label": "1. Car Type:", "a": "compact"},
            {"label": "2. Cost per day: $", "a": "40"},
            {"label": "3. Customer Surname:", "a": "Miller"}
        ]
    }
]

# SPEAKING DATA
SPEAKING_DB = [
    {
        "topic": "Daily Routine",
        "part1": ["What is your favorite part of the day?", "Do you have a fixed routine?", "How do you organize your study time?"],
        "card": "Describe a time you were very busy.\nYou should say:\n- When it was\n- What you had to do\n- How you managed it\nAnd explain how you felt about it.",
        "part3": ["Is it important to have free time?", "Do people today work harder than in the past?"]
    }
]

# --- 4. BACKEND FUNCTIONS ---
@st.cache_data(show_spinner=False)
def get_tts_audio(text, voice="onyx"):
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        res = client.audio.speech.create(model="tts-1", voice=voice, input=text)
        return res.content
    except: return None

@st.cache_resource
def get_db_connection():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds: creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds)
        return gc.open("IELTS_Users_DB").sheet1
    except: return None

# Auth Logic
def check_login(phone, password):
    ws = get_db_connection()
    if not ws: return None
    try:
        cell = ws.find(phone)
        if cell:
            row = ws.row_values(cell.row)
            # Safe JSON load
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

# --- 5. APP LOGIC ---
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ API Key Missing")
    st.stop()

if "user" not in st.session_state: st.session_state.user = None
if "spk_state" not in st.session_state: st.session_state.spk_state = {"active": False, "part": 1, "idx": 0}

# ==================== AUTHENTICATION ====================
if not st.session_state.user:
    c1, c2 = st.columns([1, 2])
    with c1: st.image("https://cdn-icons-png.flaticon.com/512/5736/5736561.png", width=120)
    with c2: st.title("ALAN | CD-IELTS Simulator")
    
    t1, t2 = st.tabs(["Login", "Register"])
    with t1:
        with st.form("login_f"):
            uid = st.text_input("Student ID:")
            upw = st.text_input("Password:", type="password")
            if st.form_submit_button("Enter Exam Hall"):
                u = check_login(uid, upw)
                if u:
                    st.session_state.user = u
                    st.session_state.messages = u["history"]
                    st.rerun()
                else: st.error("Invalid Credentials")
    with t2:
        with st.form("reg_f"):
            nid = st.text_input("New ID:")
            nnm = st.text_input("Full Name:")
            npw = st.text_input("Password:", type="password")
            if st.form_submit_button("Create Profile"):
                res = register_new(nid, nnm, npw)
                if isinstance(res, dict): 
                    st.session_state.user = res
                    st.session_state.messages = []
                    st.rerun()
                else: st.error(f"Error: {res}")

# ==================== MAIN INTERFACE ====================
else:
    u = st.session_state.user
    
    # Header
    with st.container():
        c1, c2, c3 = st.columns([1, 3, 1])
        c1.metric("Band Score", u['band'])
        c2.subheader(f"Candidate: {u['name']}")
        if c3.button("Save & Exit", type="primary"): 
            st.session_state.user = None; st.rerun()
    st.divider()

    tabs = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- 1. SPEAKING (INTERACTIVE) ---
    with tabs[0]:
        state = st.session_state.spk_state
        test = SPEAKING_DB[0]
        
        if not state["active"]:
            st.info("Part 1: Interview | Part 2: Long Turn | Part 3: Discussion")
            if st.button("Start Speaking Test"):
                state["active"] = True
                state["part"] = 1
                state["idx"] = 0
                st.session_state.messages = [] 
                st.rerun()
        else:
            # Progress bar
            st.progress(33 if state["part"]==1 else 66 if state["part"]==2 else 100)
            
            if state["part"] == 1:
                st.write("### Part 1: Introduction")
                q = test['part1'][state['idx']]
                st.markdown(f"<div class='feedback-box'>🗣️ <b>Alan:</b> {q}</div>", unsafe_allow_html=True)
                
                # Show history (last 2 turns)
                for m in st.session_state.messages[-2:]:
                     with st.chat_message(m["role"]): st.write(m["content"])

                aud = st.audio_input("Record your answer", key=f"p1_{state['idx']}")
                if aud:
                    txt = client.audio.transcriptions.create(model="whisper-1", file=aud).text
                    if txt:
                        st.session_state.messages.append({"role": "user", "content": txt})
                        # Move next
                        if state["idx"] < len(test['part1']) - 1:
                            state["idx"] += 1
                            st.rerun()
                        else:
                            state["part"] = 2
                            st.rerun()

            elif state["part"] == 2:
                st.write("### Part 2: Cue Card")
                st.warning("⏱️ You have 1 minute to prepare.")
                st.info(test['card'])
                if st.button("Start Speaking (2 mins)"): state["part"] = 3; st.rerun()

            elif state["part"] == 3:
                st.write("### Part 3: Discussion")
                st.write(f"**Question:** {test['part3'][0]}")
                aud3 = st.audio_input("Record response", key="p3_fin")
                if aud3:
                    st.success("Test Completed. Generating Feedback...")
                    with st.spinner("Analyzing Fluency, Vocab, Grammar..."):
                        res = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role":"system", "content":"Act as IELTS Examiner. Give strict Band Score and feedback."},
                                      {"role":"user", "content":"Analyze my speaking session."}]
                        )
                        st.markdown(res.choices[0].message.content)
                        if st.button("Finish"): state["active"]=False; st.rerun()

    # --- 2. WRITING (DETAILED FEEDBACK) ---
    with tabs[1]:
        w_task = st.radio("Choose Task:", ["Task 1 (Chart)", "Task 2 (Essay)"], horizontal=True)
        
        if "Task 1" in w_task:
            t1_data = WRITING_DB["task1"]
            st.subheader(t1_data['title'])
            st.bar_chart(t1_data['data'])
            st.caption(t1_data['prompt'])
            
            essay1 = st.text_area("Your Report (150 words):", height=200)
            if st.button("Grade Task 1"):
                with st.spinner("Evaluating..."):
                    prompt = f"""Act as IELTS Examiner. Grade this Task 1. 
                    Input Data: {t1_data['prompt']}. 
                    Essay: {essay1}.
                    Output strictly in Markdown table format with columns: Criteria, Score, Comment.
                    Then provide a Model Answer."""
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                    st.markdown(res.choices[0].message.content)
        else:
            prompt2 = WRITING_DB["task2"]
            st.subheader("Writing Task 2")
            st.info(prompt2)
            essay2 = st.text_area("Your Essay (250 words):", height=300)
            if st.button("Grade Task 2"):
                with st.spinner("Evaluating..."):
                    prompt = f"""Act as IELTS Examiner. Grade this Task 2.
                    Topic: {prompt2}.
                    Essay: {essay2}.
                    Output strictly in Markdown table format with columns: Criteria, Score, Comment.
                    Then provide a corrected Band 9.0 version."""
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                    st.markdown(res.choices[0].message.content)

    # --- 3. READING (SPLIT SCREEN UX) ---
    with tabs[2]:
        r_ex = READING_DB[0]
        
        st.subheader(r_ex['title'])
        
        # SPLIT SCREEN LAYOUT
        col_text, col_questions = st.columns([1, 1])
        
        with col_text:
            st.markdown(f"<div class='scroll-text'>{r_ex['text']}</div>", unsafe_allow_html=True)
            st.caption("Scroll to read the full text ⬆️")

        with col_questions:
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
                
                if st.form_submit_button("Submit Answers"):
                    score = 0
                    for i, a in enumerate(r_ans):
                        correct = r_ex['questions'][i]['a']
                        if str(a).strip().lower() == str(correct).strip().lower():
                            st.success(f"{i+1}. Correct ✅")
                            score += 1
                        else:
                            st.error(f"{i+1}. Wrong ❌ (Ans: {correct})")
                    st.metric("Total Score", f"{score}/{len(r_ans)}")

    # --- 4. LISTENING (AUDIO CACHE) ---
    with tabs[3]:
        l_ex = LISTENING_DB[0]
        st.subheader(l_ex['title'])
        st.write(f"Context: {l_ex['context']}")
        
        # AUDIO
        aud_bytes = get_tts_audio(l_ex['script'])
        if aud_bytes: st.audio(aud_bytes, format="audio/mp3")
        
        with st.form("listen_form"):
            l_inputs = []
            for i, q in enumerate(l_ex['questions']):
                val = st.text_input(q['label'])
                l_inputs.append(val)
            
            if st.form_submit_button("Check Listening"):
                l_score = 0
                for i, a in enumerate(l_inputs):
                    corr = l_ex['questions'][i]['a']
                    if corr.lower() in a.lower():
                        st.success(f"{i+1}. Correct ✅")
                        l_score += 1
                    else:
                        st.error(f"{i+1}. Wrong ❌ (Ans: {corr})")
