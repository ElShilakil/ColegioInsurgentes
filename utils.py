from extensions import db
from models import User, Subject, Student, TeacherAssignment, Activity, Grade, Attendance
from datetime import datetime

def create_admin():
    # Buscamos si ya existe un admin con el nuevo username
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        # Si no existe, lo creamos
        admin = User(
            first_name="Administrador", 
            last_name_paternal="Sistema",
            last_name_maternal="",
            username="admin", 
            role="admin"
        )
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()
        print("Admin user created/updated: admin / admin")
    else:
        # Si ya existe, nos aseguramos de que la contraseña sea 'admin'
        admin.set_password("admin")
        db.session.commit()
        print("Admin password reset to: admin")
