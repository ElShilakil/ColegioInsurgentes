from extensions import db
from models import User, Subject, Student, TeacherAssignment, Activity, Grade, Attendance
from datetime import datetime

def create_admin():
    if not User.query.filter_by(role='admin').first():
        admin = User(
            first_name="Administrador", 
            last_name_paternal="Escolar",
            last_name_maternal="",
            email="admin1@cinsurgentes.edu.mx", 
            role="admin"
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: admin1@cinsurgentes.edu.mx / admin123")
