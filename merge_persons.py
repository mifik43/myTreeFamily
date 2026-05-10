"""
Объединение двух персон (дубликатов) в одну.
Использование:
    python merge_persons.py <id_основной> <id_второстепенной>
Пример:
    python merge_persons.py 10 15
"""

import sys
from app import create_app
from models import db, Person, Marriage, SiblingLink

def merge(primary_id, secondary_id):
    app = create_app()
    with app.app_context():
        primary = Person.query.get(primary_id)
        secondary = Person.query.get(secondary_id)

        if not primary or not secondary:
            print("Одна из персон не найдена.")
            return

        # Проверяем, что они в одном дереве
        if primary.tree_id != secondary.tree_id:
            print("Персоны находятся в разных деревьях — объединение невозможно.")
            return

        print(f"Объединяем {secondary.full_name} (ID={secondary.id}) в {primary.full_name} (ID={primary.id})")

        # 1. Переносим детей (father_id, mother_id)
        for child in Person.query.filter_by(father_id=secondary.id).all():
            child.father_id = primary.id
        for child in Person.query.filter_by(mother_id=secondary.id).all():
            child.mother_id = primary.id

        # 2. Переносим супругов (браки)
        for m in secondary.marriages_as_husband:
            existing = Marriage.query.filter_by(husband_id=primary.id, wife_id=m.wife_id).first()
            if not existing:
                m.husband_id = primary.id
            else:
                db.session.delete(m)
        for m in secondary.marriages_as_wife:
            existing = Marriage.query.filter_by(husband_id=m.husband_id, wife_id=primary.id).first()
            if not existing:
                m.wife_id = primary.id
            else:
                db.session.delete(m)

        # 3. Переносим явные связи брат/сестра (SiblingLink)
        for link in secondary.sibling_links_1:
            other_id = link.person2_id
            if other_id != primary.id:
                # Создаём новую связь, если её ещё нет
                pid1, pid2 = sorted([primary.id, other_id])
                if not SiblingLink.query.filter_by(person1_id=pid1, person2_id=pid2,
                                                   tree_id=primary.tree_id).first():
                    new_link = SiblingLink(person1_id=pid1, person2_id=pid2,
                                           tree_id=primary.tree_id,
                                           relation_type=link.relation_type)
                    db.session.add(new_link)
            # Удаляем старую связь
            db.session.delete(link)

        for link in secondary.sibling_links_2:
            other_id = link.person1_id
            if other_id != primary.id:
                pid1, pid2 = sorted([primary.id, other_id])
                if not SiblingLink.query.filter_by(person1_id=pid1, person2_id=pid2,
                                                   tree_id=primary.tree_id).first():
                    new_link = SiblingLink(person1_id=pid1, person2_id=pid2,
                                           tree_id=primary.tree_id,
                                           relation_type=link.relation_type)
                    db.session.add(new_link)
            db.session.delete(link)

        # 4. Переносим фотографию, если у основной нет
        if not primary.photo and secondary.photo:
            primary.photo = secondary.photo

        # 5. Обновляем фамилию и девичью фамилию (если у secondary актуальнее)
        # Предположим, что основная персона будет носить фамилию secondary (например, Рывак),
        # а девичья фамилия — та, что у primary (Лобова) или наоборот. Пользователь может настроить.
        # Мы не меняем автоматически, оставляем как есть; можно изменить вручную после объединения.

        # 6. Удаляем второстепенную персону
        db.session.delete(secondary)
        db.session.commit()
        print("Объединение завершено успешно!")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Использование: python merge_persons.py <основной_id> <второстепенный_id>")
        sys.exit(1)
    primary_id = int(sys.argv[1])
    secondary_id = int(sys.argv[2])
    merge(primary_id, secondary_id)