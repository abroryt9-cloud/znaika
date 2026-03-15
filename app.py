import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime, timedelta
from functools import wraps
import uuid

# Загружаем переменные окружения
load_dotenv()

# Импортируем модели
from models import db, User, Chat, Message

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'znaika-super-secret-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///znaika.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите чтобы продолжить'

# Настройки GigaChat (для будущего подключения)
GIGACHAT_CREDENTIALS = os.getenv('GIGACHAT_API_KEY')

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('У вас нет доступа к этой странице', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# Создание таблиц и тестового админа
@app.before_first_request
def create_tables():
    db.create_all()
    # Создаем тестового админа, если нет пользователей
    if User.query.count() == 0:
        admin_user = User(
            username='admin',
            email='admin@znaika.ru',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        db.session.commit()

# ==================== ОСНОВНЫЕ СТРАНИЦЫ ====================

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Личный кабинет пользователя"""
    return render_template('dashboard.html', user=current_user)

# ==================== АВТОРИЗАЦИЯ ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        # Проверки
        if not username or not email or not password:
            flash('Все поля обязательны для заполнения', 'danger')
            return redirect(url_for('register'))
        
        if password != confirm:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('register'))
        
        # Проверка существования пользователя
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return redirect(url_for('register'))
        
        # Создаем нового пользователя
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Регистрация прошла успешно! Теперь можно войти', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход в систему"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            flash('Неверное имя пользователя или пароль', 'danger')
            return redirect(url_for('login'))
        
        # Обновляем время последнего входа
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        login_user(user, remember=remember)
        
        # Перенаправляем в зависимости от роли
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))

# ==================== АДМИН-ПАНЕЛЬ ====================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Главная админ-панель со статистикой"""
    # Общая статистика
    total_users = User.query.count()
    total_chats = Chat.query.count()
    total_messages = Message.query.count()
    
    # Новые пользователи за сегодня
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_today = User.query.filter(User.created_at >= today_start).count()
    
    # Новые пользователи за неделю
    week_start = today_start - timedelta(days=7)
    new_users_week = User.query.filter(User.created_at >= week_start).count()
    
    # Активные пользователи (заходили сегодня)
    active_today = User.query.filter(User.last_login >= today_start).count()
    
    # Статистика по ролям
    admins_count = User.query.filter_by(role='admin').count()
    regular_users = total_users - admins_count
    
    # Последние зарегистрированные пользователи
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
        total_users=total_users,
        total_chats=total_chats,
        total_messages=total_messages,
        new_users_today=new_users_today,
        new_users_week=new_users_week,
        active_today=active_today,
        admins_count=admins_count,
        regular_users=regular_users,
        recent_users=recent_users
    )

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Список всех пользователей"""
    # Параметры фильтрации
    role_filter = request.args.get('role', 'all')
    search = request.args.get('search', '')
    
    query = User.query
    
    if role_filter != 'all':
        query = query.filter_by(role=role_filter)
    
    if search:
        query = query.filter(
            (User.username.contains(search)) | 
            (User.email.contains(search))
        )
    
    users = query.order_by(User.created_at.desc()).all()
    
    return render_template('admin/users.html', 
        users=users, 
        role_filter=role_filter,
        search=search
    )

@app.route('/admin/user/<user_id>')
@login_required
@admin_required
def admin_user_detail(user_id):
    """Детальная информация о пользователе"""
    user = User.query.get(user_id)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin_users'))
    
    chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.created_at.desc()).all()
    
    return render_template('admin/user_detail.html', user=user, chats=chats)

@app.route('/admin/user/<user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Удаление пользователя"""
    user = User.query.get(user_id)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin_users'))
    
    # Нельзя удалить самого себя
    if user.id == current_user.id:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('admin_users'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь {user.username} удален', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def admin_toggle_admin(user_id):
    """Смена роли пользователя"""
    user = User.query.get(user_id)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin_users'))
    
    # Нельзя изменить роль самого себя
    if user.id == current_user.id:
        flash('Нельзя изменить свою собственную роль', 'danger')
        return redirect(url_for('admin_users'))
    
    user.role = 'user' if user.role == 'admin' else 'admin'
    db.session.commit()
    flash(f'Роль пользователя {user.username} изменена на {user.role}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/stats')
@login_required
@admin_required
def admin_stats():
    """Детальная статистика"""
    # Статистика по дням за последние 30 дней
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Получаем всех пользователей
    users = User.query.filter(User.created_at >= start_date).all()
    
    # Группировка по дням
    daily_stats = {}
    for i in range(31):
        day = (start_date + timedelta(days=i)).date()
        daily_stats[day] = {'new_users': 0, 'active_users': 0}
    
    # Считаем новых пользователей по дням
    for user in users:
        day = user.created_at.date()
        if day in daily_stats:
            daily_stats[day]['new_users'] += 1
    
    # Считаем активных пользователей по дням
    active_users = User.query.filter(User.last_login >= start_date).all()
    for user in active_users:
        if user.last_login:
            day = user.last_login.date()
            if day in daily_stats:
                daily_stats[day]['active_users'] += 1
    
    return render_template('admin/stats.html', daily_stats=daily_stats)

# ==================== API ДЛЯ ЧАТА ====================

@app.route('/api/chats', methods=['GET'])
@login_required
def get_chats():
    """Получение списка чатов пользователя"""
    chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.updated_at.desc()).all()
    return jsonify([chat.to_dict() for chat in chats])

@app.route('/api/chats', methods=['POST'])
@login_required
def create_chat():
    """Создание нового чата"""
    data = request.json
    chat = Chat(
        user_id=current_user.id,
        title=data.get('title', 'Новый чат'),
        mode=data.get('mode', 'tutor')
    )
    db.session.add(chat)
    db.session.commit()
    return jsonify(chat.to_dict())

@app.route('/api/chats/<chat_id>/messages', methods=['GET'])
@login_required
def get_messages(chat_id):
    """Получение сообщений чата"""
    chat = Chat.query.get(chat_id)
    if not chat or chat.user_id != current_user.id:
        return jsonify({'error': 'Чат не найден'}), 404
    
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.created_at).all()
    return jsonify([{
        'id': msg.id,
        'role': msg.role,
        'content': msg.content,
        'created_at': msg.created_at.isoformat()
    } for msg in messages])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
