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
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or len(username) < 3:
            flash("El nombre de usuario debe tener al menos 3 caracteres.", "error")
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash("Esta cuenta ha sido desactivada.", "error")
                return redirect(url_for('auth.login'))
            
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            session['user_role'] = user.role
            return redirect(url_for('auth.index'))
        
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('auth.login'))
