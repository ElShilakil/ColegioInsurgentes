from functools import wraps
from flask import session, flash, redirect, url_for
from models import User

PERMISSIONS = {
    'admin': [
        'MANAGE_TEACHERS',
        'MANAGE_STUDENTS',
        'MANAGE_ASSIGNMENTS',
        'MANAGE_SUBJECTS',
        'VIEW_REPORTS',
        'VIEW_TEACHER_DASHBOARD',
        'MANAGE_ATTENDANCE',
        'MANAGE_ACTIVITIES',
        'MANAGE_GRADES'
    ],
    'teacher': [
        'VIEW_TEACHER_DASHBOARD',
        'MANAGE_ATTENDANCE',
        'MANAGE_ACTIVITIES',
        'MANAGE_GRADES'
    ]
}

def login_required(permission=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Por favor, inicia sesión para acceder.", "error")
                return redirect(url_for('auth.login'))
            
            user = User.query.get(session['user_id'])
            if not user or not user.is_active:
                session.clear()
                flash("Sesión inválida o cuenta desactivada.", "error")
                return redirect(url_for('auth.login'))

            if permission:
                role_permissions = PERMISSIONS.get(user.role, [])
                if permission not in role_permissions:
                    flash("No tienes permiso para acceder a esta sección.", "error")
                    return redirect(url_for('auth.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
