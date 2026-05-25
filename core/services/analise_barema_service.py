from core.entities import SolicitacaoAnalise
from core.repository import AnaliseBaremaRepository
from core.services.notification_service import NotificationService


class AnaliseBaremaService:
    def __init__(self, repository=None, notification_service=None):
        self.repository = repository or AnaliseBaremaRepository()
        self.notification_service = notification_service or NotificationService()

    def registrar_solicitacao(self, solicitacao: SolicitacaoAnalise):
        return self.repository.criar(solicitacao)

    def listar_solicitacoes(self):
        return self.repository.listar_ordenadas_por_data()

    def registrar_parecer(self, analise_id, parecer, usuario):
        if not usuario or not usuario.eh_coordenador():
            raise PermissionError("Apenas coordenadores podem registrar parecer.")

        analise_modelo = self.repository.buscar_modelo_por_id(analise_id)
        if not analise_modelo:
            return None

        solicitacao = analise_modelo.to_domain()
        solicitacao.registrar_parecer(parecer)
        analise_atualizada = self.repository.salvar_entidade(analise_modelo, solicitacao)
        self.notification_service.enviar_feedback(analise_atualizada, parecer)
        return analise_atualizada
