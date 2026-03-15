import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from gigachat import GigaChat
import uuid

load_dotenv()

app = Flask(__name__)

# Ключ из переменных окружения
GIGACHAT_CREDENTIALS = os.getenv('GIGACHAT_API_KEY')

# Системные промпты для разных режимов
SYSTEM_PROMPTS = {
    'tutor': "Ты — Знайка, добрый репетитор. Объясняй просто, задавай наводящие вопросы, хвали за правильные мысли. Никогда не давай готовый ответ сразу, а подводи к решению.",
    'essay': "Ты — Знайка, помогаешь с сочинениями. Помогай с идеями, проверяй ошибки, но не пиши полностью за ученика.",
    'solver': "Ты — Знайка, решаешь задачи по шагам. Разбивай решение на понятные шаги, объясняй каждый шаг.",
    'translate': "Ты — Знайка, переводчик. Переводи текст, сохраняя смысл и стиль оригинала.",
    'summary': "Ты — Знайка, делаешь краткое содержание. Выделяй главное, пиши понятно, сохраняй ключевые идеи.",
    'ideas': "Ты — Знайка, генератор идей. Помогай придумывать, задавай уточняющие вопросы, предлагай варианты."
}

# Хранилище истории (в памяти)
conversation_history = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    mode = data.get('mode', 'tutor')
    session_id = data.get('session_id', 'default')
    
    if not user_message:
        return jsonify({'error': 'Пустое сообщение'}), 400
    
    try:
        # Создаем клиента GigaChat с отключенной проверкой SSL (для Render)
        # verify_ssl_certs=False решает проблему с сертификатами Минцифры [citation:1][citation:2]
        with GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            verify_ssl_certs=False,  # Это наш спаситель!
            timeout=30
        ) as giga:
            
            # Собираем сообщения с системным промптом
            messages = []
            messages.append({"role": "system", "content": SYSTEM_PROMPTS[mode]})
            
            # Добавляем историю (последние 5 сообщений)
            if session_id in conversation_history:
                for msg in conversation_history[session_id][-5:]:
                    messages.append({"role": "user", "content": msg['user']})
                    messages.append({"role": "assistant", "content": msg['bot']})
            
            # Добавляем текущее сообщение
            messages.append({"role": "user", "content": user_message})
            
            # Отправляем запрос
            response = giga.chat(messages)
            
            # Получаем ответ
            bot_response = response.choices[0].message.content
            
            # Сохраняем в историю
            if session_id not in conversation_history:
                conversation_history[session_id] = []
            conversation_history[session_id].append({
                'user': user_message,
                'bot': bot_response,
                'mode': mode
            })
            
            return jsonify({'response': bot_response})
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({'error': f'Ошибка связи с GigaChat: {str(e)}'}), 500

@app.route('/history', methods=['GET'])
def get_history():
    session_id = request.args.get('session_id', 'default')
    if session_id in conversation_history:
        return jsonify(conversation_history[session_id])
    return jsonify([])

@app.route('/clear', methods=['POST'])
def clear_history():
    session_id = request.json.get('session_id', 'default')
    if session_id in conversation_history:
        conversation_history[session_id] = []
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
