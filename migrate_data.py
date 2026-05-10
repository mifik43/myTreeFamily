# migrate_data.py
import os
from app import create_app
from models import db, Person
from sqlalchemy import text

app = create_app()

def migrate():
    with app.app_context():
        inspector = db.inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('person')]

        # Перенос city -> birth_city
        if 'city' in columns and 'birth_city' in columns:
            db.session.execute(
                text("UPDATE person SET birth_city = city WHERE birth_city IS NULL AND city IS NOT NULL")
            )
            db.session.commit()
            print("city -> birth_city перенесено")

        # Перенос birth_date -> birth_year/month/day
        if 'birth_date' in columns and 'birth_year' in columns:
            db.session.execute(
                text("""
                    UPDATE person
                    SET birth_year = CAST(strftime('%Y', birth_date) AS INTEGER),
                        birth_month = CAST(strftime('%m', birth_date) AS INTEGER),
                        birth_day = CAST(strftime('%d', birth_date) AS INTEGER)
                    WHERE birth_date IS NOT NULL AND birth_year IS NULL
                """)
            )
            db.session.commit()
            print("birth_date разложено")

        # Перенос death_date -> death_year/month/day
        if 'death_date' in columns and 'death_year' in columns:
            db.session.execute(
                text("""
                    UPDATE person
                    SET death_year = CAST(strftime('%Y', death_date) AS INTEGER),
                        death_month = CAST(strftime('%m', death_date) AS INTEGER),
                        death_day = CAST(strftime('%d', death_date) AS INTEGER)
                    WHERE death_date IS NOT NULL AND death_year IS NULL
                """)
            )
            db.session.commit()
            print("death_date разложено")

        print("Миграция данных завершена.")

if __name__ == '__main__':
    migrate()