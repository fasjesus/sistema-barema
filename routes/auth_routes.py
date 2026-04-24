from flask import Blueprint, render_template, request, redirect, url_for
from flask.views import MethodView
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from core.models import Usuario

auth_bp = Blueprint('auth', __name__)

class LoginView(MethodView):
    def get(self):
        return render_template('login.html')

    def post(self):
        user = request.form.get('username')
        pw = request.form.get('password')
        usuario = Usuario.query.filter_by(username=user).first()

        if usuario and check_password_hash(usuario.password, pw):
            login_user(usuario)
            # Roteamento inteligente baseado no cargo (RBAC)
            if getattr(usuario, 'cargo', '') == 'admin':
                return redirect('/admin') 
            if getattr(usuario, 'cargo', '') == 'coordenador':
                return redirect(url_for('coordenador.painel')) 
        
        return render_template('login.html', erro="Usuário ou senha inválidos.")

class LogoutView(MethodView):
    decorators = [login_required] # Protege a rota usando decorador na classe

    def get(self):
        logout_user()
        return redirect(url_for('auth.login'))

# Registrando as rotas no Blueprint
auth_bp.add_url_rule('/login', view_func=LoginView.as_view('login'))
auth_bp.add_url_rule('/logout', view_func=LogoutView.as_view('logout'))