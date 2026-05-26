import os
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch

from app import app
from core.security import request_rate_limiter


class FakeAnaliseService:
    def __init__(self):
        self.solicitacoes = []

    def registrar_solicitacao(self, solicitacao):
        self.solicitacoes.append(solicitacao)
        return solicitacao


class SolicitarAnaliseRouteTest(unittest.TestCase):
    def setUp(self):
        self.previous_config = {
            "RATE_LIMIT_REQUESTS": app.config["RATE_LIMIT_REQUESTS"],
            "TESTING": app.config.get("TESTING", False),
        }
        app.config.update(TESTING=True, RATE_LIMIT_REQUESTS=100)
        request_rate_limiter.clear()
        self.tempdir = tempfile.TemporaryDirectory()
        self.fake_service = FakeAnaliseService()
        self.base_dir_patch = patch("routes.aluno_routes.BASE_DIR", self.tempdir.name)
        self.service_patch = patch("routes.aluno_routes.analise_service", self.fake_service)
        self.base_dir_patch.start()
        self.service_patch.start()

    def tearDown(self):
        self.service_patch.stop()
        self.base_dir_patch.stop()
        self.tempdir.cleanup()
        app.config.update(self.previous_config)
        request_rate_limiter.clear()

    def test_salva_exatamente_o_pdf_enviado(self):
        pdf_bytes = b"%PDF-1.4\nmesmo-pdf-do-download\n%%EOF"

        with app.test_client() as client:
            response = client.post(
                "/solicitar-analise",
                data={
                    "nome": "Aluno Teste",
                    "matricula": "202310001",
                    "email": "aluno@uesc.br",
                    "metodo_notificacao": "email",
                    "contato_notificacao": "aluno@uesc.br",
                    "download_confirmado": "1",
                    "barema_pdf": (BytesIO(pdf_bytes), "barema_202310001.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.fake_service.solicitacoes), 1)
        caminho_pdf = self.fake_service.solicitacoes[0].caminho_pdf
        caminho_salvo = os.path.join(self.tempdir.name, "static", "uploads", caminho_pdf)
        with open(caminho_salvo, "rb") as arquivo:
            self.assertEqual(arquivo.read(), pdf_bytes)

    def test_rejeita_sem_pdf_do_barema(self):
        with app.test_client() as client:
            response = client.post(
                "/solicitar-analise",
                data={
                    "nome": "Aluno Teste",
                    "matricula": "202310001",
                    "email": "aluno@uesc.br",
                    "download_confirmado": "1",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Baixe o documento", response.get_data(as_text=True))
        self.assertEqual(self.fake_service.solicitacoes, [])

    def test_rejeita_sem_confirmacao_de_download(self):
        with app.test_client() as client:
            response = client.post(
                "/solicitar-analise",
                data={
                    "nome": "Aluno Teste",
                    "matricula": "202310001",
                    "email": "aluno@uesc.br",
                    "barema_pdf": (BytesIO(b"%PDF-1.4\n%%EOF"), "barema.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Baixe o documento", response.get_data(as_text=True))
        self.assertEqual(self.fake_service.solicitacoes, [])


if __name__ == "__main__":
    unittest.main()
