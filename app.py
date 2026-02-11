import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import time
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(
    page_title="ZEST AI | IELTS Titanium",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. ELITE CSS STYLING ---
st.markdown("""
<style>
    /* Global Reset */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
    /* Modern Card Design */
    .stApp { background-color: #f8f9fa; }
    .css-1y4p8pa { padding-top: 0rem; }
    
    .exam-card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid #f0f0f0;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .exam-card:hover { transform: translateY(-2px); }
    
    /* Typography */
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #2c3e50; }
    .highlight { color: #3498db; font-weight: bold; }
    
    /* Split Screen Scrollable Area */
    .scroll-container {
        max-height: 400px;
        overflow-y: auto;
        padding-right: 10px;
        border-right: 2px solid #eee;
    }
    
    /* Badges */
    .badge-correct { background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .badge-wrong { background-color: #f8d7da; color: #721c24; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    
    /* Dark Mode Support */
    @media (prefers-color-scheme: dark) {
        .stApp { background-color: #0e1117; }
        .exam-card { background: #262730; border: 1px solid #444; }
        h1, h2, h3 { color: #ecf0f1; }
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA & CONTENT MANAGERS ---

class ContentManager:
    """Manages all static and dynamic exam content."""
    
    @staticmethod
    def get_speaking_topic():
        return {
            "topic": "Technology & AI",
            "part1": ["Do you use AI tools often?", "Has technology changed how you study?", "Do you prefer online or offline classes?"],
            "card": "Describe a piece of technology you want to buy.\nYou should say:\n- What it is\n- How much it costs\n- What features it has\nAnd explain why you want it.",
            "part3": ["Will robots replace teachers?", "Is privacy dead in the digital age?"]
        }

    @staticmethod
    def get_writing_task1():
        # Dynamic Data Generation for uniqueness
        df = pd.DataFrame({
            'Year': ['2018', '2019', '2020', '2021', '2022'],
            'Mobile': np.random.randint(20, 50, 5),
            'Desktop': np.random.randint(40, 70, 5)
        }).set_index('Year')
        return {
            "title": "Device Usage Trends",
            "data": df,
            "prompt": "The chart illustrates the usage of Mobile vs Desktop for internet access over 5 years."
        }

    @staticmethod
    def get_reading_test():
        return {
            "title": "The Future of Space Exploration",
            "text": """
            Space exploration has entered a new era, driven largely by private companies rather than government agencies. Companies like SpaceX and Blue Origin are reducing the cost of launching payloads into orbit through reusable rocket technology.
            
            Historically, space travel was the exclusive domain of superpowers. The Apollo missions demonstrated immense national capability but were incredibly expensive. In contrast, the 'New Space' industry focuses on commercial viability and sustainability.
            
            One of the primary goals of modern exploration is the colonization of Mars. Elon Musk has stated that humanity must become a multi-planetary species to ensure survival. However, critics argue that we should focus on repairing Earth's climate before attempting to terraform another planet.
            """,
            "questions": [
                {"q": "Who is driving the new era of space exploration?", "a": "private companies", "options": ["Governments", "Private companies", "Universities"]},
                {"q": "The main goal of New Space is national prestige. (True/False)", "a": "False", "options": ["True", "False", "Not Given"]},
                {"q": "Elon Musk wants to colonize...", "a": "Mars", "options": []}
            ]
        }

    @staticmethod
    def get_listening_test():
        return {
            "title": "Section 1: Event Registration",
            "script": """
            Good morning, Tech Conference Registration.
            Hello, I'd like to register for the upcoming AI Summit.
            Certainly. Can I have your full name?
            Yes, it is John Anderson.
            And what is your company name?
            I work for Global Tech Solutions.
            Okay. The fee is $150. Would you like to pay now?
            Yes, please.
            """,
            "context": "Complete the form based on the call.",
            "questions": [
                {"label": "1. Attendee Name:", "a": "John Anderson"},
                {"label": "2. Company: Global ______ Solutions", "a": "Tech"},
                {"label": "3. Fee: $", "a": "150"}
            ]
        }

# --- 4. CORE LOGIC MANAGERS ---

class DBHandler:
    """Handles Google Sheets connections safely."""
    @staticmethod
    @st.cache_resource
    def connect():
        try:
            creds = dict(st.secrets["gcp_service_account"])
            if "private_key" in creds: creds["private_key"] = creds["private_key"].replace("\\n", "\n")
            gc = gspread.service_account_from_dict(creds)
            return gc.open("IELTS_Users_DB").sheet1
        except: return None

    @staticmethod
    def get_user(phone):
        ws = DBHandler.connect()
        if not ws: return None
        try:
            cell = ws.find(phone)
            if cell:
                row = ws.row_values(cell.row)
                hist = json.loads(row[4]) if len(row) > 4 and row[4] else []
                return {"row": cell.row, "name": row[1], "band": row[2], "target": row[3], "history": hist, "pwd": str(row[5])}
        except: return None

    @staticmethod
    def register(phone, name, password):
        ws = DBHandler.connect()
        if not ws: return "DB_ERROR"
        try:
            if ws.find(phone): return "EXISTS"
            ws.append_row([phone, name, "5.0", "7.0", "[]", password, "English"])
            return DBHandler.get_user(phone)
        except: return "ERROR"

class AIHandler:
    """Manages OpenAI interactions with fallbacks."""
    
    @staticmethod
    @st.cache_data(show_spinner=False)
    def generate_audio(text, voice="alloy"):
        if "OPENAI_API_KEY" not in st.secrets: return None
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            res = client.audio.speech.create(model="tts-1", voice=voice, input=text)
            return res.content
        except: return None

    @staticmethod
    def grade_text(task_type, content, context=""):
        if "OPENAI_API_KEY" not in st.secrets: 
            return "⚠️ AI Unavailable. Simulation Mode: Great effort! Estimated Band: 6.5. Focus on grammar."
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            prompt = f"Act as IELTS Examiner. Grade {task_type}. Context: {context}. User Answer: {content}. Keep it brief."
            res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
            return res.choices[0].message.content
        except: return "⚠️ Error connecting to AI. Please try again later."

    @staticmethod
    def transcribe(audio_file):
        if "OPENAI_API_KEY" not in st.secrets: return "Simulation text answer."
        try:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            return client.audio.transcriptions.create(model="whisper-1", file=audio_file).text
        except: return None

# --- 5. INITIALIZATION ---

if "user" not in st.session_state: st.session_state.user = None
if "spk" not in st.session_state: st.session_state.spk = {"active": False, "part": 1, "idx": 0}

# ==================== LOGIN SYSTEM ====================
if not st.session_state.user:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>ZEST AI <span style='color:#00c853'>.</span></h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: grey;'>Premium IELTS Simulator</p>", unsafe_allow_html=True)
        
        tab_login, tab_reg = st.tabs(["Login", "Join Class"])
        
        with tab_login:
            with st.form("login_form"):
                uid = st.text_input("Student ID (Phone)")
                upw = st.text_input("Password", type="password")
                if st.form_submit_button("Enter Dashboard", use_container_width=True):
                    user = DBHandler.get_user(uid)
                    if user and user["pwd"] == upw:
                        st.session_state.user = user
                        st.session_state.messages = user["history"]
                        st.rerun()
                    else: st.error("Invalid Credentials")
        
        with tab_reg:
            with st.form("reg_form"):
                new_id = st.text_input("Phone Number")
                new_name = st.text_input("Full Name")
                new_pw = st.text_input("Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    res = DBHandler.register(new_id, new_name, new_pw)
                    if isinstance(res, dict):
                        st.session_state.user = res
                        st.session_state.messages = []
                        st.rerun()
                    else: st.error(f"Registration Failed: {res}")

# ==================== MAIN DASHBOARD ====================
else:
    u = st.session_state.user
    
    # TOP BAR
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1: st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)
    with c2: 
        st.write(f"**{u['name']}**")
        st.progress(float(u['band'])/9.0) # Visual Band Progress
    with c3: 
        if st.button("Logout"): st.session_state.user = None; st.rerun()
    
    st.markdown("---")
    
    tabs = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- MODULE 1: SPEAKING ---
    with tabs[0]:
        state = st.session_state.spk
        content = ContentManager.get_speaking_topic()
        
        if not state["active"]:
            st.info("Full IELTS Speaking Test Simulation")
            col_a, col_b = st.columns(2)
            col_a.metric("Est. Duration", "12 mins")
            col_b.metric("Focus", content["topic"])
            if st.button("Start Interview", type="primary"):
                state["active"] = True
                state["part"] = 1
                state["idx"] = 0
                st.session_state.messages = [] 
                st.rerun()
        else:
            # Phase Indicator
            st.caption(f"Phase: Part {state['part']} / 3")
            st.progress(33 * state["part"])
            
            if state["part"] == 1:
                st.subheader("Part 1: Interview")
                q = content['part1'][state['idx']]
                
                with st.chat_message("assistant", avatar="👨‍💻"):
                    st.write(q)
                
                # Show history (last 1 turn)
                if st.session_state.messages:
                    last_msg = st.session_state.messages[-1]
                    with st.chat_message("user"): st.write(last_msg["content"])

                audio = st.audio_input("Answer", key=f"spk_1_{state['idx']}")
                if audio:
                    txt = AIHandler.transcribe(audio)
                    if txt:
                        st.session_state.messages.append({"role": "user", "content": txt})
                        if state["idx"] < len(content['part1']) - 1:
                            state["idx"] += 1
                        else:
                            state["part"] = 2
                        st.rerun()

            elif state["part"] == 2:
                st.subheader("Part 2: Cue Card")
                with st.container(border=True):
                    st.markdown(content['card'])
                st.warning("⏱️ You have 1 minute to prepare notes.")
                if st.button("Start Speaking (2 mins)"): state["part"] = 3; st.rerun()

            elif state["part"] == 3:
                st.subheader("Part 3: Discussion")
                st.write(content['part3'][0])
                fin_aud = st.audio_input("Final Response", key="spk_3")
                if fin_aud:
                    txt = AIHandler.transcribe(fin_aud)
                    with st.spinner("AI Examiner is grading..."):
                        fb = AIHandler.grade_text("Speaking", txt)
                        st.success("Test Complete!")
                        st.markdown(f"<div class='exam-card'>{fb}</div>", unsafe_allow_html=True)
                    if st.button("Finish"): state["active"] = False; st.rerun()

    # --- MODULE 2: WRITING ---
    with tabs[1]:
        w_mode = st.radio("Select Task", ["Task 1 (Chart)", "Task 2 (Essay)"], horizontal=True)
        
        if "Task 1" in w_mode:
            task = ContentManager.get_writing_task1()
            col_img, col_inp = st.columns([1, 1])
            
            with col_img:
                st.subheader(task['title'])
                st.bar_chart(task['data']) # Dynamic Chart
                st.caption(task['prompt'])
            
            with col_inp:
                essay1 = st.text_area("Your Report", height=300, placeholder="Write at least 150 words...")
                if st.button("Evaluate Task 1"):
                    with st.spinner("Grading..."):
                        fb = AIHandler.grade_text("Writing Task 1", essay1, task['prompt'])
                        st.markdown(fb)
        else:
            st.subheader("Task 2: Essay")
            st.info("Some people believe that AI will replace teachers. Discuss.")
            essay2 = st.text_area("Your Essay", height=400, placeholder="Write at least 250 words...")
            if st.button("Evaluate Task 2"):
                with st.spinner("Grading..."):
                    fb = AIHandler.grade_text("Writing Task 2", essay2)
                    st.markdown(fb)

    # --- MODULE 3: READING (CBT STYLE) ---
    with tabs[2]:
        test = ContentManager.get_reading_test()
        st.subheader(test['title'])
        
        c_text, c_questions = st.columns([1, 1])
        
        with c_text:
            # Native Streamlit Scroll Container (Mobile Friendly)
            with st.container(height=500, border=True):
                st.markdown(test['text'])
        
        with c_questions:
            st.write("### Questions")
            with st.form("reading_form"):
                answers = []
                for i, q in enumerate(test['questions']):
                    st.markdown(f"**{i+1}. {q['q']}**")
                    if q['options']:
                        val = st.radio("Select:", q['options'], key=f"rq{i}", label_visibility="collapsed")
                    else:
                        val = st.text_input("Answer:", key=f"rq{i}", label_visibility="collapsed")
                    answers.append(val)
                
                if st.form_submit_button("Submit Answers"):
                    score = 0
                    for i, a in enumerate(answers):
                        correct = test['questions'][i]['a']
                        if str(a).strip().lower() == str(correct).strip().lower():
                            st.markdown(f"{i+1}. <span class='badge-correct'>Correct</span>", unsafe_allow_html=True)
                            score += 1
                        else:
                            st.markdown(f"{i+1}. <span class='badge-wrong'>Wrong</span> (Ans: {correct})", unsafe_allow_html=True)
                    st.metric("Total Score", f"{score}/{len(answers)}")

    # --- MODULE 4: LISTENING (SAFE MODE) ---
    with tabs[3]:
        test = ContentManager.get_listening_test()
        st.subheader(test['title'])
        st.write(f"Context: {test['context']}")
        
        # Audio Player with Fallback
        audio_bytes = AIHandler.generate_audio(test['script'])
        if audio_bytes:
            st.audio(audio_bytes, format="audio/mp3")
        else:
            st.warning("⚠️ Simulation Audio Used (Network Error)")
            st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")

        with st.form("listening_form"):
            l_answers = []
            for i, q in enumerate(test['questions']):
                val = st.text_input(q['label'])
                l_answers.append(val)
            
            if st.form_submit_button("Check Listening"):
                score = 0
                for i, a in enumerate(l_answers):
                    correct = test['questions'][i]['a']
                    if correct.lower() in a.lower():
                        st.markdown(f"{i+1}. <span class='badge-correct'>Correct</span>", unsafe_allow_html=True)
                        score += 1
                    else:
                        st.markdown(f"{i+1}. <span class='badge-wrong'>Wrong</span>", unsafe_allow_html=True)
                st.metric("Score", f"{score}/{len(l_answers)}")
            
