from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    surname = db.Column(db.String(100), nullable=True)
    name = db.Column(db.String(100), nullable=True)
    patronymic = db.Column(db.String(100), nullable=True)
    maiden_name = db.Column(db.String(100), nullable=True)
    gender = db.Column(db.String(1), nullable=True)
    tree = db.relationship('Tree', uselist=False, backref='owner')

class Tree(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    persons = db.relationship('Person', backref='tree', lazy=True)

    def root_persons(self):
        return Person.query.filter_by(tree_id=self.id)\
                           .filter(Person.father_id == None, Person.mother_id == None)\
                           .order_by(Person.surname, Person.name).all()

class Person(db.Model):
    __tablename__ = 'person'
    __table_args__ = (
        db.Index('ix_person_duplicate_check', 'surname', 'name', 'patronymic', 'birth_year'),
    )
    id = db.Column(db.Integer, primary_key=True)
    tree_id = db.Column(db.Integer, db.ForeignKey('tree.id'), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    patronymic = db.Column(db.String(100))
    maiden_name = db.Column(db.String(100), nullable=True)
    gender = db.Column(db.String(1), nullable=False)

    birth_year = db.Column(db.Integer, nullable=True)
    birth_month = db.Column(db.Integer, nullable=True)
    birth_day = db.Column(db.Integer, nullable=True)
    birth_notes = db.Column(db.String(200), nullable=True)

    death_year = db.Column(db.Integer, nullable=True)
    death_month = db.Column(db.Integer, nullable=True)
    death_day = db.Column(db.Integer, nullable=True)
    death_notes = db.Column(db.String(200), nullable=True)

    birth_city = db.Column(db.String(200), nullable=True)
    extra_info = db.Column(db.Text, nullable=True)
    photo = db.Column(db.String(300), nullable=True)
    social_ok = db.Column(db.String(200), nullable=True)
    social_vk = db.Column(db.String(200), nullable=True)
    social_telegram = db.Column(db.String(200), nullable=True)
    social_mail = db.Column(db.String(200), nullable=True)

    father_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    mother_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)

    father = db.relationship('Person', remote_side=[id], foreign_keys=[father_id], backref='children_father')
    mother = db.relationship('Person', remote_side=[id], foreign_keys=[mother_id], backref='children_mother')
    marriages_as_husband = db.relationship('Marriage', foreign_keys='Marriage.husband_id', backref='husband', lazy=True)
    marriages_as_wife = db.relationship('Marriage', foreign_keys='Marriage.wife_id', backref='wife', lazy=True)
    sibling_links_1 = db.relationship('SiblingLink', foreign_keys='SiblingLink.person1_id', backref='person1', lazy=True)
    sibling_links_2 = db.relationship('SiblingLink', foreign_keys='SiblingLink.person2_id', backref='person2', lazy=True)

    @property
    def full_name(self):
        parts = [self.surname, self.name, self.patronymic]
        return ' '.join(filter(None, parts))

    @property
    def birth_display(self):
        if self.birth_notes:
            return self.birth_notes
        parts = []
        if self.birth_day:
            parts.append(str(self.birth_day))
        if self.birth_month:
            parts.append(str(self.birth_month))
        if self.birth_year:
            parts.append(str(self.birth_year))
        return '.'.join(parts) if parts else 'неизвестно'

    @property
    def death_display(self):
        if self.death_notes:
            return self.death_notes
        parts = []
        if self.death_day:
            parts.append(str(self.death_day))
        if self.death_month:
            parts.append(str(self.death_month))
        if self.death_year:
            parts.append(str(self.death_year))
        return '.'.join(parts) if parts else 'жив(а)'

    @property
    def birth_date_obj(self):
        if self.birth_year and self.birth_month and self.birth_day:
            try:
                return date(self.birth_year, self.birth_month, self.birth_day)
            except ValueError:
                return None
        return None

    @property
    def death_date_obj(self):
        if self.death_year and self.death_month and self.death_day:
            try:
                return date(self.death_year, self.death_month, self.death_day)
            except ValueError:
                return None
        return None

    @property
    def spouses(self):
        sp = []
        for m in self.marriages_as_husband:
            sp.append(m.wife)
        for m in self.marriages_as_wife:
            sp.append(m.husband)
        return sp

    @property
    def step_parents(self):
        step = []
        if self.mother:
            for m in self.mother.marriages_as_wife:
                if m.husband_id != self.father_id:
                    step.append(m.husband)
        if self.father:
            for m in self.father.marriages_as_husband:
                if m.wife_id != self.mother_id:
                    step.append(m.wife)
        return step

    @property
    def siblings(self):
        sibs = set()
        if self.father:
            sibs.update(self.father.children_father)
        if self.mother:
            sibs.update(self.mother.children_mother)
        sibs.discard(self)
        for sp in self.step_parents:
            if sp.gender == 'M':
                for child in sp.children_father:
                    if child != self:
                        sibs.add(child)
            else:
                for child in sp.children_mother:
                    if child != self:
                        sibs.add(child)
        for link in self.sibling_links_1:
            if link.person2_id != self.id:
                sibs.add(link.person2)
        for link in self.sibling_links_2:
            if link.person1_id != self.id:
                sibs.add(link.person1)
        return list(sibs)

class Marriage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    husband_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    wife_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    marriage_date = db.Column(db.Date, nullable=True)
    divorce_date = db.Column(db.Date, nullable=True)

class SiblingLink(db.Model):
    __tablename__ = 'sibling_link'
    id = db.Column(db.Integer, primary_key=True)
    person1_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    person2_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    relation_type = db.Column(db.String(50), default='sibling')
    tree_id = db.Column(db.Integer, db.ForeignKey('tree.id'), nullable=False)
    __table_args__ = (
        db.UniqueConstraint('person1_id', 'person2_id', name='unique_sibling_pair'),
    )