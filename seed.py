import os
from app import app
from core.models import db, Usuario
from werkzeug.security import generate_password_hash

def semear_dados():
    with app.app_context():
        print("Iniciando a semeadura de dados...")

        # 1. Busca as senhas do arquivo .env (Se não achar, usa uma padrão provisória)
        senha_admin = os.getenv('SENHA_ADMIN_DEV', 'admin_padrao')
        senha_coord = os.getenv('SENHA_COORDENADOR', 'coord_padrao')

        # 2. Cria (Admin)
        if not Usuario.query.filter_by(username='admin_dev').first():
            senha_dev_hash = generate_password_hash(senha_admin)
            dev = Usuario(username='admin_dev', password=senha_dev_hash, cargo='admin')
            db.session.add(dev)
            print("Usuário 'admin_dev' (Admin) preparado.")

        # 3. Cria a conta do COLCIC (Coordenador)
        if not Usuario.query.filter_by(username='colcic').first():
            senha_colcic_hash = generate_password_hash(senha_coord)
            coord = Usuario(username='colcic', password=senha_colcic_hash, cargo='coordenador')
            db.session.add(coord)
            print("Usuário 'colcic' (Coordenador) preparado.")

        db.session.commit()
        print("Semeadura concluída com sucesso!")

if __name__ == '__main__':
    semear_dados()