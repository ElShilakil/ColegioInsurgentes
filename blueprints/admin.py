from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import User, Student, TeacherAssignment, Subject, Grade, Trimester, SchoolCycle, Activity
from decorators import login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, cast, String
import re
from datetime import datetime, date

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required(permission='MANAGE_STUDENTS')
def admin_dashboard():
    teacher_count = User.query.filter_by(role='teacher', is_active=True).count()
    student_count = Student.query.filter_by(is_active=True).count()
    subject_count = Subject.query.count()
    assignment_count = TeacherAssignment.query.count()
    cycle_count = SchoolCycle.query.count()
    active_period = Trimester.query.filter_by(is_active=True).first()
    return render_template('admin/dashboard.html', 
                           teacher_count=teacher_count, 
                           student_count=student_count,
                           subject_count=subject_count,
                           assignment_count=assignment_count,
                           cycle_count=cycle_count,
                           active_period=active_period)

def get_next_cycle_info():
    """Calcula el nombre y fechas sugeridas para el siguiente ciclo escolar."""
    last_cycle = SchoolCycle.query.order_by(SchoolCycle.id.desc()).first()
    if not last_cycle:
        return "2025-2026", 2025, 2026

    # Intentar extraer años del nombre (formato YYYY-YYYY)
    match = re.search(r'(\d{4})-(\d{4})', last_cycle.name)
    if match:
        start_year = int(match.group(1)) + 1
        end_year = int(match.group(2)) + 1
        return f"{start_year}-{end_year}", start_year, end_year
    
    # Fallback si el nombre no tiene el formato esperado
    return "Nuevo Ciclo", date.today().year, date.today().year + 1

@admin_bp.route('/periods', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ASSIGNMENTS') 
def manage_periods():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'edit_trimester_dates':
            trimester_id = request.form.get('trimester_id')
            new_start = date.fromisoformat(request.form.get('start_date'))
            new_end = date.fromisoformat(request.form.get('end_date'))
            
            if new_end <= new_start:
                flash("Error: La fecha de fin debe ser posterior a la de inicio.", "error")
                return redirect(url_for('admin.manage_periods'))

            t = db.session.get(Trimester, trimester_id)
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
                selected_t = db.session.get(Trimester, trimester_id)
                
                # Desactivar todos los trimestres de TODOS los ciclos para asegurar unicidad
                Trimester.query.update({Trimester.is_active: False})
                selected_t.is_active = True
                
                # Sincronizar ciclo activo
                SchoolCycle.query.update({SchoolCycle.is_active: False})
                selected_t.cycle.is_active = True
                
                db.session.commit()
                flash(f"{selected_t.name} del ciclo {selected_t.cycle.name} activado como periodo actual del sistema.", "success")

        return redirect(url_for('admin.manage_periods'))

    active_cycle = SchoolCycle.query.filter_by(is_active=True).first()
    last_t3 = None
    if active_cycle:
        last_t3 = Trimester.query.filter_by(cycle_id=active_cycle.id).order_by(Trimester.id.desc()).first()
    
    can_start_next = True
    if last_t3 and last_t3.end_date and date.today() < last_t3.end_date:
        can_start_next = False

    next_name, _, _ = get_next_cycle_info()
    
    return render_template('admin/periods.html', 
                           active_cycle=active_cycle,
                           can_start_next=can_start_next, 
                           next_name=next_name,
                           last_t3=last_t3)

@admin_bp.route('/cycles/next', methods=['POST'])
@login_required(permission='MANAGE_ASSIGNMENTS')
def start_next_cycle():
    active_cycle = SchoolCycle.query.filter_by(is_active=True).first()
    
    # 1. Validación de Conclusión
    if active_cycle:
        t3 = Trimester.query.filter_by(cycle_id=active_cycle.id).order_by(Trimester.id.desc()).first()
        if t3 and t3.end_date and date.today() < t3.end_date:
            flash(f"El ciclo {active_cycle.name} aún no ha terminado (Finaliza el {t3.end_date.strftime('%d/%m/%Y')}).", "error")
            return redirect(url_for('admin.manage_periods'))

    # 2. Cálculo Lógico del Nombre y Proyección de Fechas
    next_name, start_yr, end_year = get_next_cycle_info()
    
    # 3. Creación y Activación del Nuevo Ciclo
    if active_cycle:
        active_cycle.is_active = False
        # Desactivar todos los trimestres del ciclo pasado
        Trimester.query.filter_by(cycle_id=active_cycle.id).update({Trimester.is_active: False})

    new_cycle = SchoolCycle(name=next_name, is_active=True)
    db.session.add(new_cycle)
    db.session.flush()

    # 4. Generación Automática de Trimestres Default
    trimesters_config = [
        (f"Trimestre 1 ({next_name})", date(start_yr, 8, 25), date(start_yr, 11, 21), True),
        (f"Trimestre 2 ({next_name})", date(start_yr, 11, 24), date(end_year, 3, 20), False),
        (f"Trimestre 3 ({next_name})", date(end_year, 3, 23), date(end_year, 7, 10), False),
    ]

    for t_name, start, end, active in trimesters_config:
        new_t = Trimester(
            cycle_id=new_cycle.id,
            name=t_name,
            start_date=start,
            end_date=end,
            is_active=active
        )
        db.session.add(new_t)

    # 5. Lógica de Promoción de Alumnos (Masiva - ORDEN CORREGIDO)
    
    # A) GRADUAR PRIMERO: Alumnos que YA están en 6to pasan a 'Egresado' e Inactivos
    # Al quedar como is_active=False, se retiran de las vistas operativas del administrador y docente.
    Student.query.filter(Student.status == 'Activo', Student.grade == 6).update(
        {Student.status: 'Egresado', Student.is_active: False}, synchronize_session=False
    )
    
    # B) PROMOVER DESPUÉS: Alumnos de 1ro a 5to suben un grado
    # Al haber graduado ya a los de 6to, esta consulta solo afectará a los que realmente suben.
    Student.query.filter(Student.status == 'Activo', Student.grade < 6).update(
        {Student.grade: Student.grade + 1}, synchronize_session=False
    )

    # 6. Reinicio de Maestros (Limpieza masiva)
    TeacherAssignment.query.delete()

    try:
        db.session.commit()
        flash(f"¡Ciclo {next_name} iniciado con éxito! Los alumnos han sido promovidos y las asignaciones de maestros se han reiniciado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al iniciar el nuevo ciclo: {str(e)}", "error")

    return redirect(url_for('admin.manage_periods'))

@admin_bp.route('/teachers', methods=['GET', 'POST'])
@login_required(permission='MANAGE_TEACHERS')
def manage_teachers():
    if request.method == 'POST':
        # ... (lógica de guardado permanece igual)
        first_name = request.form.get('first_name')
        last_name_paternal = request.form.get('last_name_paternal')
        last_name_maternal = request.form.get('last_name_maternal')
        username = request.form.get('username')
        password = request.form.get('password')
        
        name_regex = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$'
        password_regex = r'^(?=.*[A-Z])(?=.*\d).{8,}$'

        if not re.match(name_regex, first_name) or not re.match(name_regex, last_name_paternal) or (last_name_maternal and not re.match(name_regex, last_name_maternal)):
            flash("Los nombres y apellidos deben contener solo letras.", "error")
        elif not username or len(username) < 3:
            flash("El usuario debe tener al menos 3 caracteres.", "error")
        elif not re.match(password_regex, password):
            flash("La contraseña debe tener al menos 8 caracteres, incluir una mayúscula y un número.", "error")
        elif User.query.filter_by(username=username).first():
            flash("El nombre de usuario ya está registrado.", "error")
        else:
            try:
                new_teacher = User(
                    first_name=first_name, 
                    last_name_paternal=last_name_paternal, 
                    last_name_maternal=last_name_maternal,
                    username=username, 
                    role='teacher'
                )
                new_teacher.set_password(password)
                db.session.add(new_teacher)
                db.session.commit()
                flash("Profesor registrado con éxito.", "success")
            except Exception:
                db.session.rollback()
                flash("Error al registrar el profesor.", "error")
    
    # Filtros para Maestros
    q = request.args.get('q', '').strip()
    query = User.query.filter_by(role='teacher')

    if q:
        search = f"%{q}%"
        query = query.filter(or_(
            User.first_name.ilike(search),
            User.last_name_paternal.ilike(search),
            User.last_name_maternal.ilike(search),
            User.username.ilike(search)
        ))

    teachers = query.order_by(User.last_name_paternal).all()
    return render_template('admin/teachers.html', 
                           teachers=teachers, 
                           q=q)

@admin_bp.route('/teachers/toggle/<int:id>')
@login_required(permission='MANAGE_TEACHERS')
def toggle_teacher(id):
    teacher = User.query.get_or_404(id)
    if teacher.is_active:
        if teacher.assignment:
            db.session.delete(teacher.assignment)
        teacher.is_active = False
        status = "desactivado y se ha liberado su grupo"
    else:
        teacher.is_active = True
        status = "activado"
    
    db.session.commit()
    flash(f"Profesor {status} con éxito.", "success")
    return redirect(url_for('admin.manage_teachers'))

@admin_bp.route('/teachers/edit/<int:id>', methods=['GET', 'POST'])
@login_required(permission='MANAGE_TEACHERS')
def edit_teacher(id):
    teacher = User.query.get_or_404(id)
    if request.method == 'POST':
        username = request.form.get('username')
        if not username or len(username) < 3:
            flash("El usuario debe tener al menos 3 caracteres.", "error")
            return redirect(url_for('admin.edit_teacher', id=id))
        
        if username != teacher.username and User.query.filter_by(username=username).first():
            flash("Ese usuario ya está en uso.", "error")
            return redirect(url_for('admin.edit_teacher', id=id))

        try:
            teacher.first_name = request.form.get('first_name')
            teacher.last_name_paternal = request.form.get('last_name_paternal')
            teacher.last_name_maternal = request.form.get('last_name_maternal')
            teacher.username = username
            
            new_password = request.form.get('password')
            if new_password:
                if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$', new_password):
                    flash("La nueva contraseña debe contener mayúsculas, minúsculas y números.", "error")
                    return redirect(url_for('admin.edit_teacher', id=id))
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
        # ... (lógica de guardado permanece igual)
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
            
    # Filtros para Alumnos
    q = request.args.get('q', '').strip()
    group_filter = request.args.get('group', '').strip()
    
    query = Student.query

    if q:
        search = f"%{q}%"
        query = query.filter(or_(
            Student.first_name.ilike(search),
            Student.last_name_paternal.ilike(search),
            Student.last_name_maternal.ilike(search),
            Student.curp.ilike(search)
        ))

    if group_filter:
        if '-' in group_filter:
            try:
                g_grade, g_group = group_filter.split('-')
                query = query.filter(Student.grade == g_grade, Student.group == g_group.upper())
            except ValueError: pass
        else:
            query = query.filter(or_(
                cast(Student.grade, String).ilike(f"%{group_filter}%"),
                Student.group.ilike(f"%{group_filter}%")
            ))

    # Obtener grupos disponibles para el selector (incluyendo inactivos para que no se pierdan filtros)
    available_groups = db.session.query(Student.grade, Student.group).\
        distinct().\
        order_by(Student.grade, Student.group).all()

    # Ordenamos: Activos primero (is_active desc), luego por grado, grupo y nombre
    students = query.order_by(Student.is_active.desc(), Student.grade, Student.group, Student.last_name_paternal).all()
    return render_template('admin/students.html', 
                           students=students, 
                           q=q, 
                           group_filter=group_filter,
                           available_groups=available_groups)

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
    status = "activado" if student.is_active else "deshabilitado"
    flash(f"Estudiante {status} con éxito.", "success")
    return redirect(url_for('admin.manage_students'))

@admin_bp.route('/assignments', methods=['GET', 'POST'])
@login_required(permission='MANAGE_ASSIGNMENTS')
def manage_assignments():
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        grade = request.form.get('grade')
        group = request.form.get('group')
        
        # Buscar si ya existe una asignación para este GRUPO (Grado y Grupo)
        existing_assignment = TeacherAssignment.query.filter_by(grade=grade, group=group).first()
        
        # Buscar si el profesor ya tiene otra asignación (porque teacher_id es unique)
        other_teacher_assignment = TeacherAssignment.query.filter_by(teacher_id=teacher_id).first()
        
        try:
            if existing_assignment:
                # Si el profesor ya tenía otro grupo asignado, borramos esa asignación vieja
                # para liberar al profesor y permitir que tome este grupo.
                if other_teacher_assignment and other_teacher_assignment.id != existing_assignment.id:
                    db.session.delete(other_teacher_assignment)
                    db.session.flush()
                
                # Actualizamos el profesor en la asignación existente del grupo.
                # Esto preserva el ID de la asignación y sus actividades vinculadas.
                existing_assignment.teacher_id = teacher_id
                flash(f"Grupo {grade}°{group} actualizado con el nuevo profesor. Actividades preservadas.", "success")
            else:
                # Si el grupo no existía, pero el profesor sí tenía otro grupo
                if other_teacher_assignment:
                    db.session.delete(other_teacher_assignment)
                    db.session.flush()
                
                # Creamos una nueva asignación para este grupo
                new_assignment = TeacherAssignment(teacher_id=teacher_id, grade=grade, group=group)
                db.session.add(new_assignment)
                flash("Nueva asignación creada con éxito.", "success")
            
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Error de integridad: Esta asignación viola las reglas del sistema.", "error")
        except Exception:
            db.session.rollback()
            flash("Ocurrió un error inesperado al guardar la asignación.", "error")
        
    # Filtros para Asignaciones
    q = request.args.get('q', '').strip()

    query = TeacherAssignment.query.join(User)

    if q:
        search = f"%{q}%"
        query = query.filter(or_(
            User.first_name.ilike(search),
            User.last_name_paternal.ilike(search),
            User.last_name_maternal.ilike(search),
            User.username.ilike(search)
        ))

    # Profesores disponibles (activos y sin grupo asignado)
    assigned_teacher_ids = [a.teacher_id for a in TeacherAssignment.query.filter(TeacherAssignment.teacher_id.isnot(None)).all()]
    available_teachers = User.query.filter(
        User.role == 'teacher',
        User.is_active == True,
        ~User.id.in_(assigned_teacher_ids)
    ).all()

    # Grupos asignados actualmente (que tienen profesor)
    assigned_groups = [(a.grade, a.group) for a in TeacherAssignment.query.filter(TeacherAssignment.teacher_id.isnot(None)).all()]

    # Grupos reales (basados en alumnos activos)
    all_real_groups = db.session.query(Student.grade, Student.group).\
        filter_by(is_active=True).distinct().\
        order_by(Student.grade, Student.group).all()
    
    # Filtrar grupos que NO tienen profesor asignado
    unassigned_groups = [g for g in all_real_groups if (g.grade, g.group) not in assigned_groups]

    # Organizar grupos por grado para el frontend
    available_by_grade = {}
    for g in unassigned_groups:
        if g.grade not in available_by_grade:
            available_by_grade[g.grade] = []
        available_by_grade[g.grade].append(g.group)

    assignments = query.order_by(TeacherAssignment.grade, TeacherAssignment.group).all()

    return render_template('admin/assignments.html', 
                           teachers=available_teachers, 
                           assignments=assignments,
                           q=q,
                           available_by_grade=available_by_grade)

@admin_bp.route('/assignments/delete/<int:id>')
@login_required(permission='MANAGE_ASSIGNMENTS')
def delete_assignment(id):
    assignment = TeacherAssignment.query.get_or_404(id)
    if assignment.teacher:
        teacher_name = assignment.teacher.full_name
        assignment.teacher_id = None
        db.session.commit()
        flash(f"Se ha desvinculado al profesor {teacher_name} del grupo con éxito. El historial del grupo se ha conservado.", "success")
    else:
        # Si ya no tenía maestro, pero el registro existe (grupo vacío con historia), 
        # aquí podríamos decidir si borrarlo físicamente si no tiene actividades.
        if not assignment.activities:
            db.session.delete(assignment)
            db.session.commit()
            flash("Grupo vacío eliminado correctamente.", "success")
        else:
            flash("Este grupo está vacante pero conserva historial académico.", "info")
            
    return redirect(url_for('admin.manage_assignments'))

@admin_bp.route('/subjects')
@login_required(permission='MANAGE_SUBJECTS')
def manage_subjects():
    subjects = Subject.query.order_by(Subject.formative_field, Subject.name).all()
    return render_template('admin/subjects.html', subjects=subjects)

@admin_bp.route('/reports')
@login_required(permission='VIEW_REPORTS')
def list_reports():
    # Obtener parámetros de búsqueda
    search_query = request.args.get('q', '').strip()
    group_filter = request.args.get('group', '').strip()

    # Consulta base: Estudiantes activos
    query = Student.query.filter_by(is_active=True)

    # Filtrar por nombre o apellidos si hay búsqueda
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(or_(
            Student.first_name.ilike(search_pattern),
            Student.last_name_paternal.ilike(search_pattern),
            Student.last_name_maternal.ilike(search_pattern),
            Student.curp.ilike(search_pattern)
        ))

    # Filtrar por Grado-Grupo si está seleccionado
    if group_filter:
        try:
            grade, group = group_filter.split('-')
            query = query.filter(Student.grade == grade, Student.group == group)
        except ValueError:
            pass

    # Obtener todos los alumnos filtrados, ordenados por grado, grupo y nombre
    students = query.order_by(Student.grade, Student.group, Student.last_name_paternal).all()
    
    # Obtener grupos disponibles para el selector (dinámico)
    available_groups = db.session.query(Student.grade, Student.group).\
        filter_by(is_active=True).distinct().\
        order_by(Student.grade, Student.group).all()
    
    return render_template('admin/reports_list.html', 
                           students=students, 
                           available_groups=available_groups,
                           search_query=search_query,
                           group_filter=group_filter)

@admin_bp.route('/reports/view/<int:student_id>')
@login_required(permission='VIEW_REPORTS')
def view_report_card(student_id):
    student = Student.query.get_or_404(student_id)
    
    # 1. Identificar el Ciclo Escolar Activo
    active_cycle = SchoolCycle.query.filter_by(is_active=True).first()
    if not active_cycle:
        flash("No hay un ciclo escolar activo para generar boletas.", "error")
        return redirect(url_for('admin.list_reports'))

    # 2. Obtener SOLO los trimestres del ciclo activo
    periods = Trimester.query.filter_by(cycle_id=active_cycle.id).order_by(Trimester.id).all()
    period_ids = [p.id for p in periods]

    # 3. Obtener calificaciones del alumno vinculadas SOLO a esos trimestres
    grades = Grade.query.join(Activity).filter(
        Grade.student_id == student_id,
        Activity.trimester_id.in_(period_ids)
    ).all()
    
    subject_data = {}
    grouped_scores = {}
    
    for g in grades:
        activity = g.activity
        subj = activity.subject
        trimester_id = activity.trimester_id
        
        if trimester_id not in period_ids: continue # Doble validación de seguridad

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
            
        grouped_scores[subj.id][trimester_id].append({
            'score': g.score,
            'weight': activity.percentage_value
        })
        
    for subj_id, periods_scores in grouped_scores.items():
        for t_id, scores_data in periods_scores.items():
            if scores_data:
                total_weighted_score = sum(s['score'] * (s['weight'] / 100.0) for s in scores_data)
                total_weight_percentage = sum(s['weight'] for s in scores_data)
                
                if total_weight_percentage > 0:
                    subject_data[subj_id]['averages'][t_id] = (total_weighted_score / (total_weight_percentage / 100.0))
                else:
                    subject_data[subj_id]['averages'][t_id] = 0
            
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
                           active_cycle=active_cycle,
                           today=datetime.now())
