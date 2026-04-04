import os
import uuid
from datetime import datetime, date
from flask import Flask, request, render_template, send_file, jsonify
from flask_cors import CORS
from core.entities import Estudante, ProcessoBarema, ItemBarema
from core.repository import BaremaRepository
from core.services import PDFService, CertificateProcessor
from database import init_db
import sqlite3

app = Flask(__name__)
CORS(app)

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

@app.route('/')
def home():
    atividades = repo.load_atividades('antigo')
    return render_template('index.html', data_hoje=date.today().strftime("%d/%m/%Y"), atividades=atividades)

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
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Erro interno"}), 500

@app.route('/get_barema_data/<tipo>')
def get_barema_data(tipo):
    return jsonify(repo.load_atividades(tipo))

@app.route('/solicitar-analise', methods=['POST'])
def solicitar_analise():
    try:
        # 1. Pegar dados do formulário
        nome = request.form.get('nome')
        matricula = request.form.get('matricula')
        email = request.form.get('email')
        barema_tipo = request.form.get('barema_tipo', 'antigo')
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        # 2. Criar entidades básicas
        aluno = Estudante(nome=nome, matricula=matricula, email=email)
        processo = ProcessoBarema(estudante=aluno, tipo_barema=barema_tipo, data_envio=data_hoje)

        pag_atual = 2
        
        # Carregar atividades (retorna lista de dicts)
        atividades_base = repo.load_atividades(barema_tipo)
        
        certificados_para_anexar = [] # Lista para guardar todos os arquivos enviados
        
        for ativ_dict in atividades_base:
            ativ_objeto = repo.to_entity(ativ_dict)
            id_at = ativ_objeto.id 

            horas = request.form.get(f'horas_{id_at}')
            if horas and horas.strip():
                # Captura os arquivos da atividade atual
                files = request.files.getlist(f'certificado_{id_at}')
                intervalos = []
                
                for f in files:
                    if f and f.filename != '':
                        # Processa a numeração de páginas (Exatamente como no /barema)
                        prox, inter = cert_processor.get_page_info(pag_atual, f)
                        intervalos.append(inter)
                        certificados_para_anexar.append(f) # Adiciona à lista global de anexos
                        pag_atual = prox
                
                item = ItemBarema(
                    atividade=ativ_objeto, 
                    horas_input=str(horas), 
                    tipo_barema=barema_tipo,
                    intervalo_paginas=", ".join(intervalos) # Passa os intervalos para a tabela
                )
                processo.adicionar_item(item)

        # 4. GERAR O PDF COMPLETO 
        pdf_buffer = pdf_service.gerar_completo(processo, certificados=certificados_para_anexar) 

        # 5. SALVAR NO DISCO
        nome_arquivo = f"barema_{matricula}_{uuid.uuid4().hex[:6]}.pdf"
        caminho_completo = os.path.join(UPLOAD_FOLDER, nome_arquivo)

        with open(caminho_completo, 'wb') as f:
            f.write(pdf_buffer.getbuffer())

        # 6. SALVAR NO BANCO SQLITE
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
        import traceback
        print(traceback.format_exc()) # Mostra o erro detalhado no terminal
        return str(e), 500

# Rota do Painel (token simples na URL)
@app.route('/coordenador/painel')
def painel_coordenador():
    token = request.args.get('token')
    if token != 'COLCIC2026': # Token de acesso
        return "Acesso Negado: Token inválido.", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Pega todas as solicitações, das mais recentes para as mais antigas
    cursor.execute("SELECT * FROM analises ORDER BY data_solicitacao DESC")
    analises = cursor.fetchall()
    conn.close()

    return render_template('painel_coordenador.html', analises=analises)

# Rota para o Coordenador Salvar o Feedback
@app.route('/salvar-feedback', methods=['POST'])
def salvar_feedback():
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

    return redirect('/coordenador/painel?token=COLCIC2026')

if __name__ == '__main__':
    init_db() 
    app.run(debug=True)