"""
Скрипт миграции данных из старых полей birth_date / death_date (тип Date)
в новые поля birth_year, birth_month, birth_day, birth_notes
и аналогично для смерти.
После успешного переноса старые колонки можно удалить (см. инструкцию).
"""
import os
from app1 import app, db
from models import Person

def migrate():
    with app.app_context():
        # Добавляем новые колонки, если их ещё нет (сырой SQL)
        # Для SQLite синтаксис ADD COLUMN IF NOT EXISTS не поддерживается,
        # поэтому используем try/except или проверяем через inspector.
        # Лучше выполнить вручную или через Alembic.
        # Здесь мы просто проверим наличие колонок в модели: они уже определены в models.py?
        # Если запускаем после обновления models.py, колонки уже есть.
        # Но на всякий случай можно создать их "сырым" запросом, если они отсутствуют.
        engine = db.engine
        if engine.dialect.name == 'sqlite':
            # SQLite: ALTER TABLE ADD COLUMN (игнорируем ошибку, если уже есть)
            for col, col_type in [('birth_year', 'INTEGER'), ('birth_month', 'INTEGER'),
                                  ('birth_day', 'INTEGER'), ('birth_notes', 'VARCHAR(200)'),
                                  ('death_year', 'INTEGER'), ('death_month', 'INTEGER'),
                                  ('death_day', 'INTEGER'), ('death_notes', 'VARCHAR(200)')]:
                try:
                    db.session.execute(f'ALTER TABLE person ADD COLUMN {col} {col_type}')
                except Exception as e:
                    print(f'Column {col} probably exists: {e}')
            db.session.commit()
        else:
            # Для PostgreSQL можно использовать ALTER TABLE ... ADD COLUMN IF NOT EXISTS
            pass  # Оставим для Alembic

        persons = Person.query.all()
        updated = 0
        for p in persons:
            # Старые поля (они ещё присутствуют в модели? Если мы временно оставили birth_date, death_date)
            # Предполагаем, что в текущей ревизии кода они есть.
            if hasattr(p, 'birth_date') and p.birth_date:
                try:
                    p.birth_year = p.birth_date.year
                    p.birth_month = p.birth_date.month
                    p.birth_day = p.birth_date.day
                    updated += 1
                except AttributeError:
                    pass
            if hasattr(p, 'death_date') and p.death_date:
                try:
                    p.death_year = p.death_date.year
                    p.death_month = p.death_date.month
                    p.death_day = p.death_date.day
                except AttributeError:
                    pass
        db.session.commit()
        print(f'Перенесено записей (рождение): {updated}')

        # После успешного переноса старые колонки можно удалить вручную.
        # Если нужно, выполните SQL DROP COLUMN (только после полной проверки)
        # db.session.execute('ALTER TABLE person DROP COLUMN birth_date')
        # db.session.execute('ALTER TABLE person DROP COLUMN death_date')
        # db.session.commit()

if __name__ == '__main__':
    migrate()