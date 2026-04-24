from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import User, Student, TeacherAssignment, Subject, Grade, Trimester, SchoolCycle
from decorators import login_required
from sqlalchemy.exc import IntegrityError
import re
from datetime import datetime, date

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required(permission='MANAGE_STUDENTS')
def admin_dashboard():
    teacher_count = User.query.filter_by(role='teacher').count()
    student_count = Student.query.filter_by(is_active=True).count()
    active_period = Trimester.query.filter_by(is_active=True).first()
    return render_template('admin/dashboard.html', 
                           teacher_count=teacher_count, 
                           student_count=student_count, 
                           active_period=active_period)

@admin_bp.route('/periods', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ASSIGNMENTS') 
def manage_periods():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'setup_cycle':
            name = request.form.get('name')
            
            # VALIDACIÓN ESTRICTA: Consultar Trimestre 3 del ciclo activo actual
            active_cycle = SchoolCycle.query.filter_by(is_active=True).first()
            if active_cycle:
                # El tercer trimestre es el último (ordenado por ID)
                t3 = Trimester.query.filter_by(cycle_id=active_cycle.id).order_by(Trimester.id.desc()).first()
                if t3 and t3.end_date:
                    if date.today() < t3.end_date:
                        flash(f"No se puede crear un nuevo ciclo. El Trimestre 3 del ciclo {active_cycle.name} termina hasta el {t3.end_date.strftime('%d/%m/%Y')}.", "error")
                        return redirect(url_for('admin.manage_periods'))

            # Crear ciclo (fechas en blanco para trimestres)
            new_cycle = SchoolCycle(name=name)
            db.session.add(new_cycle)
            
            for i in range(1, 4):
                t = Trimester(
                    cycle=new_cycle,
                    name=f"Trimestre {i}",
                    is_active=False
                )
                db.session.add(t)
            
            db.session.commit()
            flash("Ciclo y trimestres vacíos creados con éxito.", "success")
            
        elif action == 'edit_trimester_dates':
            trimester_id = request.form.get('trimester_id')
            new_start = date.fromisoformat(request.form.get('start_date'))
            new_end = date.fromisoformat(request.form.get('end_date'))
            
            if new_end <= new_start:
                flash("Error: La fecha de fin debe ser posterior a la de inicio.", "error")
                return redirect(url_for('admin.manage_periods'))

            t = Trimester.query.get(trimester_id)
            if t:
                # Obtener todos los trimestres del ciclo ordenados
                all_t = Trimester.query.filter_by(cycle_id=t.cycle_id).order_by(Trimester.id).all()
                idx = all_t.index(t)

                # Validar contra el trimestre anterior (si existe)
                if idx > 0:
                    prev_t = all_t[idx-1]
                    if prev_t.end_date and new_start <= prev_t.end_date:
                        flash(f"Error: El {t.name} no puede iniciar antes o el mismo día que termina el {prev_t.name} ({prev_t.end_date.strftime('%d/%m/%Y')}).", "error")
                        return redirect(url_for('admin.manage_periods'))

                # Validar contra el trimestre siguiente (si existe)
                if idx < len(all_t) - 1:
                    next_t = all_t[idx+1]
                    if next_t.start_date and new_end >= next_t.start_date:
                        flash(f"Error: El {t.name} no puede terminar después o el mismo día que inicia el {next_t.name} ({next_t.start_date.strftime('%d/%m/%Y')}).", "error")
                        return redirect(url_for('admin.manage_periods'))

                t.start_date = new_start
                t.end_date = new_end
                db.session.commit()
                flash(f"Fechas de {t.name} actualizadas correctamente.", "success")

        elif action == 'set_active':
            trimester_id = request.form.get('active_trimester')
            if trimester_id:
                selected_t = Trimester.query.get(trimester_id)
                Trimester.query.filter_by(cycle_id=selected_t.cycle_id).update({Trimester.is_active: False})
                selected_t.is_active = True
                
                SchoolCycle.query.update({SchoolCycle.is_active: False})
                selected_t.cycle.is_active = True
                
                db.session.commit()
                flash(f"{selected_t.name} del ciclo {selected_t.cycle.name} activado.", "success")

        return redirect(url_for('admin.manage_periods'))

    cycles = SchoolCycle.query.order_by(SchoolCycle.id.desc()).all()
    return render_template('admin/periods.html', cycles=cycles)

@admin_bp.route('/teachers', methods=['GET', 'POST'])
@login_required(permission='MANAGE_TEACHERS')
def manage_teachers():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name_paternal = request.form.get('last_name_paternal')
        last_name_maternal = request.form.get('last_name_maternal')
        email = request.form.get('email')
        password = request.form.get('password')
        
        name_regex = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$'
        password_regex = r'^(?=.*[A-Z])(?=.*\d).{8,}$'

        if not re.match(name_regex, first_name) or not re.match(name_regex, last_name_paternal) or (last_name_maternal and not re.match(name_regex, last_name_maternal)):
            flash("Los nombres y apellidos deben contener solo letras.", "error")
        elif not re.match(r'^[^@]{5,}@cinsurgentes\.edu\.mx$', email):
            flash("El correo debe tener al menos 5 caracteres antes del dominio @cinsurgentes.edu.mx", "error")
        elif not re.match(password_regex, password):
            flash("La contraseña debe tener al menos 8 caracteres, incluir una mayúscula y un número.", "error")
        elif User.query.filter_by(email=email).first():
            flash("El correo ya está registrado.", "error")
        else:
            try:
                new_teacher = User(
                    first_name=first_name, 
                    last_name_paternal=last_name_paternal, 
                    last_name_maternal=last_name_maternal,
                    email=email, 
                    role='teacher'
                )
                new_teacher.set_password(password)
                db.session.add(new_teacher)
                db.session.commit()
                flash("Profesor registrado con éxito.", "success")
            except Exception:
                db.session.rollback()
                flash("Error al registrar el profesor.", "error")
    
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/teachers.html', teachers=teachers)

@admin_bp.route('/teachers/toggle/<int:id>')
@login_required(permission='MANAGE_TEACHERS')
def toggle_teacher(id):
    teacher = User.query.get_or_404(id)
    teacher.is_active = not teacher.is_active
    db.session.commit()
    status = "activado" if teacher.is_active else "desactivado"
    flash(f"Profesor {status} con éxito.", "success")
    return redirect(url_for('admin.manage_teachers'))

@admin_bp.route('/teachers/edit/<int:id>', methods=['GET', 'POST'])
@login_required(permission='MANAGE_TEACHERS')
def edit_teacher(id):
    teacher = User.query.get_or_404(id)
    if request.method == 'POST':
        email = request.form.get('email')
        if not re.match(r'^.{5,}@cinsurgentes\.edu\.mx$', email):
            flash("El correo debe tener más de 4 caracteres y el dominio @cinsurgentes.edu.mx", "error")
            return redirect(url_for('admin.edit_teacher', id=id))
        
        if email != teacher.email and User.query.filter_by(email=email).first():
            flash("Ese correo ya está en uso por otro usuario.", "error")
            return redirect(url_for('admin.edit_teacher', id=id))

        try:
            teacher.first_name = request.form.get('first_name')
            teacher.last_name_paternal = request.form.get('last_name_paternal')
            teacher.last_name_maternal = request.form.get('last_name_maternal')
            teacher.email = email
            
            new_password = request.form.get('password')
            if new_password:
                teacher.set_password(new_password)
                
            db.session.commit()
            flash("Datos del profesor actualizados.", "success")
            return redirect(url_for('admin.manage_teachers'))
        except Exception:
            db.session.rollback()
            flash("Error al actualizar datos.", "error")

    return render_template('admin/edit_teacher.html', teacher=teacher)

@admin_bp.route('/students', methods=['GET', 'POST'])
@login_required(permission='MANAGE_STUDENTS')
def manage_students():
    if request.method == 'POST':
        curp = request.form.get('curp')
        first_name = request.form.get('first_name')
        last_name_paternal = request.form.get('last_name_paternal')
        last_name_maternal = request.form.get('last_name_maternal')
        nombre_tutor = request.form.get('nombre_tutor')
        telefono_tutor = request.form.get('telefono_tutor')
        email_tutor = request.form.get('email_tutor')
        grade = request.form.get('grade')
        group = request.form.get('group')
        
        name_regex = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$'
        curp_regex = r'^[A-Z0-9]{18}$'

        if not re.match(curp_regex, curp):
            flash("El CURP debe tener exactamente 18 caracteres alfanuméricos.", "error")
        elif not re.match(name_regex, first_name) or not re.match(name_regex, last_name_paternal) or (last_name_maternal and not re.match(name_regex, last_name_maternal)):
            flash("Los nombres y apellidos deben contener solo letras.", "error")
        elif Student.query.filter_by(curp=curp).first():
            flash("El CURP ya está registrado.", "error")
        else:
            try:
                new_student = Student(
                    curp=curp, 
                    first_name=first_name,
                    last_name_paternal=last_name_paternal,
                    last_name_maternal=last_name_maternal,
                    nombre_tutor=nombre_tutor,
                    telefono_tutor=telefono_tutor,
                    email_tutor=email_tutor,
                    grade=grade, 
                    group=group
                )
                db.session.add(new_student)
                db.session.commit()
                flash("Estudiante registrado con éxito.", "success")
            except Exception:
                db.session.rollback()
                flash("Error al registrar el estudiante.", "error")
            
    students = Student.query.filter_by(is_active=True).order_by(Student.grade, Student.group).all()
    return render_template('admin/students.html', students=students)

@admin_bp.route('/students/edit/<int:id>', methods=['GET', 'POST'])
@login_required(permission='MANAGE_STUDENTS')
def edit_student(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        curp = request.form.get('curp')
        if curp != student.curp and Student.query.filter_by(curp=curp).first():
            flash("Ese CURP ya pertenece a otro estudiante.", "error")
            return redirect(url_for('admin.edit_student', id=id))

        try:
            student.curp = curp
            student.first_name = request.form.get('first_name')
            student.last_name_paternal = request.form.get('last_name_paternal')
            student.last_name_maternal = request.form.get('last_name_maternal')
            student.nombre_tutor = request.form.get('nombre_tutor')
            student.telefono_tutor = request.form.get('telefono_tutor')
            student.email_tutor = request.form.get('email_tutor')
            student.grade = request.form.get('grade')
            student.group = request.form.get('group')
            
            db.session.commit()
            flash("Datos del estudiante actualizados.", "success")
            return redirect(url_for('admin.manage_students'))
        except Exception:
            db.session.rollback()
            flash("Error al actualizar datos.", "error")

    return render_template('admin/edit_student.html', student=student)

@admin_bp.route('/students/toggle/<int:id>')
@login_required(permission='MANAGE_STUDENTS')
def toggle_student(id):
    student = Student.query.get_or_404(id)
    student.is_active = not student.is_active
    db.session.commit()
    status = "activado" if student.is_active else "desactivado (borrado lógico)"
    flash(f"Estudiante {status} con éxito.", "success")
    return redirect(url_for('admin.manage_students'))

@admin_bp.route('/assignments', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ASSIGNMENTS')
def manage_assignments():
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        grade = request.form.get('grade')
        group = request.form.get('group')
        
        existing_group = TeacherAssignment.query.filter_by(grade=grade, group=group).first()
        if existing_group and str(existing_group.teacher_id) != str(teacher_id):
            flash(f"El grupo {grade}°{group} ya tiene un profesor asignado ({existing_group.teacher.full_name}).", "error")
            return redirect(url_for('admin.manage_assignments'))

        existing_teacher = TeacherAssignment.query.filter_by(teacher_id=teacher_id).first()
        
        try:
            if existing_teacher:
                existing_teacher.grade = grade
                existing_teacher.group = group
                flash("Asignación actualizada.", "success")
            else:
                new_assignment = TeacherAssignment(teacher_id=teacher_id, grade=grade, group=group)
                db.session.add(new_assignment)
                flash("Asignación creada con éxito.", "success")
            
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Error de integridad: Esta asignación viola las reglas del sistema.", "error")
        except Exception:
            db.session.rollback()
            flash("Ocurrió un error inesperado al guardar la asignación.", "error")
        
    teachers = User.query.filter_by(role='teacher', is_active=True).all()
    assignments = TeacherAssignment.query.all()
    return render_template('admin/assignments.html', teachers=teachers, assignments=assignments)

@admin_bp.route('/subjects', methods=['GET', 'POST'])
@login_required(permission='MANAGE_SUBJECTS')
def manage_subjects():
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    if request.method == 'POST':
        name = request.form.get('name')
        formative_field = request.form.get('formative_field')
        
        new_subject = Subject(name=name, formative_field=formative_field)
        db.session.add(new_subject)
        db.session.commit()
        flash("Materia registrada con éxito.", "success")
            
    subjects = Subject.query.all()
    return render_template('admin/subjects.html', subjects=subjects, fields=formative_fields)

@admin_bp.route('/subjects/edit/<int:id>', methods=['GET', 'POST'])
@login_required(permission='MANAGE_SUBJECTS')
def edit_subject(id):
    subject = Subject.query.get_or_404(id)
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.formative_field = request.form.get('formative_field')
        db.session.commit()
        flash("Materia actualizada.", "success")
        return redirect(url_for('admin.manage_subjects'))
    return render_template('admin/edit_subject.html', subject=subject, fields=formative_fields)

@admin_bp.route('/reports')
@login_required(permission='VIEW_REPORTS')
def list_reports():
    students = Student.query.filter_by(is_active=True).order_by(Student.grade, Student.group).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    return render_template('admin/reports_list.html', students=students)

@admin_bp.route('/reports/view/<int:student_id>')
@login_required(permission='VIEW_REPORTS')
def view_report_card(student_id):
    student = Student.query.get_or_404(student_id)
    periods = Trimester.query.join(SchoolCycle).order_by(Trimester.start_date.desc(), Trimester.id).all()
    grades = Grade.query.filter_by(student_id=student_id).all()
    
    subject_data = {}
    grouped_scores = {}
    
    for g in grades:
        activity = g.activity
        subj = activity.subject
        trimester_id = activity.trimester_id
        
        if trimester_id is None: continue

        if subj.id not in subject_data:
            subject_data[subj.id] = {
                'name': subj.name,
                'field': subj.formative_field,
                'averages': {}
            }
        
        if subj.id not in grouped_scores:
            grouped_scores[subj.id] = {}
        
        if trimester_id not in grouped_scores[subj.id]:
            grouped_scores[subj.id][trimester_id] = []
            
        grouped_scores[subj.id][trimester_id].append(g.score)
        
    for subj_id, periods_scores in grouped_scores.items():
        for t_id, scores in periods_scores.items():
            if scores:
                subject_data[subj_id]['averages'][t_id] = sum(scores) / len(scores)
            else:
                # Si no hay calificaciones para este trimestre, no incluimos la entrada
                pass
            
    field_data = {}
    formative_fields = [
        "Lenguajes",
        "Saberes y pensamiento científico",
        "Ética, naturaleza y sociedades",
        "De lo humano y lo comunitario"
    ]
    
    for field in formative_fields:
        field_data[field] = {'subjects': [], 'averages': {}}
        
    for sid in subject_data:
        data = subject_data[sid]
        field_data[data['field']]['subjects'].append(data)

    for field in field_data:
        subjs = field_data[field]['subjects']
        for period in periods:
            period_scores = [s['averages'][period.id] for s in subjs if period.id in s['averages']]
            if period_scores:
                field_data[field]['averages'][period.id] = sum(period_scores) / len(period_scores)
            
    return render_template('admin/view_report.html', 
                           student=student, 
                           field_data=field_data, 
                           periods=periods,
                           today=datetime.now())
