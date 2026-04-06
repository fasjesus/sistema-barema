import os
import uuid
import sqlite3
import traceback
from datetime import datetime, date
from flask import Flask, request, render_template, send_file, jsonify, session, redirect, url_for
from flask_cors import CORS
from werkzeug.security import check_password_hash
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# Importações das entidades e serviços
from core.entities import Estudante, ProcessoBarema, ItemBarema
from core.repository import BaremaRepository
from core.services import PDFService, CertificateProcessor
from database import init_db

app = Flask(__name__)
CORS(app)

# CONFIGURAÇÕES DE SEGURANÇA
app.secret_key = os.getenv('SECRET_KEY', 'chave-padrao-caso-nao-encontre-env')

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

# --- ROTAS PÚBLICAS (ALUNO) ---

@app.route('/')
def home():
    # Carrega os dados iniciais do barema (regulamento antigo por padrão)
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

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO analises (matricula, nome_aluno, caminho_pdf, status) 
            VALUES (?, ?, ?, ?)
        """, (matricula, nome, nome_arquivo, 'Pendente'))
        conn.commit()
        conn.close()

        return "Solicitação enviada!", 200

    except Exception as e:
        print(traceback.format_exc())
        return str(e), 500

# --- ROTAS DE AUTENTICAÇÃO E PAINEL (COORDENADOR) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM usuarios WHERE username = ?", (user,))
        data = cursor.fetchone()
        conn.close()

        # Verifica se o usuário existe e a senha (hash) bate
        if data and check_password_hash(data[0], pw):
            session['logado'] = True
            session['usuario'] = user
            return redirect(url_for('painel_coordenador'))
        
        return render_template('login.html', erro="Usuário ou senha inválidos.")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/coordenador/painel')
def painel_coordenador():
    # Proteção
    if not session.get('logado'):
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM analises ORDER BY data_solicitacao DESC")
    analises = cursor.fetchall()
    conn.close()
    return render_template('painel_coordenador.html', analises=analises)

@app.route('/salvar-feedback', methods=['POST'])
def salvar_feedback():
    if not session.get('logado'):
        return redirect(url_for('login'))

    id_analise = request.form.get('id')
    feedback = request.form.get('feedback')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE analises SET feedback = ?, status = 'Analisado' WHERE id = ?",
        (feedback, id_analise)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('painel_coordenador'))

if __name__ == '__main__':
    init_db() # Cria tabelas e usuário administrador inicial
    app.run(debug=True)