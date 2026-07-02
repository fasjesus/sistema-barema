import os
import uuid
import traceback
from datetime import date
from flask import Blueprint, render_template, request, send_file, jsonify
from flask.views import MethodView
from core.entities import Estudante, ProcessoBarema, ItemBarema, SolicitacaoAnalise
from core.repository import BaremaRepository
from core.services import (
    AnaliseBaremaService,
    ActivityRule,
    CertificateProcessor,
    CertificateValidationProcessor,
    PDFService,
    StudentContext,
)

aluno_bp = Blueprint('aluno', __name__)

# Instanciando serviços com caminhos relativos ao projeto raiz
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
repo = BaremaRepository(BASE_DIR)
cert_processor = CertificateProcessor()
validation_processor = CertificateValidationProcessor()
analise_service = AnaliseBaremaService()
pdf_service = PDFService(
    logo_uesc=os.path.join(BASE_DIR, 'static', 'images', 'logo_uesc.png'),
    logo_colcic=os.path.join(BASE_DIR, 'static', 'images', 'logo_computacao.png')
)

class BaremaValidationError(ValueError):
    pass

def _ano_ingresso_from_matricula(matricula):
    try:
        return int(str(matricula or "")[:4])
    except ValueError:
        return None

def _activity_rule_from_entity(atividade):
    return ActivityRule(
        id=str(atividade.id),
        descricao=atividade.descricao or "",
        min_horas=atividade.min_horas_num,
        max_horas=atividade.max_horas_num,
    )

def _horas_maior_que_zero(valor):
    try:
        return float(str(valor or "").replace(",", ".")) > 0
    except ValueError:
        return False

def _formatar_horas(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)

    if numero.is_integer():
        return str(int(numero))
    return f"{numero:g}"

def _carga_minima_exigida(aluno, tipo_barema=None):
    ano_ingresso = _ano_ingresso_from_matricula(aluno.matricula)

    if ano_ingresso is None:
        return 200 if tipo_barema == "antigo" else 120

    return 200 if ano_ingresso < 2023 else 120

def _validar_carga_minima(processo):
    carga_minima = _carga_minima_exigida(
        processo.estudante,
        processo.tipo_barema,
    )
    total_horas = processo.total_horas

    if total_horas < carga_minima:
        raise BaremaValidationError(
            "Carga horaria insuficiente: o barema exige no minimo {0}h, "
            "mas foram computadas {1}h.".format(
                _formatar_horas(carga_minima),
                _formatar_horas(total_horas),
            )
        )

def _mensagens_do_resultado(filename, resultado):
    mensagens = []
    mensagens.extend(f"{filename}: Erro: {erro}" for erro in resultado.erros)
    mensagens.extend(
        f"{filename}: Irregularidade: {irregularidade}"
        for irregularidade in resultado.irregularidades
    )
    mensagens.extend(f"{filename}: Aviso: {aviso}" for aviso in resultado.avisos)
    return mensagens

def _validar_certificados_da_atividade(
    file_storages,
    aluno,
    atividade,
    horas_solicitadas,
    fingerprints_certificados=None,
):
    ano_ingresso = _ano_ingresso_from_matricula(aluno.matricula)

    if ano_ingresso is None:
        mensagem = "Atividade {0}: Erro: nao foi possivel identificar o ano de ingresso pela matricula.".format(atividade.id)
        print(f"VALIDACAO: {mensagem}")
        return [mensagem]

    arquivos = []
    conteudos = []
    try:
        for file_storage in file_storages:
            filename = file_storage.filename or "certificado"
            file_storage.seek(0)
            conteudo = file_storage.read()
            file_storage.seek(0)
            arquivos.append(filename)
            conteudos.append(conteudo)

        resultado_atividade = validation_processor.validate_activity(
            conteudos,
            StudentContext(nome=aluno.nome or "", ano_ingresso=ano_ingresso),
            _activity_rule_from_entity(atividade),
            horas_solicitadas,
            duplicate_fingerprints=fingerprints_certificados,
        )

        mensagens = []
        for filename, resultado_certificado in zip(arquivos, resultado_atividade.certificados):
            mensagens.extend(_mensagens_do_resultado(filename, resultado_certificado))

        mensagens.extend(
            f"Atividade {atividade.id}: Erro: {erro}"
            for erro in resultado_atividade.erros
        )
        mensagens.extend(
            f"Atividade {atividade.id}: Irregularidade: {irregularidade}"
            for irregularidade in resultado_atividade.irregularidades
        )
        mensagens.extend(
            f"Atividade {atividade.id}: Aviso: {aviso}"
            for aviso in resultado_atividade.avisos
        )

        if mensagens:
            for mensagem in mensagens:
                print(f"VALIDACAO: {mensagem}")
        else:
            print(f"VALIDACAO: Atividade {atividade.id}: certificados sem irregularidades.")

        return mensagens
    except Exception as exc:
        for file_storage in file_storages:
            try:
                file_storage.seek(0)
            except Exception:
                pass
        mensagem = f"Atividade {atividade.id}: Erro: nao foi possivel validar automaticamente os certificados."
        print(f"VALIDACAO: {mensagem} Detalhe: {exc}")
        return [mensagem]

def _montar_processo_barema(form, files):
    aluno = Estudante(
        nome=form.get('nome',''),
        matricula=form.get('matricula',''),
        email=form.get('email',''),
    )
    tipo = form.get('barema_tipo', 'antigo')
    processo = ProcessoBarema(
        estudante=aluno,
        tipo_barema=tipo,
        data_envio=form.get('data_verificacao',''),
    )

    atividades_base = repo.load_atividades(tipo)
    certificados, pag_atual = [], 2
    fingerprints_certificados = {}
    tem_atividade_preenchida = False

    for ativ in atividades_base:
        ativ_objeto = repo.to_entity(ativ)
        id_at = ativ['id']
        horas_raw = form.get(f"horas_{id_at}", "")
        files_atividade = files.getlist(f"certificado_{id_at}")
        files_validos = [f for f in files_atividade if f and f.filename != '']
        intervalos = []
        observacoes = []
        if files_validos or _horas_maior_que_zero(horas_raw):
            tem_atividade_preenchida = True

        for f in files_validos:
            prox, inter = cert_processor.get_page_info(pag_atual, f)
            intervalos.append(inter)
            certificados.append(f)
            pag_atual = prox

        if files_validos or (horas_raw and str(horas_raw).strip()):
            observacoes.extend(
                _validar_certificados_da_atividade(
                    files_validos,
                    aluno,
                    ativ_objeto,
                    horas_raw,
                    fingerprints_certificados,
                )
            )

        item = ItemBarema(
            atividade=ativ_objeto,
            horas_input=str(horas_raw),
            tipo_barema=tipo,
            intervalo_paginas=", ".join(intervalos),
            observacoes=observacoes
        )
        processo.adicionar_item(item)

    if not tem_atividade_preenchida:
        raise BaremaValidationError(
            "Preencha ao menos uma atividade antes de gerar o barema."
        )

    return processo, aluno, certificados

def _gerar_pdf_barema(form, files):
    processo, aluno, certificados = _montar_processo_barema(form, files)
    return pdf_service.gerar_completo(processo, certificados), aluno, processo

class HomeView(MethodView):
    def get(self):
        atividades = repo.load_atividades('antigo')
        return render_template('index.html', data_hoje=date.today().strftime("%d/%m/%Y"), atividades=atividades)

class BaremaDataView(MethodView):
    def get(self, tipo):
        return jsonify(repo.load_atividades(tipo))

class GerarRascunhoView(MethodView):
    def post(self):
        try:
            processo, aluno, certificados = _montar_processo_barema(
                request.form,
                request.files,
            )
            _validar_carga_minima(processo)
            pdf = pdf_service.gerar_completo(processo, certificados)
            return send_file(
                pdf,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"barema_{aluno.matricula}.pdf",
            )
        except BaremaValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            print(traceback.format_exc())
            return jsonify({"error": "Erro interno"}), 500

class PreviewBaremaView(MethodView):
    def post(self):
        try:
            pdf, aluno, _processo = _gerar_pdf_barema(request.form, request.files)
            return send_file(
                pdf,
                mimetype='application/pdf',
                as_attachment=False,
                download_name=f"preview_barema_{aluno.matricula}.pdf",
            )
        except BaremaValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            print(traceback.format_exc())
            return jsonify({"error": "Erro interno"}), 500

class SolicitarAnaliseView(MethodView):
    def post(self):
        try:
            nome, matricula, email = request.form.get('nome'), request.form.get('matricula'), request.form.get('email')

            if request.form.get('download_confirmado') != '1':
                return "Baixe o documento antes de solicitar analise.", 400

            barema_pdf = request.files.get('barema_pdf')
            if not barema_pdf:
                return "Baixe o documento antes de solicitar analise.", 400

            pdf_bytes = barema_pdf.read()
            if not pdf_bytes:
                return "Baixe o documento antes de solicitar analise.", 400

            aluno = Estudante(nome=nome, matricula=matricula, email=email)

            matricula_arquivo = "".join(ch for ch in str(matricula or "") if ch.isdigit()) or "sem_matricula"
            nome_arquivo = f"barema_{matricula_arquivo}_{uuid.uuid4().hex[:6]}.pdf"
            upload_folder = os.path.join(BASE_DIR, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            caminho_completo = os.path.join(upload_folder, nome_arquivo)

            with open(caminho_completo, 'wb') as f:
                f.write(pdf_bytes)

            metodo = request.form.get('metodo_notificacao')  # 'email' ou 'whatsapp'
            contato = request.form.get('contato_notificacao')

            solicitacao = SolicitacaoAnalise(
                estudante=aluno,
                caminho_pdf=nome_arquivo,
                whatsapp_aluno=contato if metodo == 'whatsapp' else None,
                metodo_preferencial=metodo or 'email',
            )
            analise_service.registrar_solicitacao(solicitacao)

            return "Solicitação enviada!", 200
        except Exception as e:
            print(traceback.format_exc())
            return str(e), 500

aluno_bp.add_url_rule('/', view_func=HomeView.as_view('home'))
aluno_bp.add_url_rule('/get_barema_data/<tipo>', view_func=BaremaDataView.as_view('get_barema_data'))
aluno_bp.add_url_rule('/barema', view_func=GerarRascunhoView.as_view('barema_process'))
aluno_bp.add_url_rule('/barema/preview', view_func=PreviewBaremaView.as_view('barema_preview'))
aluno_bp.add_url_rule('/solicitar-analise', view_func=SolicitarAnaliseView.as_view('solicitar_analise'))
