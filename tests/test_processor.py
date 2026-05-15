import unittest

from core.services.validation_processor import (
    ActivityRule,
    CertificateValidationProcessor,
    QRCodeDetector,
    StudentContext,
)


class FakeQRDetector:
    def __init__(self, urls):
        self.urls = urls

    def detect(self, content):
        return self.urls


class FakeTextExtractor:
    def __init__(self, text):
        self.text = text

    def extract(self, content):
        return self.text


class CertificateValidationProcessorTest(unittest.TestCase):
    def setUp(self):
        self.student = StudentContext(nome="Maria Silva", ano_ingresso=2024)
        self.activity_rule = ActivityRule(
            id="3",
            descricao="Participacao em eventos cientificos relacionados a computacao",
            min_horas=12,
            max_horas=80,
        )

    def test_valid_certificate_with_qr_code(self):
        text = """
        Certificamos que Maria Silva participou do evento Semana de Computacao.
        Carga horaria: 20h.
        Emitido em 10/05/2024.
        """
        processor = CertificateValidationProcessor(
            qr_detector=FakeQRDetector(["https://certificados.uesc.br/validar/abc"]),
            text_extractor=FakeTextExtractor(text),
        )

        result = processor.validate(b"pdf-content", self.student, self.activity_rule)

        self.assertTrue(result.valido)
        self.assertEqual(result.dados.qr_urls, ["https://certificados.uesc.br/validar/abc"])
        self.assertEqual(result.dados.carga_horaria, 20)
        self.assertEqual(result.erros, [])
        self.assertEqual(result.irregularidades, [])

    def test_certificate_without_qr_code_generates_warning(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        CH 12h.
        Data: 15/06/2024.
        """
        processor = CertificateValidationProcessor(
            qr_detector=FakeQRDetector([]),
            text_extractor=FakeTextExtractor(text),
        )

        result = processor.validate(b"pdf-content", self.student, self.activity_rule)

        self.assertTrue(result.valido)
        self.assertIn("Certificado sem QR Code detectavel.", result.avisos)

    def test_certificate_emitted_before_student_admission_reports_irregularity(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 16h.
        Emitido em 20/12/2023.
        """
        processor = CertificateValidationProcessor(
            qr_detector=FakeQRDetector(["https://certificados.uesc.br/validar/abc"]),
            text_extractor=FakeTextExtractor(text),
        )

        result = processor.validate(b"pdf-content", self.student, self.activity_rule)

        self.assertTrue(result.valido)
        self.assertIn(
            "Certificado emitido antes do ano de ingresso do aluno.",
            result.irregularidades,
        )
        self.assertEqual(result.erros, [])

    def test_certificate_with_any_date_before_student_admission_reports_irregularity(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 16h.
        Evento realizado em 20/12/2023.
        Validacao consultada em 10/05/2026.
        """
        processor = CertificateValidationProcessor(
            qr_detector=FakeQRDetector(["https://certificados.uesc.br/validar/abc"]),
            text_extractor=FakeTextExtractor(text),
        )

        result = processor.validate(b"pdf-content", self.student, self.activity_rule)

        self.assertTrue(result.valido)
        self.assertIn(
            "Certificado emitido antes do ano de ingresso do aluno.",
            result.irregularidades,
        )
        self.assertEqual(result.erros, [])

    def test_certificate_with_year_context_before_student_admission_reports_irregularity(self):
        student = StudentContext(nome="Maria Silva", ano_ingresso=2025)
        text = """
        Certificamos que Maria Silva participou do curso.
        Carga horaria: 16h.
        Certificado emitido em 2024.
        """
        processor = CertificateValidationProcessor(
            qr_detector=FakeQRDetector(["https://certificados.uesc.br/validar/abc"]),
            text_extractor=FakeTextExtractor(text),
        )

        result = processor.validate(b"pdf-content", student, self.activity_rule)

        self.assertTrue(result.valido)
        self.assertIn(
            "Certificado emitido antes do ano de ingresso do aluno.",
            result.irregularidades,
        )
        self.assertEqual(result.erros, [])

    def test_certificate_below_minimum_hours_reports_irregularity(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 8h.
        Emitido em 20/12/2024.
        """
        processor = CertificateValidationProcessor(
            qr_detector=FakeQRDetector(["https://certificados.uesc.br/validar/abc"]),
            text_extractor=FakeTextExtractor(text),
        )

        result = processor.validate(b"pdf-content", self.student, self.activity_rule)

        self.assertTrue(result.valido)
        self.assertIn("Carga horaria inferior ao minimo de 12h.", result.irregularidades)
        self.assertEqual(result.erros, [])

    def test_untrusted_qr_code_reports_irregularity_without_blocking(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 16h.
        Emitido em 20/12/2024.
        """
        processor = CertificateValidationProcessor(
            qr_detector=FakeQRDetector(["http://site-sem-https.test/validar/abc"]),
            text_extractor=FakeTextExtractor(text),
        )

        result = processor.validate(b"pdf-content", self.student, self.activity_rule)

        self.assertTrue(result.valido)
        self.assertIn(
            "QR Code encontrado, mas a URL nao foi considerada confiavel.",
            result.irregularidades,
        )
        self.assertEqual(result.erros, [])


class QRCodeDetectorTest(unittest.TestCase):
    def test_falls_back_to_next_decoder_when_pyzbar_native_dependency_fails(self):
        detector = QRCodeDetector()

        def broken_pyzbar(_content):
            raise FileNotFoundError("libzbar-64.dll")

        detector._detect_with_pyzbar = broken_pyzbar
        detector._detect_with_opencv = lambda _content: [
            "https://certificados.uesc.br/validar/abc"
        ]

        self.assertEqual(
            detector.detect(b"pdf-content"),
            ["https://certificados.uesc.br/validar/abc"],
        )


if __name__ == "__main__":
    unittest.main()
