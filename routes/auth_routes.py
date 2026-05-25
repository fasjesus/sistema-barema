from flask import Blueprint, current_app, make_response, render_template, request, redirect, session, url_for
from flask.views import MethodView
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from core.entities import CargoUsuario
from core.repository import UsuarioRepository
from core.security import get_client_ip, login_attempt_limiter

auth_bp = Blueprint('auth', __name__)
usuario_repository = UsuarioRepository()

def _login_attempt_key(username):
    normalized_user = (username or "").strip().lower() or "usuario-desconhecido"
    client_ip = get_client_ip(request, current_app.config.get('TRUST_PROXY_HEADERS', False))
    return f"{client_ip}:{normalized_user}"

def _blocked_login_response(retry_after, username=""):
    if username:
        session['blocked_login_username'] = username

    if retry_after >= 60:
        tempo = "1 minuto"
    else:
        tempo = f"{retry_after} segundos"

    response = make_response(
        render_template(
            'login.html',
            erro=f"Muitas tentativas de login. Aguarde {tempo} para tentar novamente.",
            login_bloqueado=True,
            retry_after=retry_after,
            username=username or "",
        ),
        429,
    )
    response.headers["Retry-After"] = str(retry_after)
    return response

class LoginView(MethodView):
    def get(self):
        blocked_username = session.get('blocked_login_username', '')
        if blocked_username:
            blocked = login_attempt_limiter.is_blocked(_login_attempt_key(blocked_username))
            if blocked.blocked:
                return render_template(
                    'login.html',
                    erro="Muitas tentativas de login. Aguarde para tentar novamente.",
                    login_bloqueado=True,
                    retry_after=blocked.retry_after,
                    username=blocked_username,
                )
            session.pop('blocked_login_username', None)

        return render_template('login.html')

    def post(self):
        user = request.form.get('username')
        pw = request.form.get('password')
        attempt_key = _login_attempt_key(user)
        blocked = login_attempt_limiter.is_blocked(attempt_key)
        if blocked.blocked:
            return _blocked_login_response(blocked.retry_after, user)

        usuario = usuario_repository.buscar_por_username(user)

        if usuario and check_password_hash(usuario.password, pw):
            login_attempt_limiter.reset(attempt_key)
            session.pop('blocked_login_username', None)
            login_user(usuario)
            # Roteamento inteligente baseado no cargo (RBAC)
            if usuario.cargo == CargoUsuario.ADMIN:
                return redirect('/admin') 
            if usuario.cargo == CargoUsuario.COORDENADOR:
                return redirect(url_for('coordenador.painel')) 

        blocked = login_attempt_limiter.register_failure(
            attempt_key,
            current_app.config['LOGIN_MAX_ATTEMPTS'],
            current_app.config['LOGIN_BLOCK_SECONDS'],
        )
        if blocked.blocked:
            return _blocked_login_response(blocked.retry_after, user)

        return render_template('login.html', erro="Usuário ou senha inválidos.", username=user or "")

class LogoutView(MethodView):
    decorators = [login_required] # Protege a rota usando decorador na classe

    def get(self):
        logout_user()
        return redirect(url_for('auth.login'))

# Registrando as rotas no Blueprint
auth_bp.add_url_rule('/login', view_func=LoginView.as_view('login'))
auth_bp.add_url_rule('/logout', view_func=LogoutView.as_view('logout'))
