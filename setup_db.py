# setup_db.py
from app import app
from models import db, Usuario
from werkzeug.security import generate_password_hash

def inicializar_banco():
    with app.app_context():
        # 1. Cria as tabelas
        db.create_all()
        print("Tabelas criadas com sucesso.")
        
        # 2. Cria a Dev (Admin)
        if not Usuario.query.filter_by(username='flavia_dev').first():
            senha_dev = generate_password_hash('senha_secreta')
            dev = Usuario(username='flavia_dev', password=senha_dev, cargo='admin')
            db.session.add(dev)
            print("Usuário 'flavia_dev' (Admin) criado.")

        # 3. Cria a conta do COLCIC
        if not Usuario.query.filter_by(username='colcic').first():
            senha_colcic = generate_password_hash('123456')
            coord = Usuario(username='colcic', password=senha_colcic, cargo='coordenador')
            db.session.add(coord)
            print("Usuário 'colcic' (Coordenador) criado.")

        db.session.commit()
        print("Configuração inicial do banco de dados concluída!")

if __name__ == '__main__':
    inicializar_banco()