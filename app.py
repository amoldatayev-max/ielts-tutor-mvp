import streamlit as st
from openai import OpenAI

# Настройка страницы
st.set_page_config(page_title="IELTS AI Tutor", page_icon="🎓")

st.title("🎓 Личный IELTS Репетитор")
st.markdown("""
Я помогу тебе подготовиться к Writing и Speaking. 
* **Напиши эссе**, и я проверю его по критериям.
* **Задай вопрос**, и я объясню правило.
""")

# Проверка наличия ключа
if "OPENAI_API_KEY" not in st.secrets:
    st.info("Пожалуйста, настройте API Key в Streamlit (Settings -> Secrets), чтобы начать урок.")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Системная инструкция (Мозги учителя)
system_prompt = """
Ты — профессиональный экзаменатор IELTS с 15-летним стажем. Твоя цель — поднять балл студента.
Твой стиль: Строгий, академический, но поддерживающий.

ПРАВИЛА:
1. Если студент присылает текст (эссе/письмо):
   - Оцени примерный Band Score (например, 6.0).
   - Разбери ошибки по 4 критериям: Task Achievement, Coherence & Cohesion, Lexical Resource, Grammatical Range.
   - Дай 3 конкретных совета, как улучшить текст до более высокого балла.
   
2. Если студент задает вопрос:
   - Не давай ответ сразу. Используй наводящие вопросы (Scaffolding), как Сократ.
   - Пример: Вместо прямого перевода, дай синонимы уровня C1 или контекст.

3. Форматирование: Используй жирный шрифт для терминов и списки.
"""

# Инициализация истории чата
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

# Отображение истории (кроме системного сообщения)
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Поле ввода
if prompt := st.chat_input("Вставь эссе или задай вопрос..."):
    # 1. Добавляем вопрос пользователя
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Генерируем ответ
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
    
    # 3. Сохраняем ответ в историю
    st.session_state.messages.append({"role": "assistant", "content": response})
