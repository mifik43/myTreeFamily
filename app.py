from flask import Flask
from config import Config
from models import db
from flask_login import LoginManager
from flask_migrate import Migrate
from helpers import get_active_tree, get_active_persons
from datetime import datetime, timedelta

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

    # Регистрируем глобальную функцию для шаблонов
    app.jinja_env.globals['get_active_tree'] = get_active_tree

    # Регистрация Blueprint'ов
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

    # Команда CLI для очистки корзины
    @app.cli.command('clean-trash')
    def clean_trash():
        """Удаляет персоны, которые находятся в корзине больше 30 дней."""
        from models import Person, Marriage
        with app.app_context():
            cutoff = datetime.utcnow() - timedelta(days=30)
            old_deleted = Person.query.filter(
                Person.deleted_at != None,
                Person.deleted_at <= cutoff
            ).all()
            for p in old_deleted:
                Marriage.query.filter(
                    (Marriage.husband_id == p.id) | (Marriage.wife_id == p.id)
                ).delete()
                Person.query.filter_by(father_id=p.id).update({Person.father_id: None})
                Person.query.filter_by(mother_id=p.id).update({Person.mother_id: None})
                db.session.delete(p)
            db.session.commit()
            print(f'Окончательно удалено {len(old_deleted)} записей.')

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