import unittest
from io import BytesIO
from unittest.mock import patch

from app import app


class FakePDFService:
    def gerar_completo(self, processo, certificados):
        return BytesIO(b"%PDF-1.4\nbarema-test\n%%EOF")


class FakeAnaliseService:
    def __init__(self):
        self.solicitacoes = []

    def registrar_solicitacao(self, solicitacao):
        self.solicitacoes.append(solicitacao)
        return solicitacao


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
        self.pdf_patch.start()
        self.service_patch.start()

    def tearDown(self):
        self.service_patch.stop()
        self.pdf_patch.stop()
        app.config.update(self.previous_config)

    def form_data(self):
        return {
            "nome": "Aluno Teste",
            "matricula": "202310001",
            "email": "aluno@uesc.br",
            "data_verificacao": "21/06/2026",
            "barema_tipo": "novo",
            "horas_1": "10",
        }

    def empty_form_data(self):
        data = self.form_data()
        data.pop("horas_1")
        return data

    def zero_hours_form_data(self):
        data = self.form_data()
        data["horas_1"] = "0"
        return data

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
