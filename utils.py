from models import Person, Tree

def find_duplicates(surname, name, patronymic, birth_year, tree):
    """Возвращает словарь с ключами 'own' и 'others'."""
    if not surname or not name:
        return {'own': [], 'others': []}
    query = Person.query.filter(
        Person.surname == surname,
        Person.name == name
    )
    if patronymic:
        query = query.filter(Person.patronymic == patronymic)
    if birth_year:
        query = query.filter(Person.birth_year == birth_year)
    persons = query.all()
    own = [p for p in persons if p.tree_id == tree.id]
    others = []
    for p in persons:
        if p.tree_id != tree.id:
            t = Tree.query.get(p.tree_id)
            if t:
                owner = t.owner
                others.append((p, owner.username, owner.email))
    return {'own': own, 'others': others}