from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import User, Student, TeacherAssignment, Subject, Grade, SchoolPeriod
from decorators import login_required
from sqlalchemy.exc import IntegrityError
import re
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required(permission='MANAGE_STUDENTS')
def admin_dashboard():
    teacher_count = User.query.filter_by(role='teacher').count()
    student_count = Student.query.filter_by(is_active=True).count()
    active_period = SchoolPeriod.query.filter_by(is_active=True).first()
    return render_template('admin/dashboard.html', 
                           teacher_count=teacher_count, 
                           student_count=student_count, 
                           active_period=active_period)

@admin_bp.route('/periods', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ASSIGNMENTS') 
def manage_periods():
    if request.method == 'POST':
        period_id = request.form.get('period_id')
        name = request.form.get('name')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        is_active = request.form.get('is_active') == 'on'

        if start_date >= end_date:
            flash("La fecha de inicio debe ser anterior a la fecha de fin.", "error")
        else:
            if is_active:
                SchoolPeriod.query.update({SchoolPeriod.is_active: False})
            
            if period_id:
                period = SchoolPeriod.query.get(period_id)
                period.name = name
                period.start_date = start_date
                period.end_date = end_date
                period.is_active = is_active
            else:
                new_period = SchoolPeriod(name=name, start_date=start_date, end_date=end_date, is_active=is_active)
                db.session.add(new_period)
            
            db.session.commit()
            flash("Periodo actualizado con éxito.", "success")

    periods = SchoolPeriod.query.all()
    if not periods:
        p1 = SchoolPeriod(name="Trimestre 1", start_date=datetime(2023, 8, 28).date(), end_date=datetime(2023, 11, 24).date(), is_active=True)
        p2 = SchoolPeriod(name="Trimestre 2", start_date=datetime(2023, 11, 27).date(), end_date=datetime(2024, 3, 8).date(), is_active=False)
        p3 = SchoolPeriod(name="Trimestre 3", start_date=datetime(2024, 3, 11).date(), end_date=datetime(2024, 7, 12).date(), is_active=False)
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        periods = [p1, p2, p3]

    return render_template('admin/periods.html', periods=periods)

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
    periods = SchoolPeriod.query.order_by(SchoolPeriod.start_date).all()
    grades = Grade.query.filter_by(student_id=student_id).all()
    
    subject_data = {}
    grouped_scores = {}
    
    for g in grades:
        activity = g.activity
        subj = activity.subject
        period_id = activity.period_id
        
        if subj.id not in subject_data:
            subject_data[subj.id] = {
                'name': subj.name,
                'field': subj.formative_field,
                'averages': {}
            }
        
        if subj.id not in grouped_scores:
            grouped_scores[subj.id] = {}
        
        if period_id not in grouped_scores[subj.id]:
            grouped_scores[subj.id][period_id] = []
            
        grouped_scores[subj.id][period_id].append(g.score)
        
    for subj_id, periods_scores in grouped_scores.items():
        for period_id, scores in periods_scores.items():
            subject_data[subj_id]['averages'][period_id] = sum(scores) / len(scores) if scores else 0
            
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
