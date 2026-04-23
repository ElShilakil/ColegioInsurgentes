from app import app
from extensions import db
from models import User, Student, TeacherAssignment, Subject, SchoolCycle, Trimester, Activity, Grade, Attendance
from datetime import date

def migrate():
    with app.app_context():
        print("Iniciando migración de base de datos...")
        
        # Crear todas las tablas según los modelos actuales
        db.create_all()
        print("Tablas creadas/verificadas con éxito.")

        # Verificar si ya existe un ciclo escolar, si no, crear uno por defecto para pruebas
        if not SchoolCycle.query.first():
            print("Configurando ciclo escolar inicial 2025-2026...")
            ciclo = SchoolCycle(
                name="2025-2026",
                is_active=True
            )
            db.session.add(ciclo)
            
            # Crear los 3 trimestres sugeridos en blanco para que el admin los configure
            t1 = Trimester(cycle=ciclo, name="Trimestre 1", is_active=True)
            t2 = Trimester(cycle=ciclo, name="Trimestre 2", is_active=False)
            t3 = Trimester(cycle=ciclo, name="Trimestre 3", is_active=False)
            
            db.session.add_all([t1, t2, t3])
            db.session.commit()
            print("Ciclo escolar inicial y trimestres vacíos creados.")

        print("Migración completada con éxito.")

if __name__ == '__main__':
    migrate()
