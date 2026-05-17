import os
import unittest
from datetime import date
from unittest.mock import patch

from core.services.validation_processor import (
    AIValidationResult,
    ActivityRule,
    CertificateAIDataExtractor,
    OpenAICompatibleAIClient,
    CertificateAIPreValidator,
    CertificateAIPromptOptimizer,
    CertificateDataExtractor,
    CertificateValidationProcessor,
    ExtractedCertificateData,
    StudentContext,
    build_ai_client_from_env,
)


class FakeTextExtractor:
    def __init__(self, texts):
        self.texts = list(texts)

    def extract(self, content):
        return self.texts.pop(0)


class FakeAIClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def complete_json(self, prompt):
        self.prompts.append(prompt)
        return self.response


class SequenceAIClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete_json(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)


class FailingAIClient:
    def complete_json(self, prompt):
        raise AssertionError("AI client should not be called")


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

    def test_ai_extraction_fallback_completes_missing_hours_and_dates(self):
        text = """
        Certificamos que Maria Silva participou do evento Semana de Computacao.
        A atividade totalizou vinte horas.
        Emitido no dia dez de maio de dois mil e vinte e quatro.
        """
        ai_extractor = CertificateAIDataExtractor(
            ai_client=FakeAIClient(
                {
                    "carga_horaria": 20,
                    "datas": ["2024-05-10"],
                    "data_emissao": "2024-05-10",
                }
            ),
            enabled=True,
        )
        extractor = CertificateDataExtractor(
            text_extractor=FakeTextExtractor([text]),
            ai_extractor=ai_extractor,
        )

        data = extractor.extract(b"pdf-content")

        self.assertEqual(data.carga_horaria, 20)
        self.assertEqual(data.datas, [date(2024, 5, 10)])
        self.assertEqual(data.data_emissao, date(2024, 5, 10))

    def test_ai_extraction_fallback_is_not_called_when_regex_data_is_complete(self):
        text = """
        Certificamos que Maria Silva participou do evento Semana de Computacao.
        Carga horaria: 20h.
        Emitido em 10/05/2024.
        """
        ai_extractor = CertificateAIDataExtractor(
            ai_client=FailingAIClient(),
            enabled=True,
        )
        extractor = CertificateDataExtractor(
            text_extractor=FakeTextExtractor([text]),
            ai_extractor=ai_extractor,
        )

        data = extractor.extract(b"pdf-content")

        self.assertEqual(data.carga_horaria, 20)
        self.assertEqual(data.datas, [date(2024, 5, 10)])

    def test_ai_extraction_failure_keeps_local_extraction_result(self):
        text = """
        Certificamos que Maria Silva participou do evento Semana de Computacao.
        Emitido em 10/05/2024.
        """
        ai_extractor = CertificateAIDataExtractor(
            ai_client=FailingAIClient(),
            enabled=True,
        )
        extractor = CertificateDataExtractor(
            text_extractor=FakeTextExtractor([text]),
            ai_extractor=ai_extractor,
        )

        data = extractor.extract(b"pdf-content")

        self.assertIsNone(data.carga_horaria)
        self.assertEqual(data.datas, [date(2024, 5, 10)])


class CertificateAIPreValidationTest(unittest.TestCase):
    def setUp(self):
        self.student = StudentContext(nome="Maria Silva", ano_ingresso=2024)
        self.activity_rule = ActivityRule(
            id="3",
            descricao="Participacao em eventos cientificos relacionados a computacao",
            min_horas=12,
            max_horas=80,
        )

    def test_prompt_optimizer_keeps_payload_compact(self):
        noisy_text = (
            "Linha irrelevante com muito espaco. " * 80
            + "Certificamos que Maria Silva participou de Semana de Computacao. "
            + "Carga horaria: 20h. Emitido em 10/05/2024."
        )
        optimizer = CertificateAIPromptOptimizer(max_text_chars=180)

        payload = optimizer.build_payload(
            ExtractedCertificateData(text=noisy_text, carga_horaria=20),
            self.student,
            self.activity_rule,
        )

        self.assertLessEqual(len(payload["cert"]["txt"]), 180)
        self.assertNotIn("  ", payload["cert"]["txt"])
        self.assertEqual(
            payload["checks"],
            ["compatibilidade_atividade", "inconsistencias_texto"],
        )
        self.assertTrue(payload["sinais"]["nome_aluno_encontrado_no_texto"])
        self.assertEqual(payload["cert"]["nome_identificado"], "Maria Silva")
        self.assertTrue(payload["sinais"]["nome_formulario_confere_com_certificado"])

    def test_prompt_optimizer_keeps_ai_as_pre_validation_layer(self):
        optimizer = CertificateAIPromptOptimizer(max_text_chars=300)

        prompt = optimizer.build_prompt(
            ExtractedCertificateData(
                text="Certificamos que Joao Santos participou do evento. Carga horaria: 20h.",
                carga_horaria=20,
            ),
            self.student,
            self.activity_rule,
        )

        self.assertIn("pre-validacao academica", prompt)
        self.assertIn("confirma o nome do aluno", prompt)
        self.assertIn("carga horaria estruturada", prompt)
        self.assertIn('"nome_aluno_encontrado_no_texto":false', prompt)
        self.assertIn('"nome_identificado":"Joao Santos"', prompt)
        self.assertIn('"nome_formulario_confere_com_certificado":false', prompt)
        self.assertIn('{"irregularidades":[],"avisos":[]}', prompt)

    def test_ai_pre_validator_reports_objective_name_mismatch_even_when_model_misses_it(self):
        client = FakeAIClient({"irregularidades": [], "avisos": []})
        validator = CertificateAIPreValidator(
            ai_client=client,
            prompt_optimizer=CertificateAIPromptOptimizer(max_text_chars=300),
            enabled=True,
        )

        result = validator.validate_certificate(
            ExtractedCertificateData(
                text="Certificamos que Joao Santos participou do evento. Carga horaria: 20h.",
                carga_horaria=20,
            ),
            self.student,
            self.activity_rule,
        )

        self.assertEqual(
            result.irregularidades,
            [
                "IA: Nome do aluno informado nao confere com o nome identificado "
                "no certificado (Joao Santos)."
            ],
        )

    def test_ai_pre_validator_adds_structured_irregularities_and_avisos(self):
        client = FakeAIClient(
            {
                "irregularidades": ["Certificado nao parece relacionado a computacao."],
                "avisos": ["Conferir manualmente a instituicao emissora."],
            }
        )
        validator = CertificateAIPreValidator(
            ai_client=client,
            prompt_optimizer=CertificateAIPromptOptimizer(max_text_chars=300),
            enabled=True,
        )

        result = validator.validate_certificate(
            ExtractedCertificateData(
                text="Maria Silva concluiu curso de jardinagem. Carga horaria: 20h.",
                carga_horaria=20,
            ),
            self.student,
            self.activity_rule,
        )

        self.assertEqual(
            result.irregularidades,
            ["IA: Certificado nao parece relacionado a computacao."],
        )
        self.assertEqual(
            result.avisos,
            ["IA: Conferir manualmente a instituicao emissora."],
        )
        self.assertEqual(len(client.prompts), 1)
        self.assertLess(len(client.prompts[0]), 1400)

    def test_disabled_ai_pre_validator_does_not_call_client(self):
        validator = CertificateAIPreValidator(
            ai_client=FailingAIClient(),
            enabled=False,
        )

        result = validator.validate_certificate(
            ExtractedCertificateData(text="Maria Silva. Carga horaria: 20h."),
            self.student,
            self.activity_rule,
        )

        self.assertEqual(result, AIValidationResult())

    def test_from_env_disabled_ai_does_not_configure_client(self):
        with patch.dict(os.environ, {"CERTIFICATE_AI_ENABLED": "0"}, clear=True):
            validator = CertificateAIPreValidator.from_env()

        self.assertFalse(validator.enabled)
        self.assertIsNone(validator.ai_client)

    def test_from_env_none_provider_skips_ai_even_when_enabled(self):
        with patch.dict(
            os.environ,
            {"CERTIFICATE_AI_ENABLED": "1", "CERTIFICATE_AI_PROVIDER": "none"},
            clear=True,
        ):
            validator = CertificateAIPreValidator.from_env()

        self.assertFalse(validator.enabled)
        self.assertIsNone(validator.ai_client)

    def test_ollama_provider_uses_openai_compatible_defaults(self):
        env = {
            "CERTIFICATE_AI_PROVIDER": "ollama",
        }
        with patch.dict(os.environ, env, clear=True):
            client = build_ai_client_from_env()

        self.assertIsInstance(client, OpenAICompatibleAIClient)
        self.assertEqual(client.api_key, "ollama")
        self.assertEqual(client.base_url, "http://localhost:11434/v1")
        self.assertEqual(client.model, "llama3.2:3b")
        self.assertEqual(client.timeout, 45)

    def test_build_ai_client_from_env_creates_openai_compatible_client(self):
        env = {
            "CERTIFICATE_AI_PROVIDER": "openai_compatible",
            "AI_API_KEY": "test-key",
            "AI_BASE_URL": "https://api.example.test/v1",
            "AI_MODEL": "example-model",
            "AI_TIMEOUT": "7",
        }
        with patch.dict(os.environ, env, clear=True):
            client = build_ai_client_from_env()

        self.assertIsInstance(client, OpenAICompatibleAIClient)
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.base_url, "https://api.example.test/v1")
        self.assertEqual(client.model, "example-model")
        self.assertEqual(client.timeout, 7)

    def test_unknown_provider_adds_configuration_warning_without_breaking_basic_validation(self):
        env = {
            "CERTIFICATE_AI_ENABLED": "1",
            "CERTIFICATE_AI_PROVIDER": "misterio",
        }
        with patch.dict(os.environ, env, clear=True):
            validator = CertificateAIPreValidator.from_env()

        result = validator.validate_certificate(
            ExtractedCertificateData(text="Maria Silva. Carga horaria: 20h."),
            self.student,
            self.activity_rule,
        )

        self.assertEqual(result.irregularidades, [])
        self.assertIn("IA: configuracao de pre-validacao invalida.", result.avisos)

    def test_incomplete_openai_compatible_config_adds_configuration_warning(self):
        env = {
            "CERTIFICATE_AI_ENABLED": "1",
            "CERTIFICATE_AI_PROVIDER": "openai_compatible",
            "AI_API_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            validator = CertificateAIPreValidator.from_env()

        result = validator.validate_certificate(
            ExtractedCertificateData(text="Maria Silva. Carga horaria: 20h."),
            self.student,
            self.activity_rule,
        )

        self.assertEqual(result.irregularidades, [])
        self.assertEqual(result.avisos, ["IA: configuracao de pre-validacao invalida."])

    def test_ai_client_error_returns_unavailable_warning(self):
        validator = CertificateAIPreValidator(
            ai_client=FailingAIClient(),
            enabled=True,
        )

        result = validator.validate_certificate(
            ExtractedCertificateData(text="Maria Silva. Carga horaria: 20h."),
            self.student,
            self.activity_rule,
        )

        self.assertEqual(result.irregularidades, [])
        self.assertEqual(result.avisos, ["IA: pre-validacao indisponivel no momento."])

    def test_openai_compatible_client_normalizes_json_response(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"irregularidades":["Atividade generica nao condiz."],'
                                    '"avisos":["Conferir certificado."]}'
                                )
                            }
                        }
                    ]
                }

        client = OpenAICompatibleAIClient(
            api_key="test-key",
            base_url="https://api.example.test/v1",
            model="example-model",
        )
        with patch("requests.post", return_value=FakeResponse()) as post:
            response = client.complete_json("prompt compacto")

        self.assertEqual(response["irregularidades"], ["Atividade generica nao condiz."])
        self.assertEqual(response["avisos"], ["Conferir certificado."])
        self.assertEqual(post.call_args.args[0], "https://api.example.test/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")


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

    def test_valid_certificate_without_ai(self):
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

    def test_duplicate_certificates_in_same_activity_report_irregularity(self):
        text = """
        Certificamos que Maria Silva participou do evento A.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        processor = self.build_processor(text, text)

        result = processor.validate_activity(
            [b"first-pdf", b"second-pdf"],
            self.student,
            self.activity_rule,
            horas_solicitadas="40",
        )

        self.assertIn(
            "Certificado duplicado identificado na atividade.",
            result.irregularidades,
        )

    def test_processor_merges_enabled_ai_pre_validation_result(self):
        text = """
        Certificamos que Maria Silva participou de curso de culinaria.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        ai_pre_validator = CertificateAIPreValidator(
            ai_client=FakeAIClient(
                {"irregularidades": ["Atividade nao condiz com a regra do barema."]}
            ),
            enabled=True,
        )
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text]),
            ai_pre_validator=ai_pre_validator,
        )

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertIn(
            "IA: Atividade nao condiz com a regra do barema.",
            result.irregularidades,
        )

    def test_processor_skips_basic_certificate_pre_validation_when_ai_is_enabled(self):
        text = """
        Certificamos que Joao Santos participou do evento.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        ai_pre_validator = CertificateAIPreValidator(
            ai_client=FakeAIClient({"irregularidades": []}),
            enabled=True,
        )
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text]),
            ai_pre_validator=ai_pre_validator,
        )

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertNotIn("Nome do aluno nao confere com o certificado.", result.irregularidades)
        self.assertEqual(
            result.irregularidades,
            [
                "IA: Nome do aluno informado nao confere com o nome identificado "
                "no certificado (Joao Santos)."
            ],
        )

    def test_processor_uses_basic_certificate_pre_validation_when_ai_is_disabled(self):
        text = """
        Certificamos que Joao Santos participou do evento.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text]),
            ai_pre_validator=CertificateAIPreValidator(enabled=False),
        )

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertIn("Nome do aluno nao confere com o certificado.", result.irregularidades)

    def test_processor_skips_basic_activity_pre_validation_when_ai_is_enabled(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 5h.
        Emitido em 20/12/2024.
        """
        ai_pre_validator = CertificateAIPreValidator(
            ai_client=FakeAIClient({"irregularidades": []}),
            enabled=True,
        )
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text]),
            ai_pre_validator=ai_pre_validator,
        )

        result = processor.validate_activity(
            [b"pdf-content"],
            self.student,
            self.activity_rule,
            horas_solicitadas="100",
        )

        self.assertEqual(result.irregularidades, [])
        self.assertEqual(result.certificados[0].irregularidades, [])

    def test_processor_uses_ai_for_activity_hours_when_ai_is_enabled(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 5h.
        Emitido em 20/12/2024.
        """
        client = SequenceAIClient(
            [
                {"irregularidades": []},
                {
                    "irregularidades": [
                        "Carga horaria solicitada superior ao total comprovado."
                    ]
                },
            ]
        )
        ai_pre_validator = CertificateAIPreValidator(
            ai_client=client,
            enabled=True,
        )
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text]),
            ai_pre_validator=ai_pre_validator,
        )

        result = processor.validate_activity(
            [b"pdf-content"],
            self.student,
            self.activity_rule,
            horas_solicitadas="100",
        )

        self.assertIn(
            "IA: Carga horaria solicitada superior ao total comprovado.",
            result.irregularidades,
        )
        self.assertIn('"horas_solicitadas":100.0', client.prompts[1])
        self.assertIn('"total_comprovado":5.0', client.prompts[1])

    def test_processor_reports_duplicate_certificates_when_ai_is_enabled(self):
        text = """
        Certificamos que Maria Silva participou do evento A.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        ai_pre_validator = CertificateAIPreValidator(
            ai_client=FakeAIClient({"irregularidades": []}),
            enabled=True,
        )
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text, text]),
            ai_pre_validator=ai_pre_validator,
        )

        result = processor.validate_activity(
            [b"first-pdf", b"second-pdf"],
            self.student,
            self.activity_rule,
            horas_solicitadas="40",
        )

        self.assertIn(
            "IA: Certificado duplicado identificado na atividade.",
            result.irregularidades,
        )

    def test_processor_falls_back_to_basic_activity_validation_when_ai_api_fails(self):
        text = """
        Certificamos que Maria Silva participou do evento.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        ai_pre_validator = CertificateAIPreValidator(
            ai_client=FailingAIClient(),
            enabled=True,
        )
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text, text]),
            ai_pre_validator=ai_pre_validator,
        )

        result = processor.validate_activity(
            [b"first-pdf", b"second-pdf"],
            self.student,
            self.activity_rule,
            horas_solicitadas="50",
        )

        self.assertIn(
            "Carga horaria solicitada (50h) superior ao total comprovado nos certificados (40h).",
            result.irregularidades,
        )
        self.assertIn(
            "Certificado duplicado identificado na atividade.",
            result.irregularidades,
        )
        self.assertEqual(result.avisos, [])
        self.assertEqual(result.certificados[0].avisos, [])

    def test_processor_falls_back_to_basic_certificate_validation_when_ai_api_fails(self):
        text = """
        Certificamos que Joao Santos participou do evento.
        Carga horaria: 20h.
        Emitido em 20/12/2024.
        """
        ai_pre_validator = CertificateAIPreValidator(
            ai_client=FailingAIClient(),
            enabled=True,
        )
        processor = CertificateValidationProcessor(
            text_extractor=FakeTextExtractor([text]),
            ai_pre_validator=ai_pre_validator,
        )

        result = processor.validate_certificate(
            b"pdf-content",
            self.student,
            self.activity_rule,
        )

        self.assertIn("Nome do aluno nao confere com o certificado.", result.irregularidades)
        self.assertEqual(result.avisos, [])

if __name__ == "__main__":
    unittest.main()
