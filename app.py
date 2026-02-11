import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import time

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="ALAN | IELTS Official Simulator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. ADVANCED CSS ---
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
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATABASE CONTENT (QUESTION BANK) ---
SPEAKING_DB = [
    {
        "topic": "Hometown & Accommodation",
        "part1": ["Let's talk about where you live. Do you live in a house or an apartment?", "What is your favorite room?", "Do you plan to move soon?"],
        "card": "Describe a house or apartment you would like to live in.\nYou should say:\n- Where it is\n- How big it is\n- Who you would live with\nAnd explain why you want to live there.",
        "part3": ["How have housing types changed in your country?", "Is it better to rent or buy a home?"]
    }
]

WRITING_DB = {
    "task1": [
        {
            "type": "Line Graph",
            "image": "https://www.ielts-mentor.com/images/writingsamples/ielts-line-graph-1.png",
            "prompt": "The graph shows fish and meat consumption in a European country (1979-2004). Summarize the trends."
        }
    ],
    "task2": [
        "Some people say that the best way to improve public health is by increasing the number of sports facilities. Others think that this has little effect and that other measures are required. Discuss both views and give your opinion."
    ]
}

READING_DB = [
    {
        "title": "The History of Tea",
        "text": """
        The story of tea begins in China. According to legend, in 2737 BC, the Chinese emperor Shen Nung was sitting beneath a tree while his servant boiled drinking water, when some leaves from the tree blew into the water. The emperor decided to try the brew.
        Tea consumption spread throughout the Chinese culture, reaching every aspect of the society. In 800 AD, Lu Yu wrote the first definitive book on tea, the Ch'a Ching. This work helped to standardize the cultivation and preparation of tea.
        """,
        "questions": [
            {"q": "Who wrote the first definitive book on tea?", "a": "Lu Yu", "options": []},
            {"q": "Tea was discovered in India. (True/False/Not Given)", "a": "False", "options": ["True", "False", "Not Given"]}
        ]
    }
]

LISTENING_DB = [
    {
        "title": "Section 1: Hotel Booking",
        "audio": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", 
        "context": "You will hear a man phoning a hotel to book a room.",
        "questions": [
            {"label": "1. Number of nights:", "a": "3"},
            {"label": "2. Guest Name: Mr. ______", "a": "Thompson"}
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
        # Структура: Phone, Name, Band, Target, History, Password, Lang
        worksheet.append_row([phone, name, "5.0", "7.0", "[]", password, "English"])
        return get_user(phone)
    except: return "ERROR"

def sync_data(row_id, band):
    if worksheet: worksheet.update_cell(row_id, 3, str(band))

# OPENAI CLIENT
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("API Key Missing.")
    st.stop()

# SESSION STATE
if "user" not in st.session_state: st.session_state.user = None
if "speaking_state" not in st.session_state: st.session_state.speaking_state = {"active": False, "part": 0, "q_idx": 0, "test": None}

# ==================== AUTH SCREEN (LOGIN & REGISTER) ====================
if not st.session_state.user:
    st.title("⚡️ ALAN | IELTS Official Simulator")
    
    # ВОТ ОНА - ВЕРНУВШАЯСЯ РЕГИСТРАЦИЯ!
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    
    with tab1:
        with st.form("login_form"):
            ph = st.text_input("Student ID (Phone):")
            pw = st.text_input("Password:", type="password")
            if st.form_submit_button("Start Exam"):
                u = get_user(ph)
                if u and u["pwd"] == pw:
                    st.session_state.user = u
                    st.session_state.messages = u["history"]
                    st.rerun()
                else: st.error("Invalid ID or Password")
                
    with tab2:
        with st.form("reg_form"):
            new_ph = st.text_input("New Student ID (Phone):")
            new_name = st.text_input("Full Name:")
            new_pw = st.text_input("Create Password:", type="password")
            if st.form_submit_button("Register"):
                if new_ph and new_name and new_pw:
                    res = register_user(new_ph, new_name, new_pw)
                    if res == "EXISTS":
                        st.error("User already exists!")
                    elif res == "ERROR" or res == "DB_ERROR":
                        st.error("Database Error. Try again.")
                    else:
                        st.success("Account created! Logging in...")
                        st.session_state.user = res
                        st.session_state.messages = []
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("Please fill all fields.")

# ==================== EXAM PLATFORM ====================
else:
    u = st.session_state.user
    
    # --- HEADER ---
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.metric("Band Score", u['band'], delta="Current Level")
    c2.markdown(f"### Student: {u['name']}")
    if c3.button("Save & Logout", use_container_width=True): 
        st.session_state.user = None; st.rerun()
    st.divider()

    # --- TABS ---
    t_speak, t_write, t_read, t_listen = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- 1. SPEAKING MODULE ---
    with t_speak:
        state = st.session_state.speaking_state
        
        if not state["active"]:
            st.markdown("<div class='exam-paper'><h3>Speaking Test</h3><p>Duration: 11-14 minutes. Includes Part 1, 2 and 3.</p></div>", unsafe_allow_html=True)
            if st.button("Start Speaking Test"):
                state["active"] = True
                state["test"] = random.choice(SPEAKING_DB)
                state["part"] = 1
                state["q_idx"] = 0
                st.rerun()
        else:
            test = state["test"]
            
            # PART 1
            if state["part"] == 1:
                st.subheader("Part 1: Introduction")
                current_q = test['part1'][state['q_idx']]
                st.markdown(f"<div class='question-box'>🗣️ <b>Examiner:</b> {current_q}</div>", unsafe_allow_html=True)
                
                for msg in st.session_state.messages[-3:]:
                    with st.chat_message(msg["role"]): st.write(msg["content"])

                audio = st.audio_input("Record Answer", key="spk_p1")
                if audio:
                    txt = client.audio.transcriptions.create(model="whisper-1", file=audio).text
                    st.session_state.messages.append({"role": "user", "content": txt})
                    
                    if state["q_idx"] < len(test['part1']) - 1:
                        state["q_idx"] += 1
                        st.success("Answer recorded. Next question...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        state["part"] = 2
                        st.rerun()

            # PART 2
            elif state["part"] == 2:
                st.subheader("Part 2: Cue Card")
                st.markdown(f"<div class='exam-paper'><b>Topic:</b><br>{test['card']}</div>", unsafe_allow_html=True)
                st.info("You have 1 minute to think. (Timer is running...)")
                
                if st.button("I am ready to start speaking (2 mins)"):
                     state["part"] = 3
                     st.rerun()

            # PART 3
            elif state["part"] == 3:
                st.subheader("Part 3: Discussion")
                st.markdown(f"<div class='question-box'>Let's discuss: {test['part3'][0]}</div>", unsafe_allow_html=True)
                
                audio_p3 = st.audio_input("Record Final Answer", key="spk_p3")
                if audio_p3:
                    st.success("Test Finished. Generating Feedback...")
                    resp = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": "Give IELTS Band Score and Feedback."}, 
                                  {"role": "user", "content": "Analyze my previous answers."}]
                    )
                    st.markdown(resp.choices[0].message.content)
                    if st.button("Close Test"):
                        state["active"] = False
                        st.rerun()

    # --- 2. WRITING MODULE ---
    with t_write:
        mode = st.radio("Choose Task:", ["Task 1", "Task 2"], horizontal=True)
        
        if mode == "Task 1":
            if "w_task1" not in st.session_state: st.session_state.w_task1 = random.choice(WRITING_DB["task1"])
            task = st.session_state.w_task1
            st.image(task['image'], width=500)
            st.markdown(f"**Prompt:** {task['prompt']}")
            
            essay1 = st.text_area("Report (min 150 words):", height=200)
            if st.button("Grade Task 1"):
                with st.spinner("Alan is marking..."):
                    res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": f"Act as IELTS Examiner. Grade this Task 1 report based on image description: '{task['prompt']}'. Report: {essay1}"}]
                    )
                    st.markdown(res.choices[0].message.content)

        else:
            if "w_task2" not in st.session_state: st.session_state.w_task2 = random.choice(WRITING_DB["task2"])
            prompt = st.session_state.w_task2
            st.markdown(f"<div class='question-box'>{prompt}</div>", unsafe_allow_html=True)
            
            essay2 = st.text_area("Essay (min 250 words):", height=300)
            if st.button("Grade Task 2"):
                with st.spinner("Alan is marking..."):
                    res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": f"Act as IELTS Examiner. Grade this Task 2 Essay strictly. Essay: {essay2}"}]
                    )
                    st.markdown(res.choices[0].message.content)

    # --- 3. READING MODULE ---
    with t_read:
        if "r_exam" not in st.session_state: st.session_state.r_exam = random.choice(READING_DB)
        exam = st.session_state.r_exam
        
        c1, c2 = st.columns([3,1])
        c1.markdown(f"### {exam['title']}")
        if c2.button("🔄 New Text"): st.session_state.r_exam = random.choice(READING_DB); st.rerun()
        
        st.markdown(f"<div class='exam-paper'>{exam['text']}</div>", unsafe_allow_html=True)
        
        score = 0
        with st.form("read_form"):
            user_answers = []
            for i, q in enumerate(exam['questions']):
                st.write(f"**{i+1}. {q['q']}**")
                if q['options']:
                    val = st.radio("Select:", q['options'], key=f"r_{i}", label_visibility="collapsed")
                else:
                    val = st.text_input("Answer:", key=f"r_{i}", label_visibility="collapsed")
                user_answers.append(val)
            
            if st.form_submit_button("Submit Answers"):
                st.write("### Results:")
                for i, ans in enumerate(user_answers):
                    correct = exam['questions'][i]['a']
                    if ans.lower().strip() == correct.lower():
                        st.markdown(f"{i+1}. ✅ Correct")
                        score += 1
                    else:
                        st.markdown(f"{i+1}. ❌ Your answer: **{ans}** | Correct: <span class='correct'>{correct}</span>", unsafe_allow_html=True)
                
                st.info(f"Total Score: {score}/{len(exam['questions'])}")

    # --- 4. LISTENING MODULE ---
    with t_listen:
        if "l_exam" not in st.session_state: st.session_state.l_exam = random.choice(LISTENING_DB)
        lexam = st.session_state.l_exam
        
        st.markdown(f"### {lexam['title']}")
        st.write(f"Context: {lexam['context']}")
        st.audio(lexam['audio'])
        
        score_l = 0
        with st.form("listen_form"):
            l_answers = []
            for i, q in enumerate(lexam['questions']):
                val = st.text_input(q['label'], key=f"l_{i}")
                l_answers.append(val)
            
            if st.form_submit_button("Check Listening"):
                st.write("### Results:")
                for i, ans in enumerate(l_answers):
                    correct = lexam['questions'][i]['a']
                    if ans.lower().strip() == correct.lower():
                        st.markdown(f"{i+1}. ✅ Correct")
                        score_l += 1
                    else:
                        st.markdown(f"{i+1}. ❌ Correct answer: <span class='correct'>{correct}</span>", unsafe_allow_html=True)
