# app.py - Configuração Principal do Flask
import os
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from core.models import db, Usuario, AnaliseBarema
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, current_user
from flask_migrate import Migrate  

# 1. Configurações Iniciais do Flask
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave-padrao')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 2. Flask-SQLAlchemy e Flask-Migrate
db.init_app(app)
migrate = Migrate(app, db) 

# 3. Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' 

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
