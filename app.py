import streamlit as st
from openai import OpenAI
import gspread
import json
import random

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="ALAN | IELTS Platform", page_icon="⚡️", layout="wide") # WIDE LAYOUT

# --- 2. CSS (СТИЛИ) ---
css = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Красивые метрики */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #00C853;
    }
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# --- 3. БД ---
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

# --- 4. ФУНКЦИИ ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            hist = row[4] if len(row) > 4 else "[]"
            pwd = row[5] if len(row) > 5 else "" 
            lang = row[6] if len(row) > 6 else "English" 
            try: h = json.loads(hist)
            except: h = []
            return {"row_id": cell.row, "name": row[1], "level": row[2], "target": row[3], "history": h, "password": str(pwd), "native_lang": lang}
    except: return None

def register_user(phone, name, level, target, password, native_lang):
    if not worksheet: return None
    try:
        if worksheet.find(phone): return "EXISTS"
        worksheet.append_row([phone, name, level, target, "[]", password, native_lang])
        return load_user(phone)
    except: return None

def save_history(row_id, messages):
    if not worksheet: return
    try: worksheet.update_cell(row_id, 5, json.dumps(messages, ensure_ascii=False))
    except: pass

def get_wod():
    words = [("Ubiquitous", "Вездесущий"), ("Ephemeral", "Мимолетный"), ("Eloquent", "Красноречивый"), ("Resilient", "Устойчивый")]
    return random.choice(words)

# --- 5. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets: st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state: st.session_state.user = None
if "messages" not in st.session_state: st.session_state.messages = []
if "wod" not in st.session_state: st.session_state.wod = get_wod()

# ==================== ВХОД ====================
if not st.session_state.user:
    st.title("⚡️ ALAN | IELTS Platform")
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])
    with tab1:
        with st.form("login"):
            ph = st.text_input("ID:")
            pw = st.text_input("Password:", type="password")
            if st.form_submit_button("Start"):
                ud = load_user(ph)
                if ud and str(ud["password"]).strip() == str(pw).strip():
                    st.session_state.user = ud
                    st.session_state.messages = ud["history"]
                    st.rerun()
                else: st.error("Error")
    with tab2:
        with st.form("reg"):
            n_ph = st.text_input("ID:")
            n_pw = st.text_input("Pass:")
            n_nm = st.text_input("Name:")
            n_la = st.selectbox("Lang:", ["Kazakh", "Russian", "English"])
            if st.form_submit_button("Create"):
                r = register_user(n_ph, n_nm, "Int", "7.0", n_pw, n_la)
                if r: 
                    st.session_state.user = r
                    st.session_state.messages = []
                    st.rerun()

# ==================== ПЛАТФОРМА ====================
else:
    user = st.session_state.user
    
    # --- МЕНЮ (НАВИГАЦИЯ) ---
    with st.sidebar:
        st.title("ALAN ⚡️")
        mode = st.radio("Select Mode:", ["🎙️ Speaking Coach", "📝 Writing Grader"])
        
        st.divider()
        st.info(f"💡 Word: **{st.session_state.wod[0]}**")
        
        if st.button("🚪 Logout"):
            st.session_state.user = None
            st.rerun()

    # ================== РЕЖИМ 1: SPEAKING ==================
    if mode == "🎙️ Speaking Coach":
        st.header("Speaking Simulator")
        
        # Кнопка оценки
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("📊 Grade My Speaking"):
                if len(st.session_state.messages) < 4:
                    st.warning("Not enough data. Speak more!")
                else:
                    with st.spinner("Analyzing..."):
                        # Анализ истории
                        conversation = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]])
                        eval_prompt = f"Analyze this IELTS conversation. Give estimated Band Score (0-9) for: Fluency, Vocabulary, Grammar, Pronunciation. Be strict. Output JSON."
                        
                        try:
                            # Фейковая симуляция оценки для скорости (в реале нужен запрос к GPT)
                            # Но мы сделаем реальный быстрый запрос
                            eval_res = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "system", "content": "You are IELTS Examiner. Provide brief feedback and Estimated Band Score based on user inputs."}, 
                                          {"role": "user", "content": conversation}]
                            )
                            st.success(eval_res.choices[0].message.content)
                        except: st.error("Error grading.")

        # ЧАТ
        if not st.session_state.messages:
            sys = f"Role: IELTS Coach ALAN. Lang: {user['native_lang']}. Style: Brief, Correct errors. Ask next question."
            st.session_state.messages.append({"role": "system", "content": sys})
            st.session_state.messages.append({"role": "assistant", "content": "Let's start Part 1. What is your full name?"})

        for msg in st.session_state.messages:
            if msg["role"] != "system":
                av = "👨‍💻" if msg["role"] == "assistant" else "👤"
                with st.chat_message(msg["role"], avatar=av):
                    st.markdown(msg["content"])

        # ВВОД
        audio_val = st.audio_input("Voice 🎙️")
        text_val = st.chat_input("Type...")

        user_in = None
        if audio_val:
            try: user_in = client.audio.transcriptions.create(model="whisper-1", file=audio_val).text
            except: pass
        elif text_val: user_in = text_val

        if user_in:
            st.session_state.messages.append({"role": "user", "content": user_in})
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_in)

            with st.chat_message("assistant", avatar="👨‍💻"):
                full_resp = ""
                ph = st.empty()
                stream = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        full_resp += chunk.choices[0].delta.content
                        ph.markdown(full_resp + " ▌")
                ph.markdown(full_resp)
                
                # Ключ для аудио
                try:
                    response = client.audio.speech.create(model="tts-1", voice="onyx", input=full_resp)
                    st.audio(response.content, format="audio/mp3", key=f"aud_{len(st.session_state.messages)}")
                except: pass

            st.session_state.messages.append({"role": "assistant", "content": full_resp})
            save_history(user["row_id"], st.session_state.messages)

    # ================== РЕЖИМ 2: WRITING GRADER ==================
    elif mode == "📝 Writing Grader":
        st.header("Writing Task 2 Check")
        st.caption("Paste your essay below. Alan will grade it and rewrite it to Band 9.0.")
        
        topic = st.text_input("Essay Topic (Question):", placeholder="e.g., Some people think technology makes us lazy...")
        essay_text = st.text_area("Your Essay:", height=300)
        
        if st.button("📝 Check My Essay"):
            if essay_text and topic:
                with st.spinner("Alan is marking your paper..."):
                    prompt = f"""
                    Act as a strict IELTS Examiner.
                    Topic: {topic}
                    Essay: {essay_text}
                    
                    Task:
                    1. Give an estimated Band Score (0-9).
                    2. List 3 main grammar/vocab errors.
                    3. Rewrite the essay to be a perfect Band 9.0 version.
                    """
                    
                    res = client.chat.completions.create(
                        model="gpt-4o", # Тут лучше использовать мощную модель
                        messages=[{"role": "user", "content": prompt}]
                    )
                    
                    st.markdown("### 📊 Feedback")
                    st.write(res.choices[0].message.content)
            else:
                st.warning("Please enter topic and essay.")
