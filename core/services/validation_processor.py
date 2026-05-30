from typing import Optional, Sequence

from .certificate_ai_validation_service import (
    CertificateAIPreValidator,
    CertificateAIPromptOptimizer,
    OpenAICompatibleAIClient,
    build_ai_client_from_env,
)
from .certificate_extraction_service import (
    CertificateAIDataExtractor,
    CertificateDataExtractor,
    PyMuPDFTextExtractor,
    RegexCertificateParser,
    TesseractOCRTextExtractor,
)
from .certificate_pre_validation_service import BasicCertificatePreValidator
from .certificate_validation_models import (
    AIValidationResult,
    ActivityRule,
    ActivityValidationResult,
    CertificateValidationResult,
    ContextValidator,
    ExtractedCertificateData,
    StudentContext,
    TextExtractor,
)
from .certificate_validation_utils import debug


class CertificateValidationProcessor:
    def __init__(
        self,
        extractor: Optional[CertificateDataExtractor] = None,
        text_extractor: Optional[TextExtractor] = None,
        parser: Optional[RegexCertificateParser] = None,
        pre_validator: Optional[BasicCertificatePreValidator] = None,
        ai_pre_validator: Optional[CertificateAIPreValidator] = None,
        enable_ai_validation: Optional[bool] = None,
        context_validator: Optional[ContextValidator] = None,
        trust_validator=None,
    ):
        self.extractor = extractor or CertificateDataExtractor(
            text_extractor=text_extractor,
            parser=parser,
        )
        self.pre_validator = pre_validator or BasicCertificatePreValidator()
        self.ai_pre_validator = (
            ai_pre_validator
            if ai_pre_validator is not None
            else CertificateAIPreValidator.from_env(enabled=enable_ai_validation)
        )
        self.context_validator = context_validator
        self.trust_validator = trust_validator

    def validate_certificate(
        self,
        certificate_content: bytes,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> CertificateValidationResult:
        dados = self.extractor.extract(certificate_content)
        irregularidades = []
        avisos = []
        erros = []

        if self._uses_ai_pre_validation():
            debug(
                "Validation-Processor",
                "Modo de pre-validacao: IA habilitada. Validacao basica do certificado pulada.",
            )
            ai_result = self.ai_pre_validator.validate_certificate(dados, student, activity_rule)
            erros.extend(ai_result.erros)
            irregularidades.extend(ai_result.irregularidades)
            avisos.extend(ai_result.avisos)
            if self._ai_unavailable(ai_result.avisos):
                debug(
                    "Validation-Processor",
                    "IA indisponivel na pre-validacao do certificado. Usando validacao basica como fallback.",
                )
                erros = []
                avisos = []
                irregularidades = self.pre_validator.validate_certificate(
                    dados,
                    student,
                    activity_rule,
                )
        else:
            debug(
                "Validation-Processor",
                "Modo de pre-validacao: IA desabilitada. Usando validacao basica do certificado.",
            )
            irregularidades.extend(
                self.pre_validator.validate_certificate(dados, student, activity_rule)
            )

        if self.context_validator is not None:
            irregularidades.extend(
                self.context_validator.validate(dados, student, activity_rule)
            )

        return CertificateValidationResult(
            valido=True,
            dados=dados,
            erros=erros,
            irregularidades=irregularidades,
            avisos=avisos,
        )

    def validate_activity(
        self,
        certificate_contents: Sequence[bytes],
        student: StudentContext,
        activity_rule: ActivityRule,
        horas_solicitadas,
        duplicate_fingerprints=None,
    ) -> ActivityValidationResult:
        certificados = [
            self.validate_certificate(content, student, activity_rule)
            for content in certificate_contents
        ]
        dados_extraidos = [resultado.dados for resultado in certificados]
        irregularidades = []
        if self._uses_ai_pre_validation():
            debug(
                "Validation-Processor",
                "Modo de pre-validacao: IA habilitada. Validacoes basicas da atividade puladas; usando IA para atividade.",
            )
            ai_activity_result = self.ai_pre_validator.validate_activity(
                certificados,
                student,
                activity_rule,
                horas_solicitadas,
            )
            irregularidades.extend(ai_activity_result.irregularidades)
            avisos = ai_activity_result.avisos
            erros = ai_activity_result.erros
            if self._has_ai_unavailable_result(certificados, ai_activity_result.avisos):
                debug(
                    "Validation-Processor",
                    "IA indisponivel na pre-validacao da atividade. Recalculando atividade com validacao basica.",
                )
                certificados = [
                    self._basic_certificate_result(
                        resultado.dados,
                        student,
                        activity_rule,
                    )
                    for resultado in certificados
                ]
                dados_extraidos = [resultado.dados for resultado in certificados]
                irregularidades = []
                irregularidades.extend(
                    self.pre_validator.validate_activity_hours(
                        horas_solicitadas,
                        dados_extraidos,
                    )
                )
                irregularidades.extend(
                    self.pre_validator.validate_duplicate_certificates(dados_extraidos)
                )
                if duplicate_fingerprints is not None:
                    irregularidades.extend(
                        message
                        for message in self.pre_validator.validate_duplicate_certificates(
                            dados_extraidos,
                            duplicate_fingerprints,
                            activity_rule.id,
                        )
                        if message not in irregularidades
                    )
                avisos = []
                erros = []
            elif duplicate_fingerprints is not None:
                for message in self.pre_validator.validate_duplicate_certificates(
                    dados_extraidos,
                    duplicate_fingerprints,
                    activity_rule.id,
                ):
                    message_normalized = message.casefold()
                    already_reported = any(
                        message_normalized in irregularidade.casefold()
                        or irregularidade.casefold() in message_normalized
                        for irregularidade in irregularidades
                    )
                    if not already_reported:
                        irregularidades.append(message)
        else:
            irregularidades.extend(
                self.pre_validator.validate_activity_hours(
                    horas_solicitadas,
                    dados_extraidos,
                )
            )
            irregularidades.extend(
                self.pre_validator.validate_duplicate_certificates(
                    dados_extraidos,
                    duplicate_fingerprints,
                    activity_rule.id,
                )
            )
            avisos = []
            erros = []

        return ActivityValidationResult(
            valido=True,
            certificados=certificados,
            erros=erros,
            irregularidades=irregularidades,
            avisos=avisos,
        )

    def validate(
        self,
        certificate_content: bytes,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> CertificateValidationResult:
        return self.validate_certificate(certificate_content, student, activity_rule)

    def _uses_ai_pre_validation(self) -> bool:
        return bool(self.ai_pre_validator.enabled)

    def _basic_certificate_result(
        self,
        dados: ExtractedCertificateData,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> CertificateValidationResult:
        irregularidades = self.pre_validator.validate_certificate(dados, student, activity_rule)
        if self.context_validator is not None:
            irregularidades.extend(
                self.context_validator.validate(dados, student, activity_rule)
            )
        return CertificateValidationResult(
            valido=True,
            dados=dados,
            erros=[],
            irregularidades=irregularidades,
            avisos=[],
        )

    def _has_ai_unavailable_result(
        self,
        certificados: Sequence[CertificateValidationResult],
        activity_avisos: Sequence[str],
    ) -> bool:
        return any(self._ai_unavailable(resultado.avisos) for resultado in certificados) or self._ai_unavailable(activity_avisos)

    def _ai_unavailable(self, avisos: Sequence[str]) -> bool:
        normalized_avisos = [aviso.casefold() for aviso in avisos]
        return any(
            "pre-validacao indisponivel" in aviso
            or "configuracao de pre-validacao invalida" in aviso
            for aviso in normalized_avisos
        )


__all__ = [
    "AIValidationResult",
    "ActivityRule",
    "ActivityValidationResult",
    "BasicCertificatePreValidator",
    "CertificateAIPreValidator",
    "CertificateAIPromptOptimizer",
    "CertificateAIDataExtractor",
    "CertificateDataExtractor",
    "CertificateValidationProcessor",
    "CertificateValidationResult",
    "ContextValidator",
    "ExtractedCertificateData",
    "OpenAICompatibleAIClient",
    "PyMuPDFTextExtractor",
    "RegexCertificateParser",
    "StudentContext",
    "TextExtractor",
    "TesseractOCRTextExtractor",
    "build_ai_client_from_env",
]
