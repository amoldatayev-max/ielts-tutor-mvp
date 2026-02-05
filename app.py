import streamlit as st
from openai import OpenAI
import gspread
import json

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Coach Alex", page_icon="🇬🇧", layout="centered")

# --- КОНТАКТ ДЛЯ СБРОСА ПАРОЛЯ ---
# Теперь здесь ваша прямая ссылка
ADMIN_CONTACT = "https://t.me/aligassan_zest" 

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ---
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

# --- ФУНКЦИИ БД ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            # Структура: Phone, Name, Level, Target, History, Password
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
        if worksheet.find(phone):
            return "EXISTS"
        worksheet.append_row([phone, name, level, target, "[]", password])
        return load_user(phone)
    except:
        return None

def save_history(row_id, messages):
    if not worksheet: return
    history_str = json.dumps(messages, ensure_ascii=False)
    worksheet.update_cell(row_id, 5, history_str)

# --- ПРОВЕРКА OPENAI ---
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Нет ключа OpenAI.")
    st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# ЭКРАН 1: ВХОД / РЕГИСТРАЦИЯ
# ==========================================
if not st.session_state.user:
    st.title("🇬🇧 IELTS Coach Alex")
    
    tab1, tab2 = st.tabs(["🔐 Войти", "📝 Регистрация"])
    
    # --- ВХОД ---
    with tab1:
        with st.form("login_form"):
            phone_login = st.text_input("Ваш ID (Телефон):")
            pass_login = st.text_input("Пароль:", type="password")
            
            if st.form_submit_button("Войти"):
                if phone_login and pass_login:
                    user_data = load_user(phone_login)
                    if user_data:
                        if str(user_data["password"]).strip() == str(pass_login).strip():
                            st.session_state.user = user_data
                            st.session_state.messages = user_data["history"]
                            st.success(f"Welcome back, {user_data['name']}!")
                            st.rerun()
                        else:
                            st.error("Неверный пароль!")
                    else:
                        st.error("Пользователь не найден.")
                else:
                    st.warning("Введите ID и пароль.")

        st.divider()
        # Кликабельная ссылка для сброса
        if st.expander("Забыли пароль?"):
            st.markdown(f"Напишите администратору для восстановления доступа: **[Написать в Telegram]({ADMIN_CONTACT})**")

    # --- РЕГИСТРАЦИЯ ---
    with tab2:
        with st.form("reg_form"):
            new_phone = st.text_input("Придумай ID (Телефон):", help="Это будет твой логин")
            new_pass = st.text_input("Придумай пароль:", type="password")
            new_name = st.text_input("Имя:")
            new_level = st.select_slider("Уровень:", ["Beginner", "Intermediate", "Advanced"])
            new_target = st.selectbox("Цель:", ["Band 6.0", "Band 7.0", "Band 8.0+"])
            
            if st.form_submit_button("Создать аккаунт"):
                if new_phone and new_pass and new_name:
                    result = register_user(new_phone, new_name, new_level, new_target, new_pass)
                    if result == "EXISTS":
                        st.error("Такой пользователь уже есть. Попробуй войти.")
                    elif result:
                        st.session_state.user = result
                        st.session_state.messages = []
                        st.rerun()
                    else:
                        st.error("Ошибка регистрации.")
                else:
                    st.warning("Заполни все поля!")

# ==========================================
# ЭКРАН 2: ЧАТ
# ==========================================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.write(f"Студент: **{user['name']}**")
        if st.button("Выйти"):
            st.session_state.user = None
            st.session_state.messages = []
            st.rerun()

    st.title(f"Chat with Alex ({user['target']})")

    if not st.session_state.messages:
        sys_prompt = f"Role: IELTS Coach Alex. Student: {user['name']} ({user['level']}). Goal: {user['target']}. Style: Friendly WhatsApp chat, short answers."
        st.session_state.messages.append({"role": "system", "content": sys_prompt})
        st.session_state.messages.append({"role": "assistant", "content": f"Hi {user['name']}! Alex here. Let's crash IELTS! What are we practicing?"})
        save_history(user["row_id"], st.session_state.messages)

    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("Message Alex..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
                temperature=0.7
            )
            response = st.write_stream(stream)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_history(user["row_id"], st.session_state.messages)
