from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask.views import MethodView
from flask_login import current_user, login_required

from core.services import AnaliseBaremaService

coordenador_bp = Blueprint("coordenador", __name__, url_prefix="/coordenador")
analise_service = AnaliseBaremaService()


class CoordenadorBaseView(MethodView):
    decorators = [login_required]

    def dispatch_request(self, *args, **kwargs):
        if not current_user.eh_coordenador():
            abort(403)
        return super().dispatch_request(*args, **kwargs)


class PainelView(CoordenadorBaseView):
    def get(self):
        analises_banco = analise_service.listar_solicitacoes()
        return render_template("painel_coordenador.html", analises=analises_banco)


class SalvarFeedbackView(CoordenadorBaseView):
    def post(self):
        id_analise = request.form.get("id")
        feedback = request.form.get("feedback")
        try:
            analise_service.registrar_parecer(id_analise, feedback, current_user)
        except Exception as exc:
            print(f"Erro ao salvar parecer da analise {id_analise}: {exc}")

        return redirect(url_for("coordenador.painel"))


coordenador_bp.add_url_rule("/painel", view_func=PainelView.as_view("painel"))
coordenador_bp.add_url_rule(
    "/salvar-feedback",
    view_func=SalvarFeedbackView.as_view("salvar_feedback"),
)
