from extensions import db
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name_paternal = db.Column(db.String(50), nullable=False)
    last_name_maternal = db.Column(db.String(50))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name_paternal} {self.last_name_maternal or ''}".strip()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    curp = db.Column(db.String(18), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name_paternal = db.Column(db.String(50), nullable=False)
    last_name_maternal = db.Column(db.String(50))
    nombre_tutor = db.Column(db.String(100))
    telefono_tutor = db.Column(db.String(20))
    email_tutor = db.Column(db.String(120))
    grade = db.Column(db.Integer, nullable=False)
    group = db.Column(db.String(1), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name_paternal} {self.last_name_maternal or ''}".strip()

class TeacherAssignment(db.Model):
    __tablename__ = 'teacher_assignments'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    group = db.Column(db.String(1), nullable=False)
    
    teacher = db.relationship('User', backref=db.backref('assignment', uselist=False))

    __table_args__ = (UniqueConstraint('grade', 'group', name='_grade_group_uc'),)

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    formative_field = db.Column(db.String(100), nullable=False)

class SchoolCycle(db.Model):
    __tablename__ = 'school_cycles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=False)
    
    trimesters = db.relationship('Trimester', backref='cycle', cascade="all, delete-orphan", order_by="Trimester.id")

class Trimester(db.Model):
    __tablename__ = 'trimesters'
    id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('school_cycles.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False) # Ej: "Trimestre 1"
    start_date = db.Column(db.Date, nullable=True) # En blanco al inicio
    end_date = db.Column(db.Date, nullable=True)   # En blanco al inicio
    is_active = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "cycle_id": self.cycle_id,
            "cycle_name": self.cycle.name,
            "name": self.name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active
        }

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    trimester_id = db.Column(db.Integer, db.ForeignKey('trimesters.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    percentage_value = db.Column(db.Float, nullable=False)

    subject = db.relationship('Subject', backref='activities')
    trimester = db.relationship('Trimester', backref='activities')

class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)

    activity = db.relationship('Activity', backref='grades')
    student = db.relationship('Student', backref='grades')

    __table_args__ = (UniqueConstraint('student_id', 'activity_id', name='_student_activity_uc'),)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(20), nullable=False)
