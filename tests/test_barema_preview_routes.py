import unittest
from io import BytesIO
from unittest.mock import patch

from app import app
from core.entities import Atividade


class FakePDFService:
    def gerar_completo(self, processo, certificados):
        return BytesIO(b"%PDF-1.4\nbarema-test\n%%EOF")


class FakeAnaliseService:
    def __init__(self):
        self.solicitacoes = []

    def registrar_solicitacao(self, solicitacao):
        self.solicitacoes.append(solicitacao)
        return solicitacao


class FakeBaremaRepository:
    def load_atividades(self, tipo):
        return [
            {
                "id": "1",
                "atividade": "Atividade teste",
                "carga_maxima": "300h",
                "max_horas_num": 300,
                "min_horas_num": None,
            }
        ]

    def to_entity(self, atividade):
        return Atividade(
            id=str(atividade["id"]),
            descricao=atividade["atividade"],
            carga_maxima=atividade["carga_maxima"],
            max_horas_num=atividade["max_horas_num"],
            min_horas_num=atividade["min_horas_num"],
        )


class BaremaPreviewRouteTest(unittest.TestCase):
    def setUp(self):
        self.previous_config = {
            "TESTING": app.config.get("TESTING", False),
        }
        app.config.update(TESTING=True)
        self.fake_analise_service = FakeAnaliseService()
        self.pdf_patch = patch("routes.aluno_routes.pdf_service", FakePDFService())
        self.service_patch = patch(
            "routes.aluno_routes.analise_service",
            self.fake_analise_service,
        )
        self.repo_patch = patch("routes.aluno_routes.repo", FakeBaremaRepository())
        self.pdf_patch.start()
        self.service_patch.start()
        self.repo_patch.start()

    def tearDown(self):
        self.repo_patch.stop()
        self.service_patch.stop()
        self.pdf_patch.stop()
        app.config.update(self.previous_config)

    def form_data(self, matricula="202310001", barema_tipo="novo", horas="120"):
        data = {
            "nome": "Aluno Teste",
            "matricula": matricula,
            "email": "aluno@uesc.br",
            "data_verificacao": "21/06/2026",
            "barema_tipo": barema_tipo,
        }
        if horas is not None:
            data["horas_1"] = horas
        return data

    def empty_form_data(self):
        return self.form_data(horas=None)

    def zero_hours_form_data(self):
        return self.form_data(horas="0")

    def test_preview_retorna_pdf_inline_sem_registrar_solicitacao(self):
        with app.test_client() as client:
            response = client.post("/barema/preview", data=self.form_data())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("inline", response.headers["Content-Disposition"])
        self.assertIn("preview_barema_202310001.pdf", response.headers["Content-Disposition"])
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_geracao_final_continua_retornando_pdf_como_attachment(self):
        with app.test_client() as client:
            response = client.post("/barema", data=self.form_data())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("barema_202310001.pdf", response.headers["Content-Disposition"])
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_geracao_final_rejeita_ingresso_antes_de_2023_com_menos_de_200h(self):
        data = self.form_data(
            matricula="202210001",
            barema_tipo="antigo",
            horas="199",
        )

        with app.test_client() as client:
            response = client.post("/barema", data=data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("minimo 200h", response.get_data(as_text=True))
        self.assertIn("computadas 199h", response.get_data(as_text=True))
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_geracao_final_aceita_ingresso_antes_de_2023_com_200h_ou_mais(self):
        data = self.form_data(
            matricula="202210001",
            barema_tipo="antigo",
            horas="200",
        )

        with app.test_client() as client:
            response = client.post("/barema", data=data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_geracao_final_rejeita_ingresso_a_partir_de_2023_com_menos_de_120h(self):
        data = self.form_data(
            matricula="202310001",
            barema_tipo="novo",
            horas="119",
        )

        with app.test_client() as client:
            response = client.post("/barema", data=data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("minimo 120h", response.get_data(as_text=True))
        self.assertIn("computadas 119h", response.get_data(as_text=True))
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_geracao_final_aceita_ingresso_a_partir_de_2023_com_120h_ou_mais(self):
        data = self.form_data(
            matricula="202310001",
            barema_tipo="novo",
            horas="120",
        )

        with app.test_client() as client:
            response = client.post("/barema", data=data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_preview_continua_liberada_abaixo_da_carga_minima(self):
        data = self.form_data(
            matricula="202310001",
            barema_tipo="novo",
            horas="10",
        )

        with app.test_client() as client:
            response = client.post("/barema/preview", data=data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("inline", response.headers["Content-Disposition"])
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_preview_rejeita_barema_sem_atividade_preenchida(self):
        with app.test_client() as client:
            response = client.post("/barema/preview", data=self.empty_form_data())

        self.assertEqual(response.status_code, 400)
        self.assertIn("Preencha ao menos uma atividade", response.get_data(as_text=True))
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_geracao_final_rejeita_barema_sem_atividade_preenchida(self):
        with app.test_client() as client:
            response = client.post("/barema", data=self.empty_form_data())

        self.assertEqual(response.status_code, 400)
        self.assertIn("Preencha ao menos uma atividade", response.get_data(as_text=True))
        self.assertEqual(self.fake_analise_service.solicitacoes, [])

    def test_geracao_final_rejeita_barema_apenas_com_horas_zeradas(self):
        with app.test_client() as client:
            response = client.post("/barema", data=self.zero_hours_form_data())

        self.assertEqual(response.status_code, 400)
        self.assertIn("Preencha ao menos uma atividade", response.get_data(as_text=True))
        self.assertEqual(self.fake_analise_service.solicitacoes, [])


if __name__ == "__main__":
    unittest.main()
