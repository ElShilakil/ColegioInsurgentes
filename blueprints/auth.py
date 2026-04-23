from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import User
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if session.get('user_role') == 'admin':
        return redirect(url_for('admin.admin_dashboard'))
    return redirect(url_for('teacher.teacher_dashboard'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not re.match(r'^[^@]{5,}@cinsurgentes\.edu\.mx$', email):
            flash("El correo debe tener al menos 5 caracteres antes del dominio @cinsurgentes.edu.mx", "error")
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash("Esta cuenta ha sido desactivada.", "error")
                return redirect(url_for('auth.login'))
            
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            session['user_role'] = user.role
            return redirect(url_for('auth.index'))
        
        flash("Correo o contraseña incorrectos.", "error")
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('auth.login'))
