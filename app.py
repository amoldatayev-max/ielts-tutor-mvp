import streamlit as st
from openai import OpenAI
import gspread
import json
import random
import re

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="ALAN | Official IELTS Simulator", page_icon="🎓", layout="wide")

# Улучшенный CSS для профессионального вида
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { 
        padding: 10px 25px; 
        font-weight: bold;
        border-radius: 10px 10px 0 0;
    }
    .exam-container {
        padding: 25px;
        background-color: #f8f9fa;
        color: #1a1a1a;
        border-radius: 15px;
        border-left: 5px solid #007bff;
        margin-bottom: 20px;
    }
    @media (prefers-color-scheme: dark) {
        .exam-container { background-color: #262730; color: white; }
    }
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ---
@st.cache_resource(ttl=600)
def get_db_connection():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds:
            creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(creds)
        return gc.open("IELTS_Users_DB").sheet1
    except: return None

worksheet = get_db_connection()

# --- 3. AUTH & SYNC ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            hist = json.loads(row[4]) if len(row) > 4 else []
            return {"row_id": cell.row, "name": row[1], "band": row[2], "target": row[3], "history": hist, "password": str(row[5]), "lang": row[6]}
    except: return None

def sync(row_id, band=None, history=None):
    if not worksheet: return
    if band: worksheet.update_cell(row_id, 3, str(band))
    if history: worksheet.update_cell(row_id, 5, json.dumps(history, ensure_ascii=False))

# --- 4. REAL EXAM CONTENT ---
READING_CONTENT = {
    "title": "The Evolution of Language",
    "text": """Language is a complex system of communication that is unique to human beings. While many animals possess basic forms of communication, such as birdsong or whale calls, human language is characterized by its infinite flexibility and creativity. Linguists have long debated the origins of language, with some suggesting it emerged as a byproduct of increased brain size, while others argue it was a specific evolutionary adaptation for social cooperation.

One prominent theory, proposed by Noam Chomsky, is the 'Universal Grammar' hypothesis. This suggests that the human brain contains an innate capacity for language, which is hard-wired from birth. However, critics of this view point to the vast diversity of the world's 7,000 languages as evidence that language is primarily a cultural construct learned through social interaction.

As societies became more complex, the need for written language emerged. The earliest forms of writing were pictographic, but these eventually evolved into the sophisticated alphabetic systems we use today. In the modern era, technology is once again transforming language, with the rise of digital communication leading to new forms of slang and altered grammatical structures.""",
    "questions": [
        "1. According to the text, what makes human language different from animal communication?",
        "2. Noam Chomsky believes that language ability is learned through social interaction. (True/False/Not Given)",
        "3. How many languages are estimated to exist in the world today?"
    ],
    "answers": ["flexibility", "false", "7000"]
}

WRITING_PROMPT = """**Writing Task 2**
You should spend about 40 minutes on this task. 
Write about the following topic:

*In many countries, traditional customs and behaviors are being lost as people follow a more global culture. To what extent do you agree or disagree with this statement?*

Give reasons for your answer and include any relevant examples from your own knowledge or experience. 
**Write at least 250 words.**"""

# --- 5. INITIALIZATION ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
if "user" not in st.session_state: st.session_state.user = None

# ==================== AUTH ====================
if not st.session_state.user:
    st.title("🎓 ZEST AI | IELTS Official Simulator")
    st.info("Please login to access all exam modules.")
    with st.form("auth"):
        ph = st.text_input("ID (Phone):")
        pw = st.text_input("Password:", type="password")
        if st.form_submit_button("Enter Exam Hall"):
            u = load_user(ph)
            if u and u["password"] == pw:
                st.session_state.user = u
                st.session_state.messages = u["history"]
                st.rerun()
            else: st.error("Invalid Credentials.")

# ==================== EXAM PORTAL ====================
else:
    user = st.session_state.user
    
    # --- HEADER ---
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: st.metric("Current Band Score", user['band'])
    with c2: 
        st.markdown(f"### Candidate: {user['name']}")
        st.caption("Exam Mode: Active")
    with c3:
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    st.divider()

    # --- TABS ---
    tab_s, tab_w, tab_r, tab_l = st.tabs(["🎙️ SPEAKING", "📝 WRITING", "📖 READING", "🎧 LISTENING"])

    # --- 🎙️ SPEAKING SECTION ---
    with tab_s:
        st.markdown("### IELTS Speaking Simulator")
        
        st.write("**Current Phase:** Part 1 (Introduction and Interview)")
        
        for msg in st.session_state.messages[-4:]:
            if msg["role"] != "system":
                with st.chat_message(msg["role"], avatar="👨‍💻" if msg["role"]=="assistant" else "👤"):
                    st.markdown(msg["content"])

        audio_val = st.audio_input("Answer ALAN 🎙️")
        if audio_val:
            u_text = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
            st.session_state.messages.append({"role": "user", "content": u_text})
            
            with st.chat_message("assistant", avatar="👨‍💻"):
                prompt = f"You are ALAN, an official IELTS examiner. Phase: Part 1. Evaluate: '{u_text}'. Provide: 1. A short correction. 2. A follow-up question. 3. Tag: [BAND: X.X]"
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "system", "content": prompt}] + st.session_state.messages[-5:])
                ai_text = resp.choices[0].message.content
                
                # Update Band logic
                match = re.search(r"\[BAND:\s*([\d\.]+)\]", ai_text)
                if match:
                    user['band'] = match.group(1)
                    sync(user['row_id'], band=match.group(1))
                    st.toast(f"Band Updated: {match.group(1)}", icon="🎓")
                    ai_text = re.sub(r"\[.*?\]", "", ai_text).strip()

                st.markdown(ai_text)
                v = client.audio.speech.create(model="tts-1", voice="onyx", input=ai_text)
                st.audio(v.content, format="audio/mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
                sync(user['row_id'], history=st.session_state.messages)
                st.rerun()

    # --- 📝 WRITING SECTION ---
    with tab_w:
        st.markdown("### Writing Task 2")
        
        st.info(WRITING_PROMPT)
        essay = st.text_area("Write your response here (min 250 words):", height=400)
        word_count = len(essay.split())
        st.write(f"Word count: **{word_count}**")
        
        if st.button("Submit Essay for Marking"):
            if word_count < 100: st.error("Essay is too short.")
            else:
                with st.spinner("ALAN is analyzing your Task Response, Cohesion, Lexical Resource, and Grammar..."):
                    res = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": f"Grade this IELTS Task 2 Essay strictly based on 4 criteria. Give a band score: {essay}"}]
                    )
                    st.success("Analysis Complete")
                    st.markdown(res.choices[0].message.content)

    # --- 📖 READING SECTION ---
    with tab_r:
        st.markdown(f"### Academic Reading: {READING_CONTENT['title']}")
        
        with st.container():
            st.markdown(f"<div class='exam-container'>{READING_CONTENT['text']}</div>", unsafe_allow_html=True)
        
        st.divider()
        st.write("#### Answer the following questions:")
        q1 = st.text_input(READING_CONTENT['questions'][0])
        q2 = st.radio(READING_CONTENT['questions'][1], ["True", "False", "Not Given"])
        q3 = st.text_input(READING_CONTENT['questions'][2])
        
        if st.button("Check Reading Answers"):
            score = 0
            if READING_CONTENT['answers'][0] in q1.lower(): score += 1
            if q2.lower() == READING_CONTENT['answers'][1]: score += 1
            if READING_CONTENT['answers'][2] in q3: score += 1
            
            b = "8.5" if score == 3 else "6.5" if score == 2 else "4.5" if score == 1 else "3.0"
            st.success(f"Score: {score}/3 | Estimated Band: {b}")
            user['band'] = b
            sync(user['row_id'], band=b)

    # --- 🎧 LISTENING SECTION ---
    with tab_l:
        st.markdown("### IELTS Listening: Section 1 (Social Context)")
        
        st.write("**Scenario:** A student is inquiring about a library membership at a university desk.")
        # Authentic listening placeholder (Educational)
        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3") 
        
        st.write("#### Fill in the blanks (Max 2 words):")
        la1 = st.text_input("1. Name of the library: _________ Library")
        la2 = st.text_input("2. Cost of annual membership: £ _________")
        
        if st.button("Check Listening Score"):
            if "central" in la1.lower() and "15" in la2:
                st.success("Correct! Band 9.0 performance.")
            else:
                st.warning("Keep practicing. Your estimated band is 5.5.")
