import unittest

from core.entities import CargoUsuario, Estudante, SolicitacaoAnalise, Usuario


class UsuarioDomainTest(unittest.TestCase):
    def test_identifica_cargos_do_usuario(self):
        coordenador = Usuario(username="colcic", cargo=CargoUsuario.COORDENADOR)
        admin = Usuario(username="admin_dev", cargo=CargoUsuario.ADMIN)

        self.assertTrue(coordenador.eh_coordenador())
        self.assertFalse(coordenador.eh_admin())
        self.assertTrue(admin.eh_admin())
        self.assertFalse(admin.eh_coordenador())


class SolicitacaoAnaliseDomainTest(unittest.TestCase):
    def test_registrar_parecer_altera_feedback_e_status(self):
        solicitacao = SolicitacaoAnalise(
            estudante=Estudante(
                nome="Aluno Exemplo",
                matricula="202310001",
                email="aluno.exemplo@uesc.br",
            ),
            caminho_pdf="barema_202310001.pdf",
        )

        solicitacao.registrar_parecer("Documentacao conferida.")

        self.assertEqual(solicitacao.feedback, "Documentacao conferida.")
        self.assertEqual(solicitacao.status, "Analisado")


if __name__ == "__main__":
    unittest.main()
