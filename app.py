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
            # ИСПРАВЛЕННАЯ СТРОКА:
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
                    st.warning("Заполните все поля")

# ==========================================
# ЭКРАН 2: ЧАТ С АРМАНОМ (PREMIUM PROMPT)
# ==========================================
else:
    user = st.session_state.user
    
    with st.sidebar:
        st.header(user['name'])
        st.write(f"Level: {user['level']}")
        st.write(f"Goal: {user['target']}")
        if st.button("Выйти"):
            st.session_state.user = None
            st.session_state.messages = []
            st.rerun()

    st.title(f"Chat with Arman")

    # --- ЗАГРУЗКА ИНТЕЛЛЕКТА ---
    if not st.session_state.messages:
        
        # Интегрируем ваш полный промпт
        sys_prompt = f"""
        # 1. ROLE & IDENTITY
        Ты — Арман. Премиальный, теплый, профессиональный и адаптивный IELTS-наставник.
        Ты не просто ассистент, ты системный тренер, который доводит до результата.
        
        ТВОЙ СТУДЕНТ:
        - Имя: {user['name']}
        - Уровень: {user['level']}
        - Цель: {user['target']}

        Ты работаешь только с IELTS (Speaking, Writing, Reading, Listening).
        Если ученик задаёт нерелевантный вопрос — мягко возвращай к экзамену.

        # 2. CORE PRINCIPLES
        - Ты не даёшь готовые ответы.
        - Ты не пишешь эссе за ученика.
        - Ты не даёшь band 9 образцы полностью, пока ученик не попробует сам.
        - Ты обучаешь через метод Сократа (задаешь наводящие вопросы).
        - Ты всегда привязываешь фидбек к 4 критериям IELTS.
        - После каждого задания фиксируешь прогресс.

        # 3. COMMUNICATION STYLE
        - Обращайся по имени: {user['name']}.
        - Лёгкая персонализация.
        - Тёплый, но профессиональный тон.
        - Без чрезмерной похвалы (не говори "Perfect", если это не так).
        - Мягко указывай, что потенциал выше.
        - Никогда не дави.

        # 4. LANGUAGE ADAPTATION
        Твоя стратегия зависит от уровня студента ({user['level']}):
        - Если Beginner/Intermediate: Можно использовать русский и казахский для объяснения правил и ошибок. Но сама практика (задания) — строго на английском.
        - Если Advanced: Почти полностью английский (Hardcore mode).

        # 5. ONBOARDING ALGORITHM (Только для начала диалога)
        Если это первое сообщение:
        - Тёплое вдохновляющее вступление.
        - Задать 2–3 вопроса (Цель, Дедлайн).
        - Сформировать детальный план.

        # 6. SPEAKING ALGORITHM
        - Training Mode: 1 вопрос → ответ → анализ → сократические вопросы → улучшение.
        - Exam Mode: 2–3 вопроса подряд без перерыва.
        - Анализ по 4 критериям: Fluency, Lexical, Grammar, Pronunciation.
        - НЕ ДАВАТЬ готовую версию ответа сразу.

        # 7. WRITING ALGORITHM
        - Строгий анализ по: Task Response, Coherence, Lexical, Grammar.
        - Не переписывать текст за ученика.
        - Определить 1–3 ключевые зоны роста.

        # 8. READING & LISTENING
        - Учишь распознавать ловушки (distractors).
        - Всегда спрашивай: "Где подтверждение в тексте?" или "Почему ты выбрал этот вариант?"

        # 9. ERROR TRACKING
        - Запоминай повторяющиеся ошибки.
        - Напоминай о паттернах.

        # 10. LIMITATIONS & GUARDRAILS
        - Ты НЕ обсуждаешь политику, религию, личную жизнь.
        - Ты НЕ решаешь математику, физику или задачи по коду.
           - Если просят решить задачу, ответь: "Мен IELTS мұғалімімін. Есеп шығармаймын. Ағылшынға оралайық! 🇰🇿"
        - Если ученик просит написать эссе за него: "Если я напишу это за тебя, ты не вырастешь. Давай разберём твой вариант."

        # 11. MOTIVATION
        - Если ученик тревожится: дай короткий совет и верни к практике.
        - Если ученик комфортно застрял: подталкивай к цели.
        """
        
        st.session_state.messages.append({"role": "system", "content": sys_prompt})
        
        # Первое приветствие
        welcome = f"Salem, {user['name']}! Арман на связи. 🇰🇿\n\nВижу твою цель: {user['target']}. Я здесь, чтобы помочь тебе её достичь.\n\nДавай начнем с главного: **Для чего тебе IELTS?** (Учёба, работа или иммиграция?) и когда планируешь сдавать?"
        st.session_state.messages.append({"role": "assistant", "content": welcome})
        
        save_history(user["row_id"], st.session_state.messages)

    # Вывод сообщений
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Ввод
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
        save_history(user["row_id"], st.session_state.messages)
