import json
import os
import re
from typing import Any, Dict, List, Optional

from .certificate_validation_models import (
    AIClient,
    AIValidationResult,
    ActivityRule,
    CertificateValidationResult,
    ExtractedCertificateData,
    StudentContext,
)
from .certificate_validation_utils import debug, normalize_text, parse_hours


class CertificateAIPromptOptimizer:
    KEYWORDS = (
        "certificamos",
        "certifico",
        "participou",
        "concluiu",
        "curso",
        "evento",
        "carga horaria",
        "horas",
        "emitido",
        "emissao",
        "computacao",
        "certificado",
    )

    def __init__(self, max_text_chars: int = 2400):
        self.max_text_chars = max_text_chars

    def build_payload(
        self,
        dados: ExtractedCertificateData,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> Dict[str, Any]:
        normalized_student_name = normalize_text(student.nome)
        normalized_certificate_text = normalize_text(dados.text)
        certificate_holder_name = self.extract_certificate_holder_name(dados.text)
        normalized_certificate_holder_name = normalize_text(certificate_holder_name or "")
        name_matches_certificate = self.name_matches_certificate(
            student.nome,
            dados.text,
            certificate_holder_name,
        )
        return {
            "aluno": {
                "nome": student.nome,
                "nome_normalizado": normalized_student_name,
                "ingresso": student.ano_ingresso,
            },
            "atividade": {
                "id": activity_rule.id,
                "desc": activity_rule.descricao,
                "min": activity_rule.min_horas,
                "max": activity_rule.max_horas,
            },
            "cert": {
                "txt": self.compact_text(dados.text),
                "nome_identificado": certificate_holder_name,
                "nome_identificado_normalizado": normalized_certificate_holder_name,
                "h": dados.carga_horaria,
                "datas": [item.isoformat() for item in dados.datas],
                "emissao": dados.data_emissao.isoformat() if dados.data_emissao else None,
            },
            "sinais": {
                "nome_aluno_encontrado_no_texto": bool(
                    normalized_student_name
                    and normalized_student_name in normalized_certificate_text
                ),
                "nome_formulario_confere_com_certificado": name_matches_certificate,
            },
            "checks": self.select_actions(dados, activity_rule),
        }

    def build_prompt(
        self,
        dados: ExtractedCertificateData,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> str:
        payload = self.build_payload(dados, student, activity_rule)
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return (
            "Voce e uma pre-validacao academica. Use so os dados fornecidos. "
            "Verifique se o texto confirma o nome do aluno, se a carga horaria estruturada "
            "parece compativel com o texto, se as datas fazem sentido e se o certificado "
            "condiz com a atividade do barema. Regras obrigatorias: compare aluno.nome "
            "com cert.nome_identificado; se forem pessoas diferentes ou "
            "sinais.nome_formulario_confere_com_certificado=false, registre "
            "irregularidade; se atividade.min existir e "
            "cert.h for menor que atividade.min, registre irregularidade; se datas forem "
            "anteriores ao ano de ingresso, registre irregularidade. Nao invente problemas: "
            "aponte apenas inconsistencias objetivas. "
            "Responda apenas JSON: {\"irregularidades\":[],\"avisos\":[]}."
            f"\nDados:{payload_json}"
        )

    def select_actions(
        self,
        dados: ExtractedCertificateData,
        activity_rule: ActivityRule,
    ) -> List[str]:
        actions = []
        if dados.text and activity_rule.descricao:
            actions.append("compatibilidade_atividade")
        if dados.text:
            actions.append("inconsistencias_texto")
        return actions

    def compact_text(self, text: str) -> str:
        clean = re.sub(r"\s+", " ", text or "").strip()
        if len(clean) <= self.max_text_chars:
            return clean

        sentences = re.split(r"(?<=[.!?;:])\s+", clean)
        scored = []
        for index, sentence in enumerate(sentences):
            normalized = normalize_text(sentence)
            score = sum(1 for keyword in self.KEYWORDS if keyword in normalized)
            if score:
                scored.append((-score, index, sentence))

        selected = [item for _, _, item in sorted(scored)[:8]]
        if selected:
            compact = " ".join(selected)
            if compact:
                return compact[: self.max_text_chars].strip()

        tail_size = max(0, self.max_text_chars // 3)
        head_size = max(0, self.max_text_chars - tail_size - 5)
        return f"{clean[:head_size]} ... {clean[-tail_size:]}".strip()

    def extract_certificate_holder_name(self, text: str) -> Optional[str]:
        clean = re.sub(r"\s+", " ", text or "").strip()
        patterns = [
            r"\bcertificamos\s+que\s+(.{3,120}?)(?:\s+participou|\s+concluiu|\s+realizou|\s+esteve|\s+frequentou|\s+atuou|[,.;])",
            r"\bcertifico\s+que\s+(.{3,120}?)(?:\s+participou|\s+concluiu|\s+realizou|\s+esteve|\s+frequentou|\s+atuou|[,.;])",
            r"\bconferid[oa]\s+a\s+(.{3,120}?)(?:[,.;]|\s+por\s+|\s+pela\s+|\s+participou|\s+concluiu)",
            r"\bparticipante\s*[:\-]\s*(.{3,120}?)(?:[,.;]|\s{2,}|$)",
            r"\bnome\s*[:\-]\s*(.{3,120}?)(?:[,.;]|\s{2,}|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, clean, re.IGNORECASE)
            if not match:
                continue
            candidate = self._clean_name_candidate(match.group(1))
            if candidate:
                return candidate
        return None

    def name_matches_certificate(
        self,
        student_name: str,
        certificate_text: str,
        certificate_holder_name: Optional[str] = None,
    ) -> Optional[bool]:
        normalized_student_name = normalize_text(student_name)
        if not normalized_student_name:
            return None

        if certificate_holder_name:
            return normalized_student_name == normalize_text(certificate_holder_name)

        normalized_certificate_text = normalize_text(certificate_text)
        if normalized_student_name in normalized_certificate_text:
            return True
        return False

    def _clean_name_candidate(self, value: str) -> str:
        candidate = re.sub(r"\s+", " ", value or "").strip(" ,.;:-")
        candidate = re.sub(r"^(?:o|a|sr\.?|sra\.?|aluno|aluna)\s+", "", candidate, flags=re.IGNORECASE)
        words = candidate.split()
        if len(words) < 2:
            return ""
        if any(char.isdigit() for char in candidate):
            return ""
        return " ".join(words[:8])


class OpenAICompatibleAIClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 45,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete_json(self, prompt: str) -> Dict[str, Any]:
        import requests

        debug(
            "AI-Client",
            f"Enviando prompt para provider OpenAI-compatible. modelo={self.model}, url={self.base_url}",
        )
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        parsed = _parse_json_payload(_extract_openai_compatible_text(payload))
        debug("AI-Client", "Resposta JSON recebida e interpretada com sucesso.")
        return parsed


class CertificateAIPreValidator:
    def __init__(
        self,
        ai_client: Optional[AIClient] = None,
        prompt_optimizer: Optional[CertificateAIPromptOptimizer] = None,
        enabled: bool = False,
        configuration_warning: Optional[str] = None,
    ):
        self.ai_client = ai_client
        self.prompt_optimizer = prompt_optimizer or CertificateAIPromptOptimizer()
        self.enabled = enabled
        self.configuration_warning = configuration_warning

    @classmethod
    def from_env(cls, enabled: Optional[bool] = None):
        should_enable = enabled if enabled is not None else _env_flag("CERTIFICATE_AI_ENABLED")
        if not should_enable:
            debug("AI-Config", "Pre-validacao com IA desabilitada por CERTIFICATE_AI_ENABLED.")
            return cls(enabled=False)

        provider = _env_text("CERTIFICATE_AI_PROVIDER", "none")
        if provider == "none":
            debug("AI-Config", "Pre-validacao com IA ignorada porque provider=none.")
            return cls(enabled=False)

        client = build_ai_client_from_env()
        if client is None:
            debug(
                "AI-Config",
                f"Pre-validacao com IA habilitada, mas configuracao invalida. provider={provider}",
            )
            return cls(
                enabled=True,
                configuration_warning="IA: configuracao de pre-validacao invalida.",
            )

        debug(
            "AI-Config",
            f"Pre-validacao com IA habilitada. provider={provider}, max_text_chars={_env_int('CERTIFICATE_AI_MAX_TEXT_CHARS', 2400)}",
        )
        return cls(
            ai_client=client,
            prompt_optimizer=CertificateAIPromptOptimizer(
                max_text_chars=_env_int("CERTIFICATE_AI_MAX_TEXT_CHARS", 2400)
            ),
            enabled=True,
        )

    def validate_certificate(
        self,
        dados: ExtractedCertificateData,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> AIValidationResult:
        if not self.enabled:
            debug("AI-Validator", "Pre-validacao com IA pulada: recurso desabilitado.")
            return AIValidationResult()
        if self.ai_client is None:
            debug("AI-Validator", "Pre-validacao com IA pulada: cliente IA indisponivel.")
            if self.configuration_warning:
                return AIValidationResult(avisos=[self.configuration_warning])
            return AIValidationResult(avisos=["IA: configuracao de pre-validacao invalida."])
        if not dados.text.strip():
            debug("AI-Validator", "Pre-validacao com IA pulada: certificado sem texto extraido.")
            return AIValidationResult()

        prompt = self.prompt_optimizer.build_prompt(dados, student, activity_rule)
        try:
            debug("AI-Validator", "Chamando IA para pre-validacao do certificado.")
            response = self.ai_client.complete_json(prompt)
        except Exception as exc:
            debug("AI-Validator", f"Falha na pre-validacao com IA: {exc}")
            return AIValidationResult(avisos=["IA: pre-validacao indisponivel no momento."])

        result = AIValidationResult(
            irregularidades=_prefixed_messages(response.get("irregularidades"), "IA"),
            avisos=_prefixed_messages(response.get("avisos"), "IA"),
        )
        self._append_name_mismatch_if_needed(result, dados, student)
        debug(
            "AI-Validator",
            "Pre-validacao com IA concluida: "
            f"{len(result.irregularidades)} irregularidade(s), {len(result.avisos)} aviso(s).",
        )
        for message in result.irregularidades:
            debug("AI-Validator", f"Irregularidade retornada: {message}")
        for message in result.avisos:
            debug("AI-Validator", f"Aviso retornado: {message}")
        return result

    def _append_name_mismatch_if_needed(
        self,
        result: AIValidationResult,
        dados: ExtractedCertificateData,
        student: StudentContext,
    ) -> None:
        certificate_holder_name = self.prompt_optimizer.extract_certificate_holder_name(dados.text)
        name_matches = self.prompt_optimizer.name_matches_certificate(
            student.nome,
            dados.text,
            certificate_holder_name,
        )
        debug(
            "AI-Validator",
            "Comparacao objetiva de nome: "
            f"formulario='{student.nome}', certificado='{certificate_holder_name or 'nao identificado'}', confere={name_matches}.",
        )
        if name_matches is not False:
            return

        already_reported = any(
            "nome" in normalize_text(message)
            for message in result.irregularidades
        )
        if already_reported:
            return

        if certificate_holder_name:
            result.irregularidades.append(
                "IA: Nome do aluno informado nao confere com o nome identificado "
                f"no certificado ({certificate_holder_name})."
            )
        else:
            result.irregularidades.append(
                "IA: Nome do aluno informado nao foi identificado no certificado."
            )

    def validate_activity(
        self,
        certificados: List[CertificateValidationResult],
        student: StudentContext,
        activity_rule: ActivityRule,
        horas_solicitadas,
    ) -> AIValidationResult:
        result = AIValidationResult()
        self._append_duplicate_certificates_if_needed(result, certificados)

        if not self.enabled:
            debug("AI-Activity-Validator", "Pre-validacao de atividade com IA pulada: recurso desabilitado.")
            return result
        if self.ai_client is None:
            debug("AI-Activity-Validator", "Pre-validacao de atividade com IA pulada: cliente IA indisponivel.")
            if self.configuration_warning:
                result.avisos.append(self.configuration_warning)
                return result
            result.avisos.append("IA: configuracao de pre-validacao invalida.")
            return result

        prompt = self._build_activity_prompt(
            certificados=certificados,
            student=student,
            activity_rule=activity_rule,
            horas_solicitadas=horas_solicitadas,
        )
        try:
            debug("AI-Activity-Validator", "Chamando IA para pre-validacao da atividade.")
            response = self.ai_client.complete_json(prompt)
        except Exception as exc:
            debug("AI-Activity-Validator", f"Falha na pre-validacao de atividade com IA: {exc}")
            result.avisos.append("IA: pre-validacao indisponivel no momento.")
            return result

        result.irregularidades.extend(
            _prefixed_messages(response.get("irregularidades"), "IA")
        )
        result.avisos.extend(_prefixed_messages(response.get("avisos"), "IA"))
        debug(
            "AI-Activity-Validator",
            "Pre-validacao de atividade com IA concluida: "
            f"{len(result.irregularidades)} irregularidade(s), {len(result.avisos)} aviso(s).",
        )
        for message in result.irregularidades:
            debug("AI-Activity-Validator", f"Irregularidade retornada: {message}")
        for message in result.avisos:
            debug("AI-Activity-Validator", f"Aviso retornado: {message}")
        return result

    def _append_duplicate_certificates_if_needed(
        self,
        result: AIValidationResult,
        certificados: List[CertificateValidationResult],
    ) -> None:
        seen = set()
        for certificado in certificados:
            fingerprint = self._certificate_fingerprint(certificado.dados)
            if not fingerprint:
                continue
            if fingerprint in seen:
                message = "IA: Certificado duplicado identificado na atividade."
                if message not in result.irregularidades:
                    result.irregularidades.append(message)
                    debug(
                        "AI-Activity-Validator",
                        "Duplicidade objetiva identificada entre certificados da atividade.",
                    )
                return
            seen.add(fingerprint)

    def _certificate_fingerprint(self, dados: ExtractedCertificateData) -> str:
        normalized = normalize_text(dados.text)
        if len(normalized) < 30:
            return ""
        return normalized

    def _build_activity_prompt(
        self,
        certificados: List[CertificateValidationResult],
        student: StudentContext,
        activity_rule: ActivityRule,
        horas_solicitadas,
    ) -> str:
        solicitadas = parse_hours(horas_solicitadas)
        certificados_payload = []
        for index, resultado in enumerate(certificados, start=1):
            dados = resultado.dados
            certificados_payload.append(
                {
                    "idx": index,
                    "h": dados.carga_horaria,
                    "datas": [item.isoformat() for item in dados.datas],
                    "txt": self.prompt_optimizer.compact_text(dados.text),
                    "irregularidades_certificado": resultado.irregularidades,
                    "avisos_certificado": resultado.avisos,
                }
            )

        total_comprovado = sum(
            resultado.dados.carga_horaria
            for resultado in certificados
            if resultado.dados.carga_horaria is not None
        )
        payload = {
            "aluno": {"nome": student.nome, "ingresso": student.ano_ingresso},
            "atividade": {
                "id": activity_rule.id,
                "desc": activity_rule.descricao,
                "min": activity_rule.min_horas,
                "max": activity_rule.max_horas,
            },
            "horas_solicitadas": solicitadas,
            "total_comprovado": total_comprovado,
            "certificados": certificados_payload,
        }
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return (
            "Voce e uma pre-validacao academica de uma atividade do barema. "
            "Use so os dados fornecidos. Regras obrigatorias: se horas_solicitadas "
            "for maior que total_comprovado, registre irregularidade; se houver "
            "certificados duplicados ou incompatibilidade clara com a atividade, registre "
            "irregularidade; se nao houver evidencia suficiente, use avisos. "
            "Responda apenas JSON: {\"irregularidades\":[],\"avisos\":[]}."
            f"\nDados:{payload_json}"
        )


def build_ai_client_from_env() -> Optional[AIClient]:
    provider = _env_text("CERTIFICATE_AI_PROVIDER", "none")
    if provider == "none":
        debug("AI-Config", "Cliente IA nao criado: provider=none.")
        return None

    if provider in {"openai_compatible", "ollama"}:
        api_key = os.getenv("AI_API_KEY", "").strip()
        base_url = os.getenv("AI_BASE_URL", "").strip()
        model = os.getenv("AI_MODEL", "").strip()
        if provider == "ollama":
            api_key = api_key or "ollama"
            base_url = base_url or "http://localhost:11434/v1"
            model = model or "llama3.2:3b"
        if not api_key or not base_url or not model:
            debug(
                "AI-Config",
                "Cliente IA nao criado: informe AI_API_KEY, AI_BASE_URL e AI_MODEL.",
            )
            return None
        debug(
            "AI-Config",
            f"Cliente IA criado. provider={provider}, model={model}, base_url={base_url}",
        )
        return OpenAICompatibleAIClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=_env_int("AI_TIMEOUT", 45),
        )

    debug("AI-Config", f"Cliente IA nao criado: provider desconhecido '{provider}'.")
    return None


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "").strip().casefold()
    return value in {"1", "true", "yes", "sim", "on"}


def _env_text(name: str, default: str) -> str:
    return os.getenv(name, default).strip().casefold()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _extract_openai_compatible_text(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return "{}"

    message = choices[0].get("message") or {}
    content = message.get("content") or "{}"
    if isinstance(content, list):
        texts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "output_text", None}
        ]
        return "\n".join(texts).strip() or "{}"
    return str(content).strip() or "{}"


def _parse_json_payload(value: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value or "", re.DOTALL)
        if not match:
            return {}
        parsed = json.loads(match.group(0))

    return parsed if isinstance(parsed, dict) else {}


def _prefixed_messages(value, prefix: str) -> List[str]:
    if not isinstance(value, list):
        return []

    messages = []
    for item in value[:5]:
        text = str(item or "").strip()
        if not text:
            continue
        if not text.startswith(f"{prefix}:"):
            text = f"{prefix}: {text}"
        messages.append(text[:240])
    return messages
