import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import json
from datetime import datetime

# Загружаем переменные окружения из .env файла
load_dotenv()

app = Flask(__name__)

# Настройки GigaChat
GIGACHAT_API_KEY = os.getenv('GIGACHAT_API_KEY')
GIGACHAT_URL = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'

# Системные промпты для всех режимов
SYSTEM_PROMPTS = {
    'tutor': """Ты — Знайка, добрый и терпеливый репетитор для школьников 1-9 классов.
Объясняй просто, задавай наводящие вопросы, хвали за правильные мысли.
Никогда не давай готовый ответ сразу, а подводи к решению.
Если ученик ошибся — мягко поправь и объясни почему.
Используй примеры из жизни, будь дружелюбным, используй эмодзи.
Разбивай сложные темы на простые шаги.""" ,

    'essay': """Ты — Знайка, помогаешь с сочинениями.
Помогай с идеями, проверяй ошибки, но не пиши полностью за ученика.
Объясняй, как улучшить текст, задавай наводящие вопросы.
Показывай структуру: вступление, основная часть, заключение.
Хвали за хорошие мысли и исправляй ошибки мягко.""" ,

    'solver': """Ты — Знайка, решаешь задачи по шагам.
Разбивай решение на понятные шаги, объясняй каждый шаг.
Спрашивай, понятно ли объяснение. Если задача сложная — упрощай.
Показывай формулы, если нужно, и объясняй, откуда они берутся.
Не давай готовый ответ сразу — подводи к нему.""" ,

    'translate': """Ты — Знайка, переводчик.
Переводи текст, сохраняя смысл и стиль оригинала.
Если есть идиомы или устойчивые выражения — объясняй их.
Давай несколько вариантов перевода, если это уместно.
Спрашивай, нужны ли пояснения по переводу.""" ,

    'summary': """Ты — Знайка, делаешь краткое содержание.
Выделяй главное, пиши понятно, сохраняй ключевые идеи.
Структурируй краткое содержание: главные герои (если есть), основные события, главная мысль.
Указывай, для какого возраста подходит текст.""" ,

    'ideas': """Ты — Знайка, генератор идей.
Помогай придумывать, задавай уточняющие вопросы, предлагай варианты.
Давай разные направления для размышления.
Спрашивай, что именно интересует, чтобы уточнить идею.
Предлагай нестандартные подходы и решения."""
}

# История диалогов (в памяти, потом можно добавить БД)
conversation_history = []

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
    
    # Формируем запрос к GigaChat
    headers = {
        'Authorization': f'Bearer {GIGACHAT_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Собираем сообщения для отправки
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPTS[mode]}
    ]
    
    # Добавляем последние 5 сообщений из истории для контекста
    if session_id in conversation_history:
        recent = conversation_history[session_id][-5:]
        for msg in recent:
            messages.append({'role': 'user', 'content': msg['user']})
            messages.append({'role': 'assistant', 'content': msg['bot']})
    
    # Добавляем текущее сообщение
    messages.append({'role': 'user', 'content': user_message})
    
    payload = {
        'model': 'GigaChat',
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': 1500,
        'top_p': 0.9,
        'frequency_penalty': 0.3,
        'presence_penalty': 0.3
    }
    
    try:
        # Отправляем запрос к GigaChat
        response = requests.post(
            GIGACHAT_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        bot_response = result['choices'][0]['message']['content']
        
        # Сохраняем в историю
        if session_id not in conversation_history:
            conversation_history[session_id] = []
        conversation_history[session_id].append({
            'user': user_message,
            'bot': bot_response,
            'mode': mode,
            'timestamp': datetime.now().isoformat()
        })
        
        # Ограничиваем историю до 50 сообщений на сессию
        if len(conversation_history[session_id]) > 50:
            conversation_history[session_id] = conversation_history[session_id][-50:]
        
        return jsonify({
            'response': bot_response,
            'mode': mode
        })
        
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Сервер долго не отвечает. Попробуй еще раз.'}), 504
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к GigaChat: {e}")
        return jsonify({'error': 'Ошибка связи с GigaChat'}), 500
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")
        return jsonify({'error': 'Что-то пошло не так'}), 500

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
    app.run(host='0.0.0.0', port=port, debug=True)
