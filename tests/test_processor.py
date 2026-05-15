import unittest
from datetime import date
from unittest.mock import patch

from core.services.validation_processor import (
    ActivityRule,
    CertificateDataExtractor,
    CertificateValidationProcessor,
    StudentContext,
)


class FakeTextExtractor:
    def __init__(self, texts):
        self.texts = list(texts)

    def extract(self, content):
        return self.texts.pop(0)


class CertificateExtractionTest(unittest.TestCase):
    def test_extracts_hours_and_dates_from_text(self):
        text = """
        Certificamos que Maria Silva participou do evento Semana de Computacao.
        Carga horaria: 20h.
        Emitido em 10/05/2024.
        """
        extractor = CertificateDataExtractor(text_extractor=FakeTextExtractor([text]))

        data = extractor.extract(b"pdf-content")

        self.assertEqual(data.carga_horaria, 20)
        self.assertEqual(data.datas, [date(2024, 5, 10)])
        self.assertEqual(data.data_emissao, date(2024, 5, 10))
        self.assertIn("Maria Silva", data.text)


class CertificateValidationProcessorTest(unittest.TestCase):
    def setUp(self):
        self.student = StudentContext(nome="Maria Silva", ano_ingresso=2024)
        self.activity_rule = ActivityRule(
            id="3",
            descricao="Participacao em eventos cientificos relacionados a computacao",
            min_horas=12,
            max_horas=80,
        )

    def build_processor(self, *texts):
        return CertificateValidationProcessor(text_extractor=FakeTextExtractor(texts))

    def test_valid_certificate_without_qr_or_ai(self):
        text = """
        Certificamos que Maria Silva participou do evento Semana de Computacao.
        Carga horaria: 20h.
        Emitido em 10/05/2024.
        """
        processor = self.build_processor(text)

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertTrue(result.valido)
        self.assertEqual(result.dados.qr_urls, [])
        self.assertEqual(result.dados.carga_horaria, 20)
        self.assertEqual(result.erros, [])
        self.assertEqual(result.irregularidades, [])
        self.assertEqual(result.avisos, [])

    def test_name_mismatch_reports_irregularity(self):
        text = """
        Certificamos que Joao Santos participou do evento.
        Carga horaria: 20h.
        Emitido em 10/05/2024.
        """
        processor = self.build_processor(text)

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertIn("Nome do aluno nao confere com o certificado.", result.irregularidades)

    def test_missing_hours_reports_irregularity(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Emitido em 10/05/2024.
        """
        processor = self.build_processor(text)

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertIn("Carga horaria nao encontrada no certificado.", result.irregularidades)

    def test_certificate_below_minimum_hours_reports_irregularity(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 8h.
        Emitido em 20/12/2024.
        """
        processor = self.build_processor(text)

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertIn("Carga horaria inferior ao minimo de 12h.", result.irregularidades)

    def test_certificate_with_any_date_before_student_admission_reports_irregularity(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 16h.
        Evento realizado em 20/12/2023.
        Validacao consultada em 10/05/2026.
        """
        processor = self.build_processor(text)

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertIn(
            "Certificado emitido antes do ano de ingresso do aluno.",
            result.irregularidades,
        )

    def test_single_certificate_with_more_hours_than_requested_is_valid_for_activity_hours(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 200h.
        Emitido em 20/12/2024.
        """
        processor = self.build_processor(text)

        result = processor.validate_activity(
            [b"pdf-content"],
            self.student,
            self.activity_rule,
            horas_solicitadas="30",
        )

        self.assertEqual(result.irregularidades, [])
        self.assertEqual(result.certificados[0].irregularidades, [])

    def test_multiple_certificates_can_sum_hours_for_same_activity(self):
        first = """
        Certificamos que Maria Silva participou do evento A.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        second = """
        Certificamos que Maria Silva participou do evento B.
        Carga horaria: 30h.
        Emitido em 21/12/2024.
        """
        processor = self.build_processor(first, second)

        result = processor.validate_activity(
            [b"first-pdf", b"second-pdf"],
            self.student,
            self.activity_rule,
            horas_solicitadas="50",
        )

        self.assertEqual(result.irregularidades, [])
        self.assertEqual([item.dados.carga_horaria for item in result.certificados], [20, 30])

    def test_activity_hours_above_extracted_sum_reports_irregularity(self):
        rule_without_minimum = ActivityRule(
            id="3",
            descricao="Participacao em eventos cientificos relacionados a computacao",
        )
        first = """
        Certificamos que Maria Silva participou do evento A.
        Carga horaria: 10h.
        Emitido em 20/12/2024.
        """
        second = """
        Certificamos que Maria Silva participou do evento B.
        Carga horaria: 20h.
        Emitido em 21/12/2024.
        """
        processor = self.build_processor(first, second)

        result = processor.validate_activity(
            [b"first-pdf", b"second-pdf"],
            self.student,
            rule_without_minimum,
            horas_solicitadas="50",
        )

        self.assertIn(
            "Carga horaria solicitada (50h) superior ao total comprovado nos certificados (30h).",
            result.irregularidades,
        )

    def test_processor_does_not_call_qr_detector(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        processor = self.build_processor(text)

        with patch(
            "core.services.validation_processor.QRCodeDetector.detect",
            side_effect=AssertionError("QR detector should not be called"),
        ):
            result = processor.validate_certificate(
                b"pdf-content",
                self.student,
                self.activity_rule,
            )

        self.assertEqual(result.irregularidades, [])


if __name__ == "__main__":
    unittest.main()
