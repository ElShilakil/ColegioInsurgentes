from extensions import db
from datetime import datetime
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

class SchoolPeriod(db.Model):
    __tablename__ = 'school_periods'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey('school_periods.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    percentage_value = db.Column(db.Float, nullable=False)

    subject = db.relationship('Subject', backref='activities')
    period = db.relationship('SchoolPeriod', backref='activities')

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
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)
