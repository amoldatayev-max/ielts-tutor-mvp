import streamlit as st
from openai import OpenAI
import gspread
import json

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Coach Alex", page_icon="🇬🇧", layout="centered")

# --- ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ---
def get_db_connection():
    try:
        # Читаем секреты, которые вы только что настроили
        credentials_dict = dict(st.secrets["gcp_service_account"])
        
        # Небольшой хак: восстанавливаем переносы строк в ключе, если они потерялись
        if "private_key" in credentials_dict:
            credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
        
        # Подключаемся
        gc = gspread.service_account_from_dict(credentials_dict)
        sh = gc.open("IELTS_Users_DB") # ВАЖНО: Ваша таблица должна называться именно так!
        return sh.sheet1
    except Exception as e:
        st.error(f"Ошибка соединения с таблицей: {e}")
        return None

worksheet = get_db_connection()

# --- ФУНКЦИИ: ЧТЕНИЕ И ЗАПИСЬ ---
def load_user(phone):
    if not worksheet: return None
    try:
        cell = worksheet.find(phone) # Ищем телефон
        if cell:
            row = worksheet.row_values(cell.row)
            # Если истории нет, создаем пустую
            history_data = row[4] if len(row) > 4 else "[]"
            return {
                "row_id": cell.row,
                "name": row[1],
                "level": row[2],
                "target": row[3],
                "history": json.loads(history_data)
            }
    except:
        return None
    return None

def register_user(phone, name, level, target):
    if not worksheet: return None
    # Добавляем строку: Phone, Name, Level, Target, History (пустая)
    worksheet.append_row([phone, name, level, target, "[]"])
    return load_user(phone)

def save_history(row_id, messages):
    if not worksheet: return
    # Превращаем переписку в текст и сохраняем в 5-ю колонку
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

# --- ЭКРАН 1: ВХОД / РЕГИСТРАЦИЯ ---
if not st.session_state.user:
    st.title("🇬🇧 IELTS Coach Alex")
    
    tab1, tab2 = st.tabs(["Войти", "Регистрация"])
    
    with tab1:
        phone_login = st.text_input("Введи свой ID (например, телефон):", key="login_phone")
        if st.button("Войти"):
            user = load_user(phone_login)
            if user:
                st.session_state.user = user
                st.session_state.messages = user["history"]
                st.success(f"Привет, {user['name']}!")
                st.rerun()
            else:
                st.error("Пользователь не найден. Сначала зарегистрируйся.")

    with tab2:
        with st.form("reg_form"):
            new_phone = st.text_input("Придумай ID (телефон):")
            new_name = st.text_input("Твое имя:")
            new_level = st.select_slider("Уровень:", ["Beginner", "Intermediate", "Advanced"])
            new_target = st.selectbox("Цель:", ["Band 6.0", "Band 7.0", "Band 8.0+"])
            
            if st.form_submit_button("Создать аккаунт"):
                if new_phone and new_name:
                    user = register_user(new_phone, new_name, new_level, new_target)
                    st.session_state.user = user
                    st.session_state.messages = []
                    st.rerun()
                else:
                    st.warning("Заполни все поля.")

# --- ЭКРАН 2: ЧАТ ---
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.write(f"Студент: **{user['name']}**")
        if st.button("Выйти"):
            st.session_state.user = None
            st.session_state.messages = []
            st.rerun()

    st.title(f"Chat with Alex ({user['target']})")

    # Первый запуск чата
    if not st.session_state.messages:
        sys_prompt = f"You are Alex, IELTS coach. Student: {user['name']} ({user['level']}). Style: Short, casual WhatsApp style. Goal: {user['target']}."
        st.session_state.messages.append({"role": "system", "content": sys_prompt})
        st.session_state.messages.append({"role": "assistant", "content": f"Hi {user['name']}! Ready to rock? What are we doing today?"})
        save_history(user["row_id"], st.session_state.messages)

    # Вывод истории
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Ввод сообщения
    if prompt := st.chat_input("Напиши ответ..."):
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
        # СОХРАНЯЕМ В ТАБЛИЦУ ПОСЛЕ КАЖДОГО СООБЩЕНИЯ
        save_history(user["row_id"], st.session_state.messages)
