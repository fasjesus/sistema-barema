# app.py - Configuração Principal do Flask
import os
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from core.models import db, Usuario, AnaliseBarema
from core.repository import UsuarioRepository
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

@login_manager.user_loader
def load_user(user_id):
    return UsuarioRepository().buscar_por_id(user_id)

# 4. Flask-Admin (Protegido)
class ViewProtegida(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.eh_admin()
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
