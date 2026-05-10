from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import Student, TeacherAssignment, Activity, Grade, Attendance, Subject, Trimester, SchoolCycle
from decorators import login_required
from datetime import datetime, date

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def get_current_trimester():
    """Obtiene el trimestre marcado como activo manualmente."""
    return Trimester.query.filter_by(is_active=True).first()

@teacher_bp.route('/dashboard')
@login_required(permission='VIEW_TEACHER_DASHBOARD')
def teacher_dashboard():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado. Contacta al administrador.", "error")
        return render_template('teacher/dashboard.html', assignment=None)
    
    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group, is_active=True).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    
    active_period = get_current_trimester()
    
    # Cálculo de faltas por alumno en el trimestre activo
    absences_by_student = {}
    if active_period:
        for student in students:
            faltas = Attendance.query.filter(
                Attendance.student_id == student.id,
                Attendance.status.in_(["Falta", "Ausente"]),
                Attendance.date >= active_period.start_date,
                Attendance.date <= active_period.end_date
            ).count()
            absences_by_student[student.id] = faltas

    return render_template('teacher/dashboard.html', 
                           assignment=assignment, 
                           students=students, 
                           active_period=active_period,
                           absences_by_student=absences_by_student)

@teacher_bp.route('/attendance', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ATTENDANCE')
def manage_attendance():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group, is_active=True).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)
    
    selected_date_str = request.form.get('date') if request.method == 'POST' else request.args.get('date')
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    else:
        selected_date = date.today()

    # Nueva Lógica: Solo Ciclo Activo
    active_cycle = SchoolCycle.query.filter_by(is_active=True).first()
    if not active_cycle:
        flash("No hay un ciclo escolar activo. Contacta al administrador.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    periods = Trimester.query.filter_by(cycle_id=active_cycle.id).order_by(Trimester.id).all()
    
    selected_trimester_id = request.args.get('trimester_id', type=int)
    
    # Identificar el trimestre objetivo
    target_trimester = None
    if selected_trimester_id:
        target_trimester = db.session.get(Trimester, selected_trimester_id)
    
    # Si no hay selección manual, buscar el activo del ciclo actual
    if not target_trimester:
        target_trimester = Trimester.query.filter_by(cycle_id=active_cycle.id, is_active=True).first()
    
    # Fallback al primero del ciclo si nada es activo
    if not target_trimester and periods:
        target_trimester = periods[0]

    # Lógica de Fecha (Synchronized)
    selected_date_str = request.form.get('date') if request.method == 'POST' else request.args.get('date')
    
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    elif 'trimester_id' in request.args and target_trimester:
        # Si el usuario seleccionó un trimestre explícitamente (click en pill), ir al inicio del periodo
        selected_date = target_trimester.start_date
    else:
        # Acceso inicial o sin parámetros explícitos de filtro, mostrar la fecha actual
        selected_date = date.today()

    attendance_summaries = {}
    if target_trimester:
        for student in students:
            atts = Attendance.query.filter(
                Attendance.student_id == student.id,
                Attendance.date >= target_trimester.start_date,
                Attendance.date <= target_trimester.end_date
            ).all()
            
            summary = {"Asistencia": 0, "Falta": 0, "Retardo": 0, "Falta Justificada": 0}
            for a in atts:
                if a.status in summary:
                    summary[a.status] += 1
            attendance_summaries[student.id] = summary
    
    if request.method == 'POST':
        for student in students:
            status = request.form.get(f'status_{student.id}')
            if status:
                att = Attendance.query.filter_by(student_id=student.id, date=selected_date).first()
                if att:
                    att.status = status
                else:
                    new_att = Attendance(student_id=student.id, date=selected_date, status=status)
                    db.session.add(new_att)
        
        db.session.commit()
        flash(f"Asistencia del {selected_date} guardada con éxito.", "success")
        return redirect(url_for('teacher.manage_attendance', date=selected_date, trimester_id=target_trimester.id if target_trimester else None))

    current_att = {a.student_id: a.status for a in Attendance.query.filter_by(date=selected_date).all()}
    selected_date_is_past = selected_date < date.today()
    
    return render_template('teacher/attendance.html', 
                           students=students, 
                           selected_date=selected_date, 
                           current_att=current_att, 
                           selected_date_is_past=selected_date_is_past,
                           attendance_summaries=attendance_summaries,
                           periods=periods,
                           selected_trimester=target_trimester,
                           selected_trimester_id=target_trimester.id if target_trimester else None)

@teacher_bp.route('/activities', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ACTIVITIES')
def manage_activities():
    # Nueva Lógica: Solo Ciclo Activo
    active_cycle = SchoolCycle.query.filter_by(is_active=True).first()
    if not active_cycle:
        flash("No hay un ciclo escolar activo. Contacta al administrador.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    active_period_system = get_current_trimester() # El marcado globalmente
    
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado. Contacta al administrador.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    if request.method == 'POST':
        # ... (lógica de guardado permanece igual, usa active_period_system si es necesario para validaciones)
        subject_id = request.form.get('subject_id')
        name = request.form.get('name')
        type = request.form.get('type')
        date_str = request.form.get('date')
        percentage = float(request.form.get('percentage'))
        activity_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        if active_period_system and active_period_system.start_date and active_period_system.end_date:
            if activity_date < active_period_system.start_date or activity_date > active_period_system.end_date:
                flash(f"La fecha de la actividad está fuera del rango de este trimestre.", "error")
                return redirect(url_for('teacher.manage_activities'))

        # Regla de Negocio: La suma de porcentajes es por SALÓN (Grado/Grupo)
        current_sum = db.session.query(db.func.sum(Activity.percentage_value)).filter(
            Activity.subject_id == subject_id,
            Activity.trimester_id == active_period_system.id,
            Activity.grade == assignment.grade,
            Activity.group == assignment.group
        ).scalar() or 0.0
        
        available = 100.0 - current_sum
        if percentage > available:
            flash(f"Error: Solo queda {available}% disponible en esta materia para este salón.", "error")
            return redirect(url_for('teacher.manage_activities'))

        new_activity = Activity(
            teacher_id=session['user_id'],
            subject_id=subject_id,
            trimester_id=active_period_system.id,
            grade=assignment.grade,
            group=assignment.group,
            name=name,
            type=type,
            date=activity_date,
            percentage_value=percentage
        )
        db.session.add(new_activity)
        db.session.commit()
        flash("Actividad creada con éxito.", "success")
        return redirect(url_for('teacher.manage_activities'))
    
    # Filtros
    q = request.args.get('q', '').strip()
    subject_filter = request.args.get('subject_filter', '').strip()
    field_filter = request.args.get('field_filter', '').strip()
    
    # Solo periodos del ciclo activo
    periods = Trimester.query.filter_by(cycle_id=active_cycle.id).order_by(Trimester.id).all()
    
    selected_period_id = request.args.get('period_id', type=int)
    if not selected_period_id:
        if active_period_system and active_period_system.cycle_id == active_cycle.id:
            selected_period_id = active_period_system.id
        elif periods:
            selected_period_id = periods[0].id

    query = Activity.query.filter_by(grade=assignment.grade, group=assignment.group)
    
    if q:
        query = query.filter(Activity.name.ilike(f"%{q}%"))
    
    if subject_filter:
        query = query.filter(Activity.subject_id == int(subject_filter))

    if field_filter:
        query = query.join(Subject).filter(Subject.formative_field == field_filter)
        
    if selected_period_id:
        query = query.filter(Activity.trimester_id == selected_period_id)
    else:
        # Si no hay nada, filtrar por el ciclo activo al menos
        query = query.join(Trimester).filter(Trimester.cycle_id == active_cycle.id)
        
    activities = query.order_by(Activity.date.desc()).all()
    subjects = Subject.query.order_by(Subject.name).all()
    
    formative_fields = [f[0] for f in db.session.query(Subject.formative_field).distinct().all()]
    
    return render_template('teacher/activities.html', 
                           subjects=subjects, 
                           activities=activities, 
                           periods=periods,
                           formative_fields=formative_fields,
                           q=q,
                           subject_filter=subject_filter,
                           field_filter=field_filter,
                           selected_period_id=selected_period_id)

@teacher_bp.route('/activities/edit/<int:id>', methods=['POST'])
@login_required(permission='MANAGE_ACTIVITIES')
def edit_activity(id):
    activity = Activity.query.get_or_404(id)
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    
    # Validación por SALÓN: El maestro debe ser el titular del salón de la actividad
    if not assignment or activity.grade != assignment.grade or activity.group != assignment.group:
        flash("No tienes permiso para editar actividades de otros grupos.", "error")
        return redirect(url_for('teacher.manage_activities'))
    
    name = request.form.get('name')
    percentage = float(request.form.get('percentage'))
    
    # Validar porcentaje disponible en el SALÓN
    current_sum = db.session.query(db.func.sum(Activity.percentage_value)).filter(
        Activity.subject_id == activity.subject_id,
        Activity.trimester_id == activity.trimester_id,
        Activity.grade == activity.grade,
        Activity.group == activity.group,
        Activity.id != id
    ).scalar() or 0.0
    
    available = round(100.0 - current_sum, 2)
    if percentage > available:
        flash(f"Error: Solo queda {available}% disponible en esta materia.", "error")
        return redirect(url_for('teacher.manage_activities'))
    
    try:
        activity.name = name
        activity.percentage_value = percentage
        db.session.commit()
        flash("Actividad actualizada.", "success")
    except Exception:
        db.session.rollback()
        flash("Error al actualizar.", "error")
        
    return redirect(url_for('teacher.manage_activities'))

@teacher_bp.route('/activities/delete/<int:id>', methods=['POST'])
@login_required(permission='MANAGE_ACTIVITIES')
def delete_activity(id):
    activity = Activity.query.get_or_404(id)
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()

    # Validación por SALÓN
    if not assignment or activity.grade != assignment.grade or activity.group != assignment.group:
        flash("No tienes permiso para eliminar esta actividad.", "error")
        return redirect(url_for('teacher.manage_activities'))
    
    try:
        Grade.query.filter_by(activity_id=id).delete()
        db.session.delete(activity)
        db.session.commit()
        flash("Actividad eliminada con éxito.", "success")
    except Exception:
        db.session.rollback()
        flash("Error al eliminar.", "error")
        
    return redirect(url_for('teacher.manage_activities'))

@teacher_bp.route('/gradebook', methods=['GET', 'POST'])
@login_required(permission='MANAGE_GRADES')
def gradebook():
    active_cycle = SchoolCycle.query.filter_by(is_active=True).first()
    if not active_cycle:
        flash("No hay un ciclo escolar activo.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    # Filtros
    q = request.args.get('q', '').strip()
    subject_filter = request.args.get('subject_filter', '').strip()
    field_filter = request.args.get('field_filter', '').strip()

    active_period_system = get_current_trimester()
    periods = Trimester.query.filter_by(cycle_id=active_cycle.id).order_by(Trimester.id).all()
    
    selected_period_id = request.args.get('period_id', type=int)
    if not selected_period_id:
        if active_period_system and active_period_system.cycle_id == active_cycle.id:
            selected_period_id = active_period_system.id
        elif periods:
            selected_period_id = periods[0].id
    
    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group, is_active=True).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)

    activities_query = Activity.query.filter_by(grade=assignment.grade, group=assignment.group)
    
    if selected_period_id:
        activities_query = activities_query.filter_by(trimester_id=selected_period_id)
    else:
        activities_query = activities_query.join(Trimester).filter(Trimester.cycle_id == active_cycle.id)
    
    if q:
        activities_query = activities_query.filter(Activity.name.ilike(f"%{q}%"))
    if subject_filter:
        activities_query = activities_query.filter(Activity.subject_id == int(subject_filter))
    if field_filter:
        activities_query = activities_query.join(Subject).filter(Subject.formative_field == field_filter)
    
    activities = activities_query.order_by(Activity.subject_id, Activity.date).all()
    
    if request.method == 'POST':
        for student in students:
            for activity in activities:
                score_key = f'score_{student.id}_{activity.id}'
                score_val = request.form.get(score_key)
                grade_obj = Grade.query.filter_by(student_id=student.id, activity_id=activity.id).first()
                if score_val and score_val.strip() != "":
                    if grade_obj: grade_obj.score = float(score_val)
                    else: db.session.add(Grade(student_id=student.id, activity_id=activity.id, score=float(score_val)))
                elif grade_obj:
                    db.session.delete(grade_obj)
        db.session.commit()
        flash("Calificaciones actualizadas.", "success")
        return redirect(url_for('teacher.gradebook', period_id=selected_period_id, q=q, subject_filter=subject_filter, field_filter=field_filter))

    existing_grades = {(g.student_id, g.activity_id): g.score for g in Grade.query.all()}
    subjects = Subject.query.order_by(Subject.name).all()
    formative_fields = [f[0] for f in db.session.query(Subject.formative_field).distinct().all()]
    
    return render_template('teacher/gradebook.html', 
                           students=students, 
                           activities=activities, 
                           existing_grades=existing_grades,
                           periods=periods,
                           subjects=subjects,
                           formative_fields=formative_fields,
                           q=q,
                           subject_filter=subject_filter,
                           field_filter=field_filter,
                           selected_period_id=selected_period_id)
