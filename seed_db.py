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
            # Lenguajes
            ("Lengua Materna (Español)", "Lenguajes"),
            ("Inglés", "Lenguajes"),
            ("Artes", "Lenguajes"),
            # Saberes y pensamiento científico
            ("Matemáticas", "Saberes y pensamiento científico"),
            ("Ciencias Naturales", "Saberes y pensamiento científico"),
            # Ética, naturaleza y sociedades
            ("Conocimiento del Medio", "Ética, naturaleza y sociedades"),
            ("Historia", "Ética, naturaleza y sociedades"),
            ("Geografía", "Ética, naturaleza y sociedades"),
            # De lo humano y lo comunitario
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

        print("Creando ciclo escolar y trimestres...")
        cycle = SchoolCycle(name="2025-2026", is_active=True)
        db.session.add(cycle)
        db.session.flush()

        t1 = Trimester(cycle_id=cycle.id, name="Septiembre-Noviembre", 
                       start_date=date(2025, 9, 1), end_date=date(2025, 11, 30), is_active=False)
        t2 = Trimester(cycle_id=cycle.id, name="Diciembre-Marzo", 
                       start_date=date(2025, 12, 1), end_date=date(2026, 3, 31), is_active=False)
        t3 = Trimester(cycle_id=cycle.id, name="Abril-Junio", 
                       start_date=date(2026, 4, 1), end_date=date(2026, 6, 30), is_active=True)
        trimesters = [t1, t2, t3]
        db.session.add_all(trimesters)
        db.session.commit()

        print("Creando 18 maestros y asignando grupos...")
        groups = []
        for g in range(1, 7):
            for section in ['A', 'B', 'C']:
                groups.append((g, section))
        
        teachers = []
        password_hash = generate_password_hash("admin123")
        
        for i, (grade, group) in enumerate(groups):
            gender = random.choice(['H', 'M'])
            first_name = random.choice(NOMBRES_H if gender == 'H' else NOMBRES_M)
            last_p = random.choice(APELLIDOS)
            last_m = random.choice(APELLIDOS)
            
            # Formato: nombre.primerapellido@cinsurgentes.edu.mx
            email = f"{first_name.lower()}.{last_p.lower()}@cinsurgentes.edu.mx"
            
            # Evitar duplicados de email en seed
            counter = 1
            while User.query.filter_by(email=email).first():
                email = f"{first_name.lower()}.{last_p.lower()}{counter}@cinsurgentes.edu.mx"
                counter += 1

            teacher = User(
                first_name=first_name,
                last_name_paternal=last_p,
                last_name_maternal=last_m,
                email=email,
                password_hash=password_hash,
                role='teacher'
            )
            db.session.add(teacher)
            db.session.flush()
            
            assignment = TeacherAssignment(teacher_id=teacher.id, grade=grade, group=group)
            db.session.add(assignment)
            teachers.append(teacher)
        
        db.session.commit()

        print("Creando 180 alumnos (10 por grupo)...")
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
                    first_name=first_name,
                    last_name_paternal=last_p,
                    last_name_maternal=last_m,
                    nombre_tutor=f"{random.choice(NOMBRES_H + NOMBRES_M)} {last_p} {random.choice(APELLIDOS)}",
                    telefono_tutor=f"55{random.randint(10000000, 99999999)}",
                    email_tutor=f"tutor_{random.randint(100, 999)}@gmail.com",
                    grade=grade,
                    group=group
                )
                db.session.add(student)
                students_by_group[(grade, group)].append(student)
        db.session.commit()

        print("Generando actividades y calificaciones...")
        # Tipos de actividad y sus porcentajes sugeridos
        activity_types = [
            ("Examen", 50.0),
            ("Tareas", 20.0),
            ("Participación", 10.0),
            ("Proyecto", 20.0)
        ]

        # Solo generar actividades para trimestres 1 y 2, y tal vez algunas para el 3 (actual)
        today = date.today()
        
        for teacher in teachers:
            # El maestro está asignado a un grupo
            grade = teacher.assignment.grade
            group = teacher.assignment.group
            students = students_by_group[(grade, group)]
            
            for trim in trimesters:
                if trim.start_date > today:
                    continue # No hay actividades para el futuro
                
                # Para cada materia
                for subj in all_subjects:
                    for act_name, pct in activity_types:
                        # Crear actividad
                        act_date = trim.start_date + timedelta(days=random.randint(0, (min(trim.end_date, today) - trim.start_date).days))
                        
                        activity = Activity(
                            teacher_id=teacher.id,
                            subject_id=subj.id,
                            trimester_id=trim.id,
                            name=f"{act_name} - {subj.name}",
                            type=act_name,
                            date=act_date,
                            percentage_value=pct
                        )
                        db.session.add(activity)
                        db.session.flush()
                        
                        # Calificar a todos los alumnos del grupo
                        for student in students:
                            score = random.uniform(6.0, 10.0)
                            if random.random() < 0.05: # 5% de probabilidad de reprobar feo
                                score = random.uniform(5.0, 6.0)
                            
                            grade_record = Grade(
                                student_id=student.id,
                                activity_id=activity.id,
                                score=round(score, 1)
                            )
                            db.session.add(grade_record)
        
        db.session.commit()

        print("Generando historial de asistencias...")
        start_date = date(2025, 9, 1)
        end_date = today
        
        delta = end_date - start_date
        all_students = Student.query.all()
        
        # Para optimizar, no agregaremos cada día individualmente en un loop gigante si es muy lento,
        # pero como son 180 alumnos y ~150 días hábiles, son ~27,000 registros. SQLAlchemy puede manejarlo.
        
        for i in range(delta.days + 1):
            current_day = start_date + timedelta(days=i)
            # Saltar fines de semana
            if current_day.weekday() >= 5:
                continue
            
            for student in all_students:
                # 90% Asistencia, 7% Retardo, 3% Falta
                rand = random.random()
                if rand < 0.90:
                    status = "Asistencia"
                elif rand < 0.97:
                    status = "Retardo"
                else:
                    status = "Falta"
                
                attendance = Attendance(
                    student_id=student.id,
                    date=current_day,
                    status=status
                )
                db.session.add(attendance)
            
            # Commit parcial cada 10 días para no saturar memoria
            if i % 10 == 0:
                db.session.commit()
                print(f"Progreso de asistencias: {current_day}")

        db.session.commit()
        print("Seeding completado con éxito.")

if __name__ == "__main__":
    seed()
