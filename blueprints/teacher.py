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

    active_period = get_current_trimester()
    attendance_summaries = {}
    if active_period:
        for student in students:
            # Resumen de asistencias del trimestre activo
            atts = Attendance.query.filter(
                Attendance.student_id == student.id,
                Attendance.date >= active_period.start_date,
                Attendance.date <= active_period.end_date
            ).all()
            
            summary = {"Asistencia": 0, "Falta": 0, "Retardo": 0, "Falta Justificada": 0}
            for a in atts:
                if a.status in summary:
                    summary[a.status] += 1
            attendance_summaries[student.id] = summary
    
    if request.method == 'POST':
        for student in students:
            # Captura el estado enviado por el radio button
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
        return redirect(url_for('teacher.manage_attendance', date=selected_date))

    # Obtenemos asistencias existentes
    current_att = {a.student_id: a.status for a in Attendance.query.filter_by(date=selected_date).all()}
    selected_date_is_past = selected_date < date.today()
    return render_template('teacher/attendance.html', 
                           students=students, 
                           selected_date=selected_date, 
                           current_att=current_att, 
                           selected_date_is_past=selected_date_is_past,
                           attendance_summaries=attendance_summaries)

@teacher_bp.route('/activities', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ACTIVITIES')
def manage_activities():
    active_period = get_current_trimester()
    if not active_period:
        flash("No hay un periodo escolar marcado como activo. Contacta al administrador.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        name = request.form.get('name')
        type = request.form.get('type')
        date_str = request.form.get('date')
        percentage = float(request.form.get('percentage'))
        activity_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Validación de fechas contra el rango del trimestre activo
        if active_period.start_date and active_period.end_date:
            if activity_date < active_period.start_date or activity_date > active_period.end_date:
                flash(f"La fecha de la actividad está fuera del rango de este trimestre.", "error")
                return redirect(url_for('teacher.manage_activities'))

        # Validación de porcentajes por Materia
        current_sum = db.session.query(db.func.sum(Activity.percentage_value)).filter(
            Activity.subject_id == subject_id,
            Activity.trimester_id == active_period.id,
            Activity.teacher_id == session['user_id']
        ).scalar() or 0.0
        
        available = 100.0 - current_sum
        if percentage > available:
            overage = percentage - available
            flash(f"Error: Solo te queda {available}% disponible en esta materia. Al intentar agregar {percentage}%, te has pasado por {overage}%.", "error")
            return redirect(url_for('teacher.manage_activities'))

        new_activity = Activity(
            teacher_id=session['user_id'],
            subject_id=subject_id,
            trimester_id=active_period.id,
            name=name,
            type=type,
            date=activity_date,
            percentage_value=percentage
        )
        db.session.add(new_activity)
        db.session.commit()
        flash("Actividad creada con éxito.", "success")
        return redirect(url_for('teacher.manage_activities'))
    
    subjects = Subject.query.all()
    activities = Activity.query.filter_by(teacher_id=session['user_id']).order_by(Activity.date.desc()).all()
    return render_template('teacher/activities.html', subjects=subjects, activities=activities, active_period=active_period)

@teacher_bp.route('/gradebook', methods=['GET', 'POST'])
@login_required(permission='MANAGE_GRADES')
def gradebook():
    assignment = TeacherAssignment.query.filter_by(teacher_id=session['user_id']).first()
    if not assignment:
        flash("No tienes un grupo asignado.", "error")
        return redirect(url_for('teacher.teacher_dashboard'))

    periods = Trimester.query.join(SchoolCycle).order_by(SchoolCycle.id.desc(), Trimester.id).all()
    active_period = get_current_trimester()
    
    selected_period_id = request.args.get('period_id', str(active_period.id) if active_period else (str(periods[0].id) if periods else None))
    
    students = Student.query.filter_by(grade=assignment.grade, group=assignment.group, is_active=True).all()
    students = sorted(students, key=lambda x: x.last_name_paternal)

    activities_query = Activity.query.filter_by(teacher_id=session['user_id'])
    if selected_period_id:
        activities_query = activities_query.filter_by(trimester_id=int(selected_period_id))
    
    activities = activities_query.order_by(Activity.subject_id, Activity.date).all()
    
    if request.method == 'POST':
        for student in students:
            for activity in activities:
                score_key = f'score_{student.id}_{activity.id}'
                score_val = request.form.get(score_key)
                
                if score_val:
                    grade_obj = Grade.query.filter_by(student_id=student.id, activity_id=activity.id).first()
                    if grade_obj:
                        grade_obj.score = float(score_val)
                    else:
                        new_grade = Grade(student_id=student.id, activity_id=activity.id, score=float(score_val))
                        db.session.add(new_grade)
        
        db.session.commit()
        flash("Calificaciones guardadas con éxito.", "success")
        return redirect(url_for('teacher.gradebook', period_id=selected_period_id))

    existing_grades = {(g.student_id, g.activity_id): g.score for g in Grade.query.all()}
    
    return render_template('teacher/gradebook.html', 
                           students=students, 
                           activities=activities, 
                           existing_grades=existing_grades,
                           periods=periods,
                           selected_period_id=int(selected_period_id) if selected_period_id else None)
