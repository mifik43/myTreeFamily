from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    trees = db.relationship('Tree', backref='owner', lazy=True)

class Tree(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    persons = db.relationship('Person', backref='tree', lazy=True)

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tree_id = db.Column(db.Integer, db.ForeignKey('tree.id'), nullable=False)
    surname = db.Column(db.String(100), nullable=False)   # фамилия
    name = db.Column(db.String(100), nullable=False)      # имя
    patronymic = db.Column(db.String(100))                # отчество (может быть пустым)
    birth_date = db.Column(db.Date)
    death_date = db.Column(db.Date, nullable=True)
    city = db.Column(db.String(200))
    gender = db.Column(db.String(1), nullable=False)      # 'M' или 'F'
    father_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    mother_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)

    father = db.relationship('Person', remote_side=[id], foreign_keys=[father_id], backref='children_father')
    mother = db.relationship('Person', remote_side=[id], foreign_keys=[mother_id], backref='children_mother')

    # браки, где данная персона муж
    marriages_as_husband = db.relationship('Marriage', foreign_keys='Marriage.husband_id', backref='husband', lazy=True)
    # браки, где данная персона жена
    marriages_as_wife = db.relationship('Marriage', foreign_keys='Marriage.wife_id', backref='wife', lazy=True)

    @property
    def full_name(self):
        parts = [self.surname, self.name, self.patronymic]
        return ' '.join(filter(None, parts))

    @property
    def spouses(self):
        """Список всех супругов (объекты Person)."""
        sp = []
        for m in self.marriages_as_husband:
            sp.append(m.wife)
        for m in self.marriages_as_wife:
            sp.append(m.husband)
        return sp

    @property
    def siblings(self):
        """Братья и сёстры (по общим родителям), исключая самого себя."""
        if not self.father and not self.mother:
            return []
        sibs = set()
        if self.father:
            sibs.update(self.father.children_father)
        if self.mother:
            sibs.update(self.mother.children_mother)
        sibs.discard(self)
        return list(sibs)

class Marriage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    husband_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    wife_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    marriage_date = db.Column(db.Date, nullable=True)
    divorce_date = db.Column(db.Date, nullable=True)