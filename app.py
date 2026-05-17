# app.py - Configuração Principal do Flask
import os
from flask import Flask, make_response, redirect, request, url_for
from dotenv import load_dotenv
from core.models import db, Usuario, AnaliseBarema
from core.security import get_client_ip, request_rate_limiter
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, current_user
from flask_migrate import Migrate  

# 1. Configurações Iniciais do Flask
load_dotenv()

def config_int(nome, padrao):
    try:
        return int(os.getenv(nome, padrao))
    except (TypeError, ValueError):
        return padrao

def config_bool(nome, padrao=False):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on", "sim"}

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave-padrao')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['RATE_LIMIT_REQUESTS'] = config_int('RATE_LIMIT_REQUESTS', 120)
app.config['RATE_LIMIT_WINDOW_SECONDS'] = config_int('RATE_LIMIT_WINDOW_SECONDS', 60)
app.config['LOGIN_MAX_ATTEMPTS'] = config_int('LOGIN_MAX_ATTEMPTS', 3)
app.config['LOGIN_BLOCK_SECONDS'] = config_int('LOGIN_BLOCK_SECONDS', 60)
app.config['TRUST_PROXY_HEADERS'] = config_bool('TRUST_PROXY_HEADERS')

# 2. Flask-SQLAlchemy e Flask-Migrate
db.init_app(app)
migrate = Migrate(app, db) 

# 3. Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' 

@app.before_request
def limitar_requisicoes_por_ip():
    client_ip = get_client_ip(request, app.config['TRUST_PROXY_HEADERS'])
    result = request_rate_limiter.hit(
        f"request:{client_ip}",
        app.config['RATE_LIMIT_REQUESTS'],
        app.config['RATE_LIMIT_WINDOW_SECONDS'],
    )
    if result.allowed:
        return None

    response = make_response("Muitas requisicoes. Tente novamente em alguns segundos.", 429)
    response.headers["Retry-After"] = str(result.retry_after)
    return response

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# 4. Flask-Admin (Protegido)
class ViewProtegida(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, 'cargo', '') == 'admin'
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login'))

admin = Admin(app, name='Bastidores - Dev')
admin.add_view(ViewProtegida(AnaliseBarema, db.session, name='Banco: Solicitações'))
admin.add_view(ViewProtegida(Usuario, db.session, name='Banco: Usuários'))

# 5. REGISTRAR AS RÉGUAS DE TOMADAS (BLUEPRINTS)
from routes.aluno_routes import aluno_bp
from routes.auth_routes import auth_bp
from routes.coordenador_routes import coordenador_bp

app.register_blueprint(aluno_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(coordenador_bp)

# 6. Rodar o App
if __name__ == '__main__':
    app.run(debug=True)
