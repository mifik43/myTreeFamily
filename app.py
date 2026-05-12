from flask import Flask
from config import Config
from models import db
from flask_login import LoginManager
from flask_migrate import Migrate
from helpers import get_active_tree 
import socket

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    migrate = Migrate(app, db)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    # Регистрируем функцию как глобальную для всех шаблонов#
    #app.jinja_env.globals['get_active_tree'] = get_active_tree

    # ... регистрация blueprint'ов ...
    from auth import auth_bp
    from main import main_bp
    from person_routes import person_bp
    from relationship_routes import rel_bp
    from confirm_routes import confirm_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(person_bp)
    app.register_blueprint(rel_bp)
    app.register_blueprint(confirm_bp)

    with app.app_context():
        db.create_all()

    return app

def get_local_ip():
    """Получает локальный IP-адрес для доступа по сети"""
    try:
        # Создаем временное соединение чтобы определить IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        return ip
    except:
        return "не удалось определить"
    
if __name__ == '__main__':
    app = create_app()
    local_ip = get_local_ip()
    app.run(
        host='0.0.0.0',  # Доступ со всех интерфейсов
        port=5500,       # Порт (можно изменить при необходимости)            
        threaded=True    # Для обработки нескольких запросов одновременно
    )