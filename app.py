import streamlit as st
from openai import OpenAI
import gspread
import json

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Coach Arman", page_icon="🇰🇿", layout="centered")

# --- 2. КОНТАКТЫ АДМИНА ---
ADMIN_CONTACT = "https://t.me/aligassan_m" 

# --- 3. ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ---
def get_db_connection():
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in credentials_dict:
            credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(credentials_dict)
        sh = gc.open("IELTS_Users_DB")
        return sh.sheet1
    except Exception as e:
        st.error(f"Ошибка БД: {e}")
        return None

worksheet = get_db_connection()

# --- 4. ФУНКЦИИ ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            history_data = row[4] if len(row) > 4 else "[]"
            password_data = row[5] if len(row) > 5 else "" 
            return {
                "row_id": cell.row,
                "name": row[1],
                "level": row[2],
                "target": row[3],
                "history": json.loads(history_data),
                "password": str(password_data)
            }
    except:
        return None
    return None

def register_user(phone, name, level, target, password):
    if not worksheet: return None
    try:
        if worksheet.find(phone): return "EXISTS"
        worksheet.append_row([phone, name, level, target, "[]", password])
        return load_user(phone)
    except:
        return None

def save_history(row_id, messages):
    if not worksheet: return
    history_str = json.dumps(messages, ensure_ascii=False)
    worksheet.update_cell(row_id, 5, history_str)

# --- 5. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Нет ключа API.")
    st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 6. ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# ЛОГИКА ВХОДА
# ==========================================
if not st.session_state.user:
    st.title("🇰🇿 IELTS Coach Arman")
    
    tab1, tab2 = st.tabs(["🔐 Войти", "📝 Регистрация"])
    
    with tab1:
        with st.form("login"):
            ph = st.text_input("Ваш ID (Телефон):")
            pw = st.text_input("Пароль:", type="password")
            if st.form_submit_button("Войти"):
                ud = load_user(ph)
                if ud and str(ud["password"]).strip() == str(pw).strip():
                    st.session_state.user = ud
                    st.session_state.messages = ud["history"]
                    st.rerun()
                else:
                    st.error("Ошибка входа")
        if st.expander("Забыли пароль?"):
            st.markdown(f"Пишите сюда: **[Telegram]({ADMIN_CONTACT})**")

    with tab2:
        with st.form("reg"):
            n_ph = st.text_input("Телефон (ID):")
            n_pw = st.text_input("Пароль:", type="password")
            n_nm = st.text_input("Имя:")
            n_lv = st.select_slider("Уровень:", ["Beginner (A1-A2)", "Intermediate (B1-B2)", "Advanced (C1-C2)"])
            n_tg = st.selectbox("Цель:", ["Band 5.5", "Band 6.0", "Band 6.5", "Band 7.0", "Band 7.5+"])
            
            if st.form_submit_button("Создать аккаунт"):
                if n_ph and n_pw and n_nm:
                    res = register_user(n_ph, n_nm, n_lv, n_tg, n_pw)
                    if res == "EXISTS": st.error("Такой пользователь уже есть.")
                    elif res:
                        st.session_state.user = res
                        st.session_state.messages = []
                        st.rerun()
                else:
                    st.warning("Заполните поля")

# ==========================================
# ЛОГИКА ЧАТА (PREMIUM MENTOR PROMPT)
# ==========================================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.header(user['name'])
        st.write(f"Level: {user['level']}")
        st.write(f"Goal: {user['target']}")
        if st.button("Выйти"):
            st.session_state.user = None
