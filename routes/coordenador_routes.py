from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask.views import MethodView
from flask_login import login_required, current_user
from core.models import db, AnaliseBarema
from core.services import NotificationService

coordenador_bp = Blueprint('coordenador', __name__, url_prefix='/coordenador')

# --- A CLASSE PAI (SEGURANÇA) ---
class CoordenadorBaseView(MethodView):
    decorators = [login_required]

    def dispatch_request(self, *args, **kwargs):
        if getattr(current_user, 'cargo', '') != 'coordenador':
            abort(403)
        return super().dispatch_request(*args, **kwargs)

# --- AS ROTAS FILHAS ---
class PainelView(CoordenadorBaseView):
    def get(self):
        analises_banco = AnaliseBarema.query.order_by(AnaliseBarema.data_solicitacao.desc()).all()
        return render_template('painel_coordenador.html', analises=analises_banco)

class SalvarFeedbackView(CoordenadorBaseView):
    def post(self):
        id_analise = request.form.get('id')
        feedback = request.form.get('feedback')
        analise = AnaliseBarema.query.get(id_analise)
        
        if analise:
            # 1. Atualiza o status no banco de dados
            analise.feedback = feedback
            analise.status = 'Analisado'
            db.session.commit()
            
            # 2. Notifica o aluno (WhatsApp ou E-mail)
            # try/except para que um erro na API externa não trave o sistema
            try:
                notifier = NotificationService()
                # O método enviar_feedback já identifica se é email ou whatsapp
                notifier.enviar_feedback(analise, feedback)
            except Exception as e:
                
                print(f"⚠️ Erro ao notificar aluno {analise.matricula}: {e}")
        
        return redirect(url_for('coordenador.painel'))

# Registrando
coordenador_bp.add_url_rule('/painel', view_func=PainelView.as_view('painel'))
coordenador_bp.add_url_rule('/salvar-feedback', view_func=SalvarFeedbackView.as_view('salvar_feedback'))