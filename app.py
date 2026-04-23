import os
import uuid
import traceback
from datetime import datetime, date
from flask import Flask, request, render_template, send_file, jsonify, redirect, url_for
from models import db, Usuario, AnaliseBarema
from werkzeug.security import check_password_hash

# Imports do Admin e Login
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'chave-padrao')

# --- CONFIGURAÇÃO DO SQLALCHEMY ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# Importações das entidades e serviços
from core.entities import Estudante, ProcessoBarema, ItemBarema
from core.repository import BaremaRepository
from core.services import PDFService, CertificateProcessor

# ==========================================
# 1. CONFIGURAÇÃO DO FLASK-LOGIN (O Segurança)
# ==========================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ==========================================
# 2. CONFIGURAÇÃO DO FLASK-ADMIN (Os Bastidores)
# ==========================================
class ViewProtegida(ModelView):
    def is_accessible(self):
        # login dev
        return current_user.is_authenticated and getattr(current_user, 'cargo', '') == 'admin'

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

admin = Admin(app, name='Bastidores - Dev')
admin.add_view(ViewProtegida(AnaliseBarema, db.session, name='Banco: Solicitações'))
admin.add_view(ViewProtegida(Usuario, db.session, name='Banco: Usuários'))


# --- CONFIGURAÇÕES DE PASTAS ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
repo = BaremaRepository(BASE_DIR)
cert_processor = CertificateProcessor()
pdf_service = PDFService(
    logo_uesc=os.path.join(BASE_DIR, 'static', 'images', 'logo_uesc.png'),
    logo_colcic=os.path.join(BASE_DIR, 'static', 'images', 'logo_computacao.png')
)

# ==========================================
# ROTAS PÚBLICAS (ALUNO)
# ==========================================

@app.route('/')
def home():
    atividades = repo.load_atividades('antigo')
    return render_template('index.html', data_hoje=date.today().strftime("%d/%m/%Y"), atividades=atividades)

@app.route('/get_barema_data/<tipo>')
def get_barema_data(tipo):
    return jsonify(repo.load_atividades(tipo))

@app.route('/barema', methods=['POST'])
def barema_process():
    try:
        aluno = Estudante(nome=request.form.get('nome',''), matricula=request.form.get('matricula',''), email=request.form.get('email',''))
        tipo = request.form.get('barema_tipo', 'antigo')
        processo = ProcessoBarema(estudante=aluno, tipo_barema=tipo, data_envio=request.form.get('data_verificacao',''))

        atividades_base = repo.load_atividades(tipo)
        certificados = []
        pag_atual = 2

        for ativ in atividades_base:
            id_at = ativ['id'] 
            horas_raw = request.form.get(f"horas_{id_at}", "")
            files = request.files.getlist(f"certificado_{id_at}")
            intervalos = []
            
            for f in files:
                if f and f.filename != '':
                    prox, inter = cert_processor.get_page_info(pag_atual, f)
                    intervalos.append(inter)
                    certificados.append(f)
                    pag_atual = prox

            item = ItemBarema(
                atividade=repo.to_entity(ativ),
                horas_input=str(horas_raw), 
                tipo_barema=tipo,
                intervalo_paginas=", ".join(intervalos)
            )
            processo.adicionar_item(item)

        pdf = pdf_service.gerar_completo(processo, certificados)
        return send_file(pdf, as_attachment=True, download_name=f"barema_{aluno.matricula}.pdf")

    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Erro interno"}), 500

@app.route('/solicitar-analise', methods=['POST'])
def solicitar_analise():
    try:
        nome = request.form.get('nome')
        matricula = request.form.get('matricula')
        email = request.form.get('email')
        barema_tipo = request.form.get('barema_tipo', 'antigo')
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        aluno = Estudante(nome=nome, matricula=matricula, email=email)
        processo = ProcessoBarema(estudante=aluno, tipo_barema=barema_tipo, data_envio=data_hoje)

        pag_atual = 2
        atividades_base = repo.load_atividades(barema_tipo)
        certificados_para_anexar = [] 
        
        for ativ_dict in atividades_base:
            ativ_objeto = repo.to_entity(ativ_dict)
            id_at = ativ_objeto.id 
            horas = request.form.get(f'horas_{id_at}')
            
            if horas and horas.strip():
                files = request.files.getlist(f'certificado_{id_at}')
                intervalos = []
                for f in files:
                    if f and f.filename != '':
                        prox, inter = cert_processor.get_page_info(pag_atual, f)
                        intervalos.append(inter)
                        certificados_para_anexar.append(f)
                        pag_atual = prox
                
                item = ItemBarema(
                    atividade=ativ_objeto, 
                    horas_input=str(horas), 
                    tipo_barema=barema_tipo,
                    intervalo_paginas=", ".join(intervalos)
                )
                processo.adicionar_item(item)

        pdf_buffer = pdf_service.gerar_completo(processo, certificados=certificados_para_anexar) 

        nome_arquivo = f"barema_{matricula}_{uuid.uuid4().hex[:6]}.pdf"
        caminho_completo = os.path.join(UPLOAD_FOLDER, nome_arquivo)

        with open(caminho_completo, 'wb') as f:
            f.write(pdf_buffer.getbuffer())

        nova_analise = AnaliseBarema(
            matricula=matricula,
            nome_aluno=nome,
            caminho_pdf=nome_arquivo,
            status='Pendente'
        )
        db.session.add(nova_analise)
        db.session.commit()

        return "Solicitação enviada!", 200

    except Exception as e:
        print(traceback.format_exc())
        return str(e), 500

# ==========================================
# ROTAS DE AUTENTICAÇÃO E PAINEL (COORDENADOR)
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')

        usuario = Usuario.query.filter_by(username=user).first()

        if usuario and check_password_hash(usuario.password, pw):
            login_user(usuario)
            
            # Verifica a coluna 'cargo'
            if getattr(usuario, 'cargo', '') == 'admin':
                return redirect('/admin') 
            if getattr(usuario, 'cargo', '') == 'coordenador':
                return redirect(url_for('painel_coordenador')) 
        
        return render_template('login.html', erro="Usuário ou senha inválidos.")
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/coordenador/painel')
@login_required 
def painel_coordenador():
    analises_banco = AnaliseBarema.query.order_by(AnaliseBarema.data_solicitacao.desc()).all()
    return render_template('painel_coordenador.html', analises=analises_banco)


@app.route('/salvar-feedback', methods=['POST'])
@login_required
def salvar_feedback():
    id_analise = request.form.get('id')
    feedback = request.form.get('feedback')

    analise = AnaliseBarema.query.get(id_analise)
    
    if analise:
        analise.feedback = feedback
        analise.status = 'Analisado'
        db.session.commit()

    return redirect(url_for('painel_coordenador'))


if __name__ == '__main__':
    app.run(debug=True)