import streamlit as st
from openai import OpenAI
import gspread
import json
import time

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="IELTS Coach Arman", page_icon="🇰🇿", layout="centered")

# --- 2. КОНТАКТЫ АДМИНА ---
ADMIN_CONTACT = "https://t.me/aligassan_m" 

# --- 3. ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ (С КЭШИРОВАНИЕМ ⚡️) ---
# @st.cache_resource гарантирует, что мы подключаемся к Google ТОЛЬКО ОДИН РАЗ
# Это ускоряет работу сайта в разы.
@st.cache_resource(ttl=600) # Переподключаться каждые 10 минут на всякий случай
def get_db_connection():
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in credentials_dict:
            credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
        gc = gspread.service_account_from_dict(credentials_dict)
        sh = gc.open("IELTS_Users_DB")
        return sh.sheet1
    except Exception as e:
        st.error(f"Ошибка соединения с БД: {e}")
        return None

worksheet = get_db_connection()

# --- 4. ФУНКЦИИ (ОПТИМИЗИРОВАНЫ) ---
def load_user(phone):
    if not worksheet: return None
    try:
        # Используем find, но обрабатываем ошибки мягче
        cell = worksheet.find(phone)
        if cell:
            row = worksheet.row_values(cell.row)
            # Защита от "битых" строк
            history_data = row[4] if len(row) > 4 else "[]"
            password_data = row[5] if len(row) > 5 else "" 
            
            # Пробуем распарсить JSON, если ошибка — возвращаем пустую историю
            try:
                history = json.loads(history_data)
            except:
                history = []

            return {
                "row_id": cell.row,
                "name": row[1],
                "level": row[2],
                "target": row[3],
                "history": history,
                "password": str(password_data)
            }
    except Exception as e:
        # Логируем ошибку в консоль разработчика, не пугая юзера
        print(f"Error loading user: {e}")
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
    try:
        history_str = json.dumps(messages, ensure_ascii=False)
        worksheet.update_cell(row_id, 5, history_str)
    except Exception as e:
        st.warning("Не удалось сохранить историю (проблема сети). Но чат продолжается.")

# --- 5. ГЕНЕРАТОР ПРОМПТА (ВЫНЕСЕН ОТДЕЛЬНО) ---
def get_system_prompt(user):
    return f"""
    # 1. ROLE & IDENTITY
    Ты — Арман. Премиальный, теплый, профессиональный и адаптивный IELTS-наставник.
    
    ТВОЙ СТУДЕНТ:
    - Имя: {user['name']}
    - Уровень: {user['level']}
    - Цель: {user['target']}

    # 2. CORE PRINCIPLES
    - Ты не даёшь готовые ответы.
    - Ты обучаешь через метод Сократа.
    - Ты всегда привязываешь фидбек к 4 критериям IELTS.

    # 3. COMMUNICATION STYLE
    - Обращайся по имени: {user['name']}.
    - Тёплый, но профессиональный тон.

    # 4. LANGUAGE ADAPTATION
    - Если Beginner/Intermediate: Используй русский/казахский для объяснения.
    - Если Advanced: Почти полностью английский.

    # 5. ONBOARDING
    - Первое сообщение: Тёплое вступление -> План или практика.

    # 6. TEACHING ALGORITHM
    - Training Mode: 1 вопрос → ответ → фидбек → СЛЕДУЮЩИЙ ВОПРОС.
    - НЕ ДАВАТЬ готовую версию ответа сразу.

    # 7. GUARDRAILS
    - НЕТ: политика, религия, математика, физика.
    - ОТКАЗ: "Мен IELTS мұғалімімін. Есеп шығармаймын. Ағылшынға оралайық! 🇰🇿"

    # 12. ENDLESS FLOW (БЕСКОНЕЧНЫЙ ПОТОК)
    - НИКОГДА не прощайся.
    - Формула: [Реакция] -> [Фидбек] -> [НОВЫЙ ВОПРОС].
    - Останавливайся только по команде "Stop".
    """

# --- 6. OPENAI ---
if "OPENAI_API_KEY" not in st.secrets:
    st.error("Нет ключа API.")
    st.stop()
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- 7. ИНИЦИАЛИЗАЦИЯ ---
if "user" not in st.session_state:
    st.session_state.user = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# ЭКРАН 1: ВХОД И РЕГИСТРАЦИЯ
# ==========================================
if not st.session_state.user:
    st.title("🇰🇿 IELTS Coach Arman")
    
    tab1, tab2 = st.tabs(["🔐 Войти", "📝 Регистрация"])
    
    with tab1:
        with st.form("login"):
            ph = st.text_input("Ваш ID (Телефон):")
            pw = st.text_input("Пароль:", type="password")
            if st.form_submit_button("Войти"):
                with st.spinner("Проверяем данные..."): # Визуальный эффект загрузки
                    ud = load_user(ph)
                    if ud and str(ud["password"]).strip() == str(pw).strip():
                        st.session_state.user = ud
                        st.session_state.messages = ud["history"]
                        st.rerun()
                    else:
                        st.error("Ошибка входа (проверьте ID или пароль)")
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
                with st.spinner("Создаем профиль..."):
                    if n_ph and n_pw and n_nm:
                        res = register_user(n_ph, n_nm, n_lv, n_tg, n_pw)
                        if res == "EXISTS": st.error("Такой пользователь уже есть.")
                        elif res:
                            st.session_state.user = res
                            st.session_state.messages = []
                            st.rerun()
                    else:
                        st.warning("Заполните все поля")

# ==========================================
# ЭКРАН 2: ЧАТ С АРМАНОМ (С УЛУЧШЕНИЯМИ)
# ==========================================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/d/d3/Flag_of_Kazakhstan.svg", width=50) # Флаг как лого
        st.header(user['name'])
        st.caption(f"Level: {user['level']} | Goal: {user['target']}")
        
        st.divider()
        
        # --- НОВАЯ ФИЧА: ВЫБОР ТЕМЫ ---
        topic = st.selectbox(
            "📚 Выбери тему урока:",
            ["General Chat", "Work & Studies", "Hometown", "Hobbies", "Travel", "Technology", "Environment"]
        )
        
        # Если тема изменилась, можно отправить системное сообщение (опционально)
        if "current_topic" not in st.session_state:
            st.session_state.current_topic = "General Chat"
        
        if topic != st.session_state.current_topic:
            st.session_state.current_topic = topic
            # Мягко просим Армана сменить тему
            st.session_state.messages.append({"role": "system", "content": f"User changed topic to: {topic}. Start asking questions about {topic} immediately."})
            st.rerun()

        st.divider()
        if st.button("🧹 Очистить чат"):
            st.session_state.messages = []
            st.rerun()
        if st.button("🚪 Выйти"):
            st.session_state.user = None
            st.session_state.messages = []
            st.rerun()

    st.title(f"Arman | IELTS Coach 🇰🇿")
    st.caption(f"Текущая тема: **{topic}**")

    # --- ЗАГРУЗКА МОЗГА ---
    if not st.session_state.messages:
        sys_prompt = get_system_prompt(user)
        st.session_state.messages.append({"role": "system", "content": sys_prompt})
        welcome = f"Salem, {user['name']}! Арман на связи. 🇰🇿\n\nМы выбрали тему: **{topic}**. Готов начать?"
        st.session_state.messages.append({"role": "assistant", "content": welcome})
        save_history(user["row_id"], st.session_state.messages)

    # --- ВЫВОД СООБЩЕНИЙ С АВАТАРКАМИ ---
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            # Выбираем иконку
            if msg["role"] == "user":
                avatar_icon = "👤" # Или ссылка на картинку
            else:
                avatar_icon = "👨‍🏫" # Или ссылка на фото Армана
            
            with st.chat_message(msg["role"], avatar=avatar_icon):
                st.markdown(msg["content"])

    # --- ВВОД ---
    if prompt := st.chat_input("Твой ответ..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="👨‍🏫"):
            message_placeholder = st.empty()
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True,
                temperature=0.7
            )
            response = st.write_stream(stream)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_history(user["row_id"], st.session_state.messages)
