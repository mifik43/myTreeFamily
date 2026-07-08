import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL',
                                             'sqlite:///' + os.path.join(basedir, 'genealogy.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 20)),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 40)),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
        'pool_pre_ping': os.environ.get('DB_POOL_PRE_PING', 'true').lower() == 'true',
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 30)),
    }
    YANDEX_MAPS_API_KEY = os.environ.get('YANDEX_MAPS_API_KEY', '6f24891b-8fe6-434c-b672-42748f62a380')