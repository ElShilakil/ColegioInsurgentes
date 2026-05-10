import random
from datetime import date, timedelta, datetime
from app import create_app
from extensions import db
from models import User, Student, TeacherAssignment, Subject, SchoolCycle, Trimester, Activity, Grade, Attendance
from utils import create_admin
from werkzeug.security import generate_password_hash

# Datos para realismo
NOMBRES_H = ["Juan", "Pedro", "Luis", "Carlos", "Miguel", "Javier", "Roberto", "Alejandro", "Ricardo", "Fernando", "Diego", "Gabriel", "Hugo", "Oscar", "Daniel", "Mateo", "Santiago", "Sebastian"]
NOMBRES_M = ["Maria", "Ana", "Lucia", "Elena", "Sofia", "Isabel", "Martha", "Gabriela", "Adriana", "Claudia", "Beatriz", "Raquel", "Ximena", "Valeria", "Camila", "Daniela", "Paola", "Fernanda"]
APELLIDOS = ["Garcia", "Martinez", "Lopez", "Gonzalez", "Rodriguez", "Perez", "Sanchez", "Ramirez", "Cruz", "Flores", "Gomez", "Morales", "Vazquez", "Jimenez", "Reyes", "Hernandez", "Diaz", "Torres", "Ruiz", "Mendoza", "Aguilar", "Ortiz", "Moreno", "Castillo", "Romero", "Alvarez", "Mendez", "Chavez", "Rivera", "Juarez"]

def generate_curp(first_name, last_p, last_m, birth_date, gender):
    # Generador de CURP simplificado para propósitos de seeding
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    curp = (last_p[:2] + (last_m[0] if last_m else 'X') + first_name[0]).upper()
    curp += birth_date.strftime("%y%m%d")
    curp += gender
    curp += "DF" # Ciudad de Mexico
    curp += "".join(random.choice(abc) for _ in range(3))
    curp += str(random.randint(0, 9))
    return curp[:18]

def seed():
    app = create_app()
    with app.app_context():
        print("Borrando datos existentes...")
        Attendance.query.delete()
        Grade.query.delete()
        Activity.query.delete()
        TeacherAssignment.query.delete()
        Student.query.delete()
        User.query.delete()
        Trimester.query.delete()
        SchoolCycle.query.delete()
        Subject.query.delete()
        db.session.commit()

        print("Creando administrador...")
        create_admin()

        print("Creando materias (Nueva Escuela Mexicana)...")
        subjects_data = [
            ("Lengua Materna (Español)", "Lenguajes"),
            ("Inglés", "Lenguajes"),
            ("Artes", "Lenguajes"),
            ("Matemáticas", "Saberes y pensamiento científico"),
            ("Ciencias Naturales", "Saberes y pensamiento científico"),
            ("Conocimiento del Medio", "Ética, naturaleza y sociedades"),
            ("Historia", "Ética, naturaleza y sociedades"),
            ("Geografía", "Ética, naturaleza y sociedades"),
            ("Formación Cívica y Ética", "De lo humano y lo comunitario"),
            ("Educación Física", "De lo humano y lo comunitario"),
            ("Vida Saludable", "De lo humano y lo comunitario")
        ]
        all_subjects = []
        for name, field in subjects_data:
            s = Subject(name=name, formative_field=field)
            db.session.add(s)
            all_subjects.append(s)
        db.session.commit()

        print("Creando ciclos escolares y trimestres históricos...")
        # Ciclo 2024-2025
        cycle_past = SchoolCycle(name="2024-2025", is_active=False)
        db.session.add(cycle_past)
        db.session.flush()

        t1_past = Trimester(cycle_id=cycle_past.id, name="Trimestre 1 (24-25)", 
                            start_date=date(2024, 8, 26), end_date=date(2024, 11, 22), is_active=False)
        t2_past = Trimester(cycle_id=cycle_past.id, name="Trimestre 2 (24-25)", 
                            start_date=date(2024, 11, 25), end_date=date(2025, 3, 21), is_active=False)
        t3_past = Trimester(cycle_id=cycle_past.id, name="Trimestre 3 (24-25)", 
                            start_date=date(2025, 3, 24), end_date=date(2025, 7, 11), is_active=False)

        # Ciclo 2025-2026
        cycle_current = SchoolCycle(name="2025-2026", is_active=True)
        db.session.add(cycle_current)
        db.session.flush()

        t1_curr = Trimester(cycle_id=cycle_current.id, name="Trimestre 1 (25-26)", 
                            start_date=date(2025, 8, 25), end_date=date(2025, 11, 21), is_active=False)
        t2_curr = Trimester(cycle_id=cycle_current.id, name="Trimestre 2 (25-26)", 
                            start_date=date(2025, 11, 24), end_date=date(2026, 3, 20), is_active=False)
        t3_curr = Trimester(cycle_id=cycle_current.id, name="Trimestre 3 (25-26)", 
                            start_date=date(2026, 3, 23), end_date=date(2026, 7, 10), is_active=True)

        all_trimesters = [t1_past, t2_past, t3_past, t1_curr, t2_curr, t3_curr]
        db.session.add_all(all_trimesters)
        db.session.commit()

        print("Creando maestros y asignando grupos...")
        groups = []
        for g in range(1, 7):
            for section in ['A', 'B', 'C']:
                groups.append((g, section))
        
        teachers = []
        password_hash = generate_password_hash("admin")
        
        for i, (grade, group) in enumerate(groups):
            gender = random.choice(['H', 'M'])
            first_name = random.choice(NOMBRES_H if gender == 'H' else NOMBRES_M)
            last_p = random.choice(APELLIDOS)
            last_m = random.choice(APELLIDOS)
            username = f"{first_name.lower()}.{last_p.lower()}"
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{first_name.lower()}.{last_p.lower()}{counter}"
                counter += 1

            teacher = User(first_name=first_name, last_name_paternal=last_p, last_name_maternal=last_m,
                          username=username, password_hash=password_hash, role='teacher')
            db.session.add(teacher)
            db.session.flush()
            
            assignment = TeacherAssignment(teacher_id=teacher.id, grade=grade, group=group)
            db.session.add(assignment)
            teachers.append(teacher)
        db.session.commit()

        print("Creando alumnos...")
        students_by_group = {}
        for grade, group in groups:
            students_by_group[(grade, group)] = []
            for _ in range(10):
                gender = random.choice(['H', 'M'])
                first_name = random.choice(NOMBRES_H if gender == 'H' else NOMBRES_M)
                last_p = random.choice(APELLIDOS)
                last_m = random.choice(APELLIDOS)
                birth_date = date(2015 - grade, random.randint(1, 12), random.randint(1, 28))
                
                student = Student(
                    curp=generate_curp(first_name, last_p, last_m, birth_date, gender),
                    first_name=first_name, last_name_paternal=last_p, last_name_maternal=last_m,
                    grade=grade, group=group
                )
                db.session.add(student)
                students_by_group[(grade, group)].append(student)
        db.session.commit()

        print("Generando historial de actividades y calificaciones (Desde Sep 2024)...")
        activity_types = [("Examen", 50.0), ("Tareas", 20.0), ("Participación", 10.0), ("Proyecto", 20.0)]
        today = date.today()
        
        for teacher in teachers:
            grade = teacher.assignment.grade
            group = teacher.assignment.group
            students = students_by_group[(grade, group)]
            
            for trim in all_trimesters:
                if trim.start_date > today:
                    continue
                
                for subj in all_subjects:
                    for act_name, pct in activity_types:
                        limit_date = min(trim.end_date, today)
                        days_diff = (limit_date - trim.start_date).days
                        if days_diff < 1: days_diff = 1
                        act_date = trim.start_date + timedelta(days=random.randint(0, days_diff))
                        
                        activity = Activity(
                            teacher_id=teacher.id, grade=grade, group=group,
                            subject_id=subj.id, trimester_id=trim.id,
                            name=f"{act_name} - {subj.name}", type=act_name,
                            date=act_date, percentage_value=pct
                        )
                        db.session.add(activity)
                        db.session.flush()
                        
                        for student in students:
                            score = random.uniform(6.0, 10.0)
                            if random.random() < 0.05: score = random.uniform(5.0, 6.0)
                            db.session.add(Grade(student_id=student.id, activity_id=activity.id, score=round(score, 1)))
        db.session.commit()

        print("Generando historial masivo de asistencias (Lunes a Viernes, desde Sep 2024)...")
        start_date = date(2024, 9, 1)
        end_date = today
        delta = end_date - start_date
        all_students = Student.query.all()
        
        for i in range(delta.days + 1):
            current_day = start_date + timedelta(days=i)
            if current_day.weekday() >= 5: # Saltar Sábado y Domingo
                continue
            
            for student in all_students:
                rand = random.random()
                if rand < 0.85: status = "Asistencia"
                elif rand < 0.93: status = "Retardo"
                elif rand < 0.97: status = "Falta"
                else: status = "Falta Justificada"
                
                db.session.add(Attendance(student_id=student.id, date=current_day, status=status))
            
            if i % 10 == 0:
                db.session.commit()
                print(f"Progreso de asistencias: {current_day} procesado.")

        db.session.commit()
        print("Seeding histórico completado con éxito.")

if __name__ == "__main__":
    seed()
