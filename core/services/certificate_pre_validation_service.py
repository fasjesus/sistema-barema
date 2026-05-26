from typing import List, MutableMapping, Optional, Sequence

from .certificate_validation_models import (
    ActivityRule,
    ExtractedCertificateData,
    StudentContext,
)
from .certificate_validation_utils import debug, format_hours, normalize_text, parse_hours


class BasicCertificatePreValidator:
    def validate_certificate(
        self,
        dados: ExtractedCertificateData,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> List[str]:
        irregularidades = []
        normalized_text = normalize_text(dados.text)
        normalized_name = normalize_text(student.nome)

        if normalized_name and normalized_name in normalized_text:
            debug("Basic-Validator", "Nome do aluno confirmado.")
        else:
            irregularidades.append("Nome do aluno nao confere com o certificado.")
            debug("Basic-Validator", "Nome do aluno nao confirmado.")

        if dados.carga_horaria is None:
            irregularidades.append("Carga horaria nao encontrada no certificado.")
            debug("Basic-Validator", "Carga horaria nao encontrada.")
        elif activity_rule.min_horas is not None and dados.carga_horaria < activity_rule.min_horas:
            minimo = format_hours(activity_rule.min_horas)
            irregularidades.append(f"Carga horaria inferior ao minimo de {minimo}h.")
            debug("Basic-Validator", "Carga horaria minima da atividade nao atendida.")

        datas_anteriores_ao_ingresso = [
            data for data in dados.datas if data.year < student.ano_ingresso
        ]
        if datas_anteriores_ao_ingresso:
            irregularidades.append("Certificado emitido antes do ano de ingresso do aluno.")
            debug("Basic-Validator", "Data anterior ao ingresso encontrada no certificado.")
        else:
            debug("Basic-Validator", "Data de emissao aprovada ou ausente.")

        return irregularidades

    def validate_activity_hours(
        self,
        horas_solicitadas,
        certificados_extraidos: Sequence[ExtractedCertificateData],
    ) -> List[str]:
        solicitadas = parse_hours(horas_solicitadas)
        if solicitadas is None or solicitadas <= 0:
            return []

        total_comprovado = sum(
            dados.carga_horaria
            for dados in certificados_extraidos
            if dados.carga_horaria is not None
        )
        if solicitadas > total_comprovado:
            return [
                "Carga horaria solicitada "
                f"({format_hours(solicitadas)}h) superior ao total comprovado nos "
                f"certificados ({format_hours(total_comprovado)}h)."
            ]

        debug("Basic-Validator", "Carga horaria solicitada comprovada pelos certificados.")
        return []

    def validate_duplicate_certificates(
        self,
        certificados_extraidos: Sequence[ExtractedCertificateData],
        fingerprints_anteriores: Optional[MutableMapping[str, str]] = None,
        atividade_atual: Optional[str] = None,
    ) -> List[str]:
        seen = set()
        for dados in certificados_extraidos:
            fingerprint = self._certificate_fingerprint(dados)
            if not fingerprint:
                continue
            if fingerprint in seen:
                return ["Certificado duplicado identificado na atividade."]
            if fingerprints_anteriores is not None and fingerprint in fingerprints_anteriores:
                atividade_origem = fingerprints_anteriores[fingerprint]
                if atividade_origem and atividade_atual and atividade_origem != atividade_atual:
                    return [
                        "Certificado duplicado identificado em outra atividade "
                        f"(atividade {atividade_origem})."
                    ]
                return ["Certificado duplicado identificado em outra atividade."]
            seen.add(fingerprint)
            if fingerprints_anteriores is not None and atividade_atual:
                fingerprints_anteriores[fingerprint] = atividade_atual

        return []

    def _certificate_fingerprint(self, dados: ExtractedCertificateData) -> str:
        normalized = normalize_text(dados.text)
        if len(normalized) < 30:
            return ""
        return normalized
