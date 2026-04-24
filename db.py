# ----- Конфигурация PostgreSQL -----
DB_USER = os.environ.get('DB_USER', 'genealogy_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'strong_password')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'genealogy_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки пула соединений (важно для высокой нагрузки)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 20,           # базовый размер пула
    'max_overflow': 40,        # максимальное дополнительное количество
    'pool_recycle': 300,       # пересоздавать соединения каждые 5 минут
    'pool_pre_ping': True,     # проверять живучесть соединения перед использованием
    'pool_timeout': 30,        # сколько секунд ждать освобождения соединения
}