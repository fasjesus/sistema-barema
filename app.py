import os
import uuid
from datetime import date
from flask import Flask, request, render_template, send_file, jsonify
from flask_cors import CORS
from core.entities import Estudante, ProcessoBarema, ItemBarema
from core.repository import BaremaRepository
from core.services import PDFService, CertificateProcessor

app = Flask(__name__)
CORS(app)

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
            id_at = ativ['id'] # Garanta que o nome aqui seja 'id_at'
            
            # Use o mesmo nome 'id_at' aqui embaixo:
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

if __name__ == '__main__':
    app.run(debug=True)