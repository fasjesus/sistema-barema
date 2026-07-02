import unittest

from core.entities import CargoUsuario, Estudante, SolicitacaoAnalise, Usuario
from core.services.analise_barema_service import AnaliseBaremaService


class FakeAnaliseModel:
    def __init__(self, solicitacao):
        self._solicitacao = solicitacao
        self.feedback = solicitacao.feedback
        self.status = solicitacao.status

    def to_domain(self):
        return self._solicitacao

    def atualizar_por_entidade(self, solicitacao):
        self._solicitacao = solicitacao
        self.feedback = solicitacao.feedback
        self.status = solicitacao.status


class FakeRepository:
    def __init__(self, analise_modelo):
        self.analise_modelo = analise_modelo
        self.salva = False

    def buscar_modelo_por_id(self, analise_id):
        return self.analise_modelo if analise_id == "1" else None

    def salvar_entidade(self, analise_modelo, solicitacao):
        self.salva = True
        analise_modelo.atualizar_por_entidade(solicitacao)
        return analise_modelo


class FakeNotificationService:
    def __init__(self):
        self.envios = []

    def enviar_feedback(self, analise, parecer):
        self.envios.append((analise, parecer))
        return {"email": object()}


class AnaliseBaremaServiceTest(unittest.TestCase):
    def test_registrar_parecer_exige_usuario_coordenador(self):
        service = AnaliseBaremaService(
            repository=FakeRepository(None),
            notification_service=FakeNotificationService(),
        )
        admin = Usuario(username="admin_dev", cargo=CargoUsuario.ADMIN)

        with self.assertRaises(PermissionError):
            service.registrar_parecer("1", "ok", admin)

    def test_registrar_parecer_atualiza_status_e_notifica(self):
        solicitacao = SolicitacaoAnalise(
            estudante=Estudante(
                nome="Aluno Exemplo",
                matricula="202310001",
                email="aluno.exemplo@uesc.br",
            ),
            caminho_pdf="barema_202310001.pdf",
        )
        repository = FakeRepository(FakeAnaliseModel(solicitacao))
        notification_service = FakeNotificationService()
        service = AnaliseBaremaService(
            repository=repository,
            notification_service=notification_service,
        )
        coordenador = Usuario(username="colcic", cargo=CargoUsuario.COORDENADOR)

        analise = service.registrar_parecer("1", "Parecer aprovado.", coordenador)

        self.assertTrue(repository.salva)
        self.assertEqual(analise.status, "Analisado")
        self.assertEqual(analise.feedback, "Parecer aprovado.")
        self.assertEqual(len(notification_service.envios), 1)
        self.assertIn("email", analise.notificacao_resultados)


if __name__ == "__main__":
    unittest.main()
