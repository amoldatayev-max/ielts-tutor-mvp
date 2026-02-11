import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import time

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="ALAN | Ultimate IELTS Simulator",
    page_icon="🎓",
    layout="wide"
)

# --- 2. DATABASE (КОНТЕНТ ЗАДАНИЙ) ---
# Здесь мы храним все варианты вопросов. Можно добавлять бесконечно.

# SPEAKING: Темы для всех 3 частей
SPEAKING_DB = [
    {
        "topic": "Hometown & Travel",
        "part1": ["Where is your hometown?", "Is it a good place for young people?", "Do you often travel?"],
        "card": "Describe a place you visited that you would recommend to others.\nYou should say:\n- Where it is\n- When you went there\n- What you did there\nAnd explain why you recommend it.",
        "part3": ["Why do some people prefer traveling alone?", "How has tourism changed in your country?"]
    },
    {
        "topic": "Technology & Work",
        "part1": ["Do you use computers often?", "What app do you use the most?", "Do you prefer working alone or in a group?"],
        "card": "Describe a piece of technology you use every day.\nYou should say:\n- What it is\n- How often you use it\n- What you use it for\nAnd explain how it helps you.",
        "part3": ["Will robots replace teachers in the future?", "Is technology making people lazy?"]
    }
]

# WRITING: Task 1 (Images) & Task 2 (Essays)
WRITING_DB = {
    "task1": [
        {
            "type": "Line Graph",
            "image": "https://www.ielts-mentor.com/images/writingsamples/ielts-line-graph-1.png", # Реальный пример графика
            "prompt": "The graph below shows the consumption of fish and different kinds of meat in a European country between 1979 and 2004. Summarise the information by selecting and reporting the main features."
        },
        {
            "type": "Map",
            "image": "https://www.ielts-mentor.com/images/writingsamples/ielts-map-writing-1.png",
            "prompt": "The maps below show the changes in a town called Stokeford between 1930 and 2010. Summarise the information."
        }
    ],
    "task2": [
        "Some people believe that unpaid community service should be a compulsory part of high school programmes. To what extent do you agree or disagree?",
        "Computers are being used more and more in education. Some people say that this is a positive trend, while others argue that it leads to negative consequences. Discuss both sides and give your opinion."
    ]
}

# READING: Разные типы вопросов
READING_DB = [
    {
        "type": "Matching Headings",
        "title": "The History of Tea",
        "text": """
        [Paragraph A] The story of tea begins in China. According to legend, in 2737 BC, the Chinese emperor Shen Nung was sitting beneath a tree while his servant boiled drinking water, when some leaves from the tree blew into the water. The emperor decided to try the brew.
        
        [Paragraph B] Tea consumption spread throughout the Chinese culture, reaching every aspect of the society. In 800 AD, Lu Yu wrote the first definitive book on tea, the Ch'a Ching. This work helped to standardize the cultivation and preparation of tea.
        
        [Paragraph C] Tea was introduced to the West by Portuguese priests and merchants in China during the 16th century. Drinking tea became fashionable among Britons during the 17th century, who started large-scale production and commercialization of the plant in India.
        """,
        "questions": [
            {"q": "Choose heading for Paragraph A", "options": ["i. The spread to the West", "ii. Origins and Myth", "iii. Standardization"], "a": "ii. Origins and Myth"},
            {"q": "Choose heading for Paragraph B", "options": ["i. Cultural Impact", "ii. Modern Production", "iii. The Emperor's Drink"], "a": "i. Cultural Impact"}
        ]
    },
    {
        "type": "True / False / Not Given",
        "title": "Urbanization",
        "text": "Urbanization allows more people to access education and healthcare. However, it also leads to higher pollution levels and cost of living. Studies show that by 2050, 68% of the world population will live in cities.",
        "questions": [
            {"q": "Urbanization reduces the cost of living. (T/F/NG)", "options": ["True", "False", "Not Given"], "a": "False"},
            {"q": "The majority of people will live in cities by 2050. (T/F/NG)", "options": ["True", "False", "Not Given"], "a": "True"}
        ]
    }
]

# LISTENING: Maps & Forms
LISTENING_DB = [
    {
        "type": "Form Filling",
        "title": "Section 1: Library Registration",
        "audio": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3", # Заглушка (в реале нужен файл диалога)
        "context": "You will hear a student registering at a library. Listen and complete the form.",
        "questions": [
            {"label": "Surname: ", "a": "Black"},
            {"label": "Address: 24 ______ Street", "a": "Park"}
        ]
    },
    {
        "type": "Map Labelling",
        "title": "Section 2: Campus Tour",
        "image": "https://ielts-up.com/images/listening/listening-map-labeling-1.png", # Пример карты
        "audio": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "context": "Look at the map of the university campus. Label the buildings.",
        "questions": [
            {"label": "Building A is the: ", "a": "Library"},
            {"label": "Building C is the: ", "a": "Cafeteria"}
        ]
    }
]

# --- 3. CSS (DESIGN) ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .exam-box { padding: 20px; background: #f0f2f6; border-radius: 10px; margin-bottom: 20px; color: #333; }
    .card-box { border: 2px dashed #444; padding: 20px; background: #fff9c4; color: #333; border-radius: 5px; }
    .stTabs [data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

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

def sync_data(row_id, band):
    if worksheet: worksheet.update_cell(row_id, 3, str(band))

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "user" not in st.session_state: st.session_state.user = None
if "speaking_state" not in st.session_state: st.session_state.speaking_state = {"part": 0, "q_index": 0, "test": None}

# ==================== LOGIN ====================
if not st.session_state.user:
    st.title("⚡️ ALAN | Ultimate IELTS Simulator")
    with st.form("auth"):
        ph = st.text_input("ID:")
        pw = st.text_input("Password:", type="password")
        if st.form_submit_button("Start Exam"):
            u = get_user(ph)
            if u and u["pwd"] == pw:
                st.session_state.user = u
                st.session_state.messages = u["history"]
                st.rerun()
            else: st.error("Access Denied")

# ==================== MAIN APP ====================
else:
    u = st.session_state.user
    
    # --- HEADER ---
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.metric("Band Score", u['band'])
    c2.markdown(f"### Student: {u['name']}")
    if c3.button("Exit"): st.session_state.user = None; st.rerun()
    st.divider()

    # --- TABS ---
    t_speak, t_write, t_read, t_listen = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- 1. SPEAKING (FULL TEST GENERATOR) ---
    with t_speak:
        state = st.session_state.speaking_state
        
        # Генерация нового теста
        if state["test"] is None:
            if st.button("🚀 Generate New Full Test"):
                state["test"] = random.choice(SPEAKING_DB)
                state["part"] = 1
                state["q_index"] = 0
                st.rerun()
            st.info("Click to start a full 15-minute speaking simulation.")
            
        else:
            test = state["test"]
            
            # --- PART 1 ---
            if state["part"] == 1:
                st.subheader(f"Part 1: {test['topic']}")
                q = test['part1'][state['q_index']]
                st.markdown(f"**Examiner asks:** {q}")
                
                # Chat History
                for msg in st.session_state.messages[-4:]:
                    with st.chat_message(msg["role"]): st.write(msg["content"])
                
                audio = st.audio_input("Answer Part 1")
                if audio:
                    ans = client.audio.transcriptions.create(model="whisper-1", file=audio).text
                    st.session_state.messages.append({"role": "user", "content": ans})
                    
                    # Logic to move next
                    if state["q_index"] < len(test['part1']) - 1:
                        state["q_index"] += 1
                        feedback = "Good. Next question."
                    else:
                        state["part"] = 2 # Move to Part 2
                        feedback = "Thank you. Now let's move to Part 2."
                    
                    st.rerun()

            # --- PART 2 (CUE CARD) ---
            elif state["part"] == 2:
                st.subheader("Part 2: Individual Long Turn")
                st.markdown(f"<div class='card-box'>{test['card']}</div>", unsafe_allow_html=True)
                st.warning("⏱️ You have 1 minute to prepare and 2 minutes to speak.")
                
                if st.button("I am ready to speak"):
                     state["part"] = 3
                     st.rerun()

            # --- PART 3 ---
            elif state["part"] == 3:
                st.subheader("Part 3: Discussion")
                st.write("Deep discussion based on Part 2.")
                st.info("Simulation Finished for this Demo.")
                if st.button("Finish Test"):
                    state["test"] = None
                    st.rerun()

    # --- 2. WRITING (TASK 1 & 2) ---
    with t_write:
        w_type = st.radio("Select Task:", ["Task 1 (Academic Graph)", "Task 2 (Essay)"], horizontal=True)
        
        if "Task 1" in w_type:
            # Случайное задание Task 1
            if "w_task1" not in st.session_state: st.session_state.w_task1 = random.choice(WRITING_DB["task1"])
            task = st.session_state.w_task1
            
            st.subheader(f"Task 1: {task['type']}")
            st.image(task['image'], width=600) # 

[Image of Graph]

            st.write(f"**Prompt:** {task['prompt']}")
            
            ans = st.text_area("Report (min 150 words):", height=200)
            if st.button("Check Task 1"):
                st.success("Analyzing graph description...")
                # GPT logic here
                
        else:
            # Случайное задание Task 2
            if "w_task2" not in st.session_state: st.session_state.w_task2 = random.choice(WRITING_DB["task2"])
            prompt = st.session_state.w_task2
            
            st.subheader("Task 2: Essay")
            st.info(prompt)
            ans = st.text_area("Essay (min 250 words):", height=300)
            if st.button("Check Task 2"):
                st.success("Grading Essay...")

    # --- 3. READING (DYNAMIC TYPES) ---
    with t_read:
        if "r_test" not in st.session_state: st.session_state.r_test = random.choice(READING_DB)
        exam = st.session_state.r_test
        
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"### {exam['title']} ({exam['type']})")
        if c2.button("🔄 New Text"): 
            st.session_state.r_test = random.choice(READING_DB)
            st.rerun()
            
        st.markdown(f"<div class='exam-box'>{exam['text']}</div>", unsafe_allow_html=True)
        
        score = 0
        with st.form("reading_form"):
            for i, q in enumerate(exam['questions']):
                st.write(f"**Q{i+1}: {q['q']}**")
                val = st.radio(f"Select {i}", q['options'], key=f"rq{i}", label_visibility="collapsed")
                if val == q['a']: score += 1
            
            if st.form_submit_button("Submit"):
                st.info(f"Score: {score}/{len(exam['questions'])}")
                if score == len(exam['questions']): st.balloons()

    # --- 4. LISTENING (MAPS & FORMS) ---
    with t_listen:
        if "l_test" not in st.session_state: st.session_state.l_test = random.choice(LISTENING_DB)
        test = st.session_state.l_test
        
        c1, c2 = st.columns([3, 1])
        c1.markdown(f"### {test['title']} ({test['type']})")
        if c2.button("🔄 New Audio"): 
            st.session_state.l_test = random.choice(LISTENING_DB)
            st.rerun()
            
        st.write(f"**Context:** {test['context']}")
        
        # Если есть картинка (Карта)
        if "image" in test:
            st.image(test['image']) # 

[Image of Map]

        
        st.audio(test['audio'])
        
        with st.form("listen_form"):
            score = 0
            for i, q in enumerate(test['questions']):
                user_ans = st.text_input(q['label'], key=f"lq{i}")
                if user_ans.lower().strip() == q['a'].lower(): score += 1
            
            if st.form_submit_button("Check Listening"):
                st.success(f"Correct Answers: {score}/{len(test['questions'])}")
