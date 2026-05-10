"""
Импорт данных из XML-файла GenoPro в базу данных Family Tree.
Использование:
    python import_genopro.py <путь_к_xml> <user_id>
Пример:
    python import_genopro.py Data.xml 1
"""
import sys
import os
from datetime import datetime
from xml.etree import ElementTree as ET

from app import create_app
from models import db, Person, Marriage, Tree, SiblingLink

def parse_date(date_str):
    """Парсинг даты из GenoPro (форматы: '12 May 1940', '1906', '7 Nov 1915' и т.п.)"""
    if not date_str:
        return None, None, None, None
    # Пробуем полную дату
    for fmt in ('%d %b %Y', '%d %B %Y', '%Y', '%d.%m.%Y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.year, dt.month, dt.day, None
        except ValueError:
            continue
    # Только год
    if date_str.isdigit():
        year = int(date_str)
        return year, None, None, None
    return None, None, None, date_str  # неопознанный формат -> в notes

def import_genopro(xml_path, user_id):
    app = create_app()
    with app.app_context():
        user_tree = Tree.query.filter_by(user_id=user_id).first()
        if not user_tree:
            print(f"Дерево для пользователя {user_id} не найдено. Создайте пользователя и дерево.")
            return

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Словари для накопления данных
        individuals = {}    # id -> dict с данными
        occupations = {}    # id -> название
        places = {}         # id -> название
        families = {}       # id -> dict {husband_id, wife_id, children_ids, marriage_id}

        # 1. Читаем места
        for place in root.findall('.//Place'):
            pid = place.get('ID')
            name = place.findtext('Name', '')
            places[pid] = name

        # 2. Читаем занятия (города)
        for occ in root.findall('.//Occupation'):
            oid = occ.get('ID')
            title = occ.findtext('Title', '')
            occupations[oid] = title

        # 3. Читаем персон
        for ind in root.findall('.//Individual'):
            ind_id = ind.get('ID')
            name_el = ind.find('Name')
            if name_el is None:
                continue
            first = name_el.findtext('First', '').strip()
            middle = name_el.findtext('Middle', '').strip()
            last = name_el.findtext('Last', '').strip()

            # Разбираем девичью фамилию в скобках, например "Лобова (Декусар)"
            maiden = None
            if '(' in first and ')' in first:
                parts = first.split('(')
                surname = parts[0].strip()
                maiden_candidate = parts[1].replace(')', '').strip()
                if maiden_candidate:
                    maiden = maiden_candidate
                first = surname
            else:
                # если скобок нет, то surname = first
                pass
            surname = first if first else middle  # иногда фамилия в middle
            name = middle if first else last      # если first пусто
            patronymic = last if first else None

            gender = ind.findtext('Gender', '')
            birth_el = ind.find('Birth')
            death_el = ind.find('Death')
            is_dead = ind.findtext('IsDead', 'N') == 'Y'

            birth_str = birth_el.findtext('Date', '') if birth_el else ''
            death_str = death_el.findtext('Date', '') if death_el else ''

            b_year, b_month, b_day, b_notes = parse_date(birth_str)
            d_year, d_month, d_day, d_notes = parse_date(death_str)

            # Город рождения из Birth/Place
            birth_city = None
            if birth_el is not None:
                place_ref = birth_el.findtext('Place', '')
                if place_ref and place_ref in places:
                    birth_city = places[place_ref]

            # Занятия -> extra_info
            occ_refs = []
            for occ_ref in ind.findall('.//Occupations'):
                occ_id = occ_ref.text.strip()
                if occ_id in occupations:
                    occ_refs.append(occupations[occ_id])
            extra_info = '; '.join(occ_refs) if occ_refs else None
            if extra_info and 'Москва' in extra_info:
                # Можно также установить birth_city, если ещё не задано
                if not birth_city:
                    birth_city = extra_info.split(';')[0].strip()

            # Фотографии
            photo = None
            for pic_ref in ind.findall('.//Pictures'):
                pic_id = pic_ref.text.strip()
                # Ищем Picture элемент
                pic_el = root.find(f".//Picture[@ID='{pic_id}']")
                if pic_el is not None:
                    file_unique = pic_el.findtext('Path', '')
                    photo = file_unique  # позже можно скопировать файл

            individuals[ind_id] = {
                'surname': surname,
                'name': name,
                'patronymic': patronymic,
                'maiden_name': maiden,
                'gender': gender,
                'birth_year': b_year, 'birth_month': b_month, 'birth_day': b_day,
                'birth_notes': b_notes,
                'death_year': d_year, 'death_month': d_month, 'death_day': d_day,
                'death_notes': d_notes,
                'birth_city': birth_city,
                'extra_info': extra_info,
                'photo': photo,
                'is_dead': is_dead
            }

        # 4. Читаем семьи
        for fam in root.findall('.//Family'):
            fam_id = fam.get('ID')
            relation = fam.findtext('Relation', '')
            union_ref = fam.findtext('Unions', '')  # ссылка на Marriage
            families[fam_id] = {
                'husband_id': None,
                'wife_id': None,
                'children_ids': [],
                'marriage_id': union_ref if relation == 'Marriage' else None
            }

        # 5. Читаем PedigreeLinks и связываем
        for link in root.findall('.//PedigreeLink'):
            link_type = link.get('PedigreeLink')
            family_id = link.get('Family')
            ind_id = link.get('Individual')
            if family_id not in families:
                continue
            if link_type == 'Parent':
                # Определяем пол по индив. и назначаем родителем
                ind_data = individuals.get(ind_id)
                if ind_data and ind_data['gender'] == 'M':
                    families[family_id]['husband_id'] = ind_id
                elif ind_data and ind_data['gender'] == 'F':
                    families[family_id]['wife_id'] = ind_id
            elif link_type == 'Biological':
                families[family_id]['children_ids'].append(ind_id)

        # 6. Читаем браки
        marriages_data = {}
        for marr in root.findall('.//Marriage'):
            marr_id = marr.get('ID')
            date_str = marr.findtext('Date', '')
            if date_str:
                marr_date = parse_date(date_str)
                # нас интересует только полная дата для Marriage.date
                if marr_date[0]:
                    m_date = datetime(marr_date[0], marr_date[1] or 1, marr_date[2] or 1).date()
                else:
                    m_date = None
            else:
                m_date = None
            marriages_data[marr_id] = m_date

        # 7. Импорт в базу данных
        # Сначала создаём всех персон (чтобы получить id)
        person_map = {}  # старый_id -> new Person
        print("Импорт персон...")
        for old_id, data in individuals.items():
            person = Person(
                tree_id=user_tree.id,
                surname=data['surname'],
                name=data['name'],
                patronymic=data['patronymic'],
                gender=data['gender'],
                birth_year=data['birth_year'],
                birth_month=data['birth_month'],
                birth_day=data['birth_day'],
                birth_notes=data['birth_notes'],
                death_year=data['death_year'],
                death_month=data['death_month'],
                death_day=data['death_day'],
                death_notes=data['death_notes'],
                birth_city=data['birth_city'],
                extra_info=data['extra_info'],
                photo=data['photo'],
                maiden_name=data.get('maiden_name'),
                # соцсети не заполняем
            )
            db.session.add(person)
            db.session.flush()  # получаем person.id
            person_map[old_id] = person

        db.session.commit()
        print(f"Создано {len(person_map)} персон.")

        # Создаём связи (семьи)
        print("Импорт семей и браков...")
        for fam_id, fam in families.items():
            husband = person_map.get(fam['husband_id'])
            wife = person_map.get(fam['wife_id'])

            # Устанавливаем родителей для детей
            for child_id in fam['children_ids']:
                child = person_map.get(child_id)
                if child:
                    if husband:
                        child.father_id = husband.id
                    if wife:
                        child.mother_id = wife.id

            # Если есть брак, создаём Marriage
            if fam['marriage_id'] and husband and wife:
                marr_date = marriages_data.get(fam['marriage_id'])
                # Проверка, что такой брак ещё не существует (по участникам)
                existing = Marriage.query.filter(
                    Marriage.husband_id == husband.id,
                    Marriage.wife_id == wife.id
                ).first()
                if not existing:
                    marriage = Marriage(
                        husband_id=husband.id,
                        wife_id=wife.id,
                        marriage_date=marr_date
                    )
                    db.session.add(marriage)

        db.session.commit()
        print("Импорт завершён успешно!")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Использование: python import_genopro.py <путь_к_xml> <user_id>")
        sys.exit(1)
    xml_path = sys.argv[1]
    user_id = int(sys.argv[2])
    import_genopro(xml_path, user_id)