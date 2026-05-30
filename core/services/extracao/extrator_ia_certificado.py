import re
from datetime import date
from typing import Any, Dict, List, Optional

from ..certificate_validation_models import AIClient, ExtractedCertificateData
from ..certificate_validation_utils import debug


class ExtratorIACertificado:
    def __init__(
        self,
        ai_client: Optional[AIClient] = None,
        habilitado: bool = False,
        max_caracteres_texto: int = 2400,
        enabled: Optional[bool] = None,
        max_text_chars: Optional[int] = None,
    ):
        if enabled is not None:
            habilitado = enabled
        if max_text_chars is not None:
            max_caracteres_texto = max_text_chars

        self.ai_client = ai_client
        self.habilitado = habilitado
        self.max_caracteres_texto = max_caracteres_texto
        self.enabled = habilitado
        self.max_text_chars = max_caracteres_texto

    @classmethod
    def from_env(cls):
        from ..certificate_ai_validation_service import (
            _env_flag,
            _env_int,
            build_ai_client_from_env,
        )

        if not _env_flag("CERTIFICATE_AI_ENABLED"):
            debug("AI-Extractor", "Extracao complementar com IA desabilitada por CERTIFICATE_AI_ENABLED.")
            return cls(habilitado=False)

        cliente = build_ai_client_from_env()
        if cliente is None:
            debug("AI-Extractor", "Extracao complementar com IA habilitada, mas cliente indisponivel.")
        else:
            debug("AI-Extractor", "Extracao complementar com IA habilitada.")

        return cls(
            ai_client=cliente,
            habilitado=True,
            max_caracteres_texto=_env_int("CERTIFICATE_AI_MAX_TEXT_CHARS", 2400),
        )

    def extract(self, texto: str) -> ExtractedCertificateData:
        if not self.habilitado:
            debug("AI-Extractor", "Extracao complementar com IA pulada: recurso desabilitado.")
            return ExtractedCertificateData(text=texto)
        if self.ai_client is None:
            debug("AI-Extractor", "Extracao complementar com IA pulada: cliente IA indisponivel.")
            return ExtractedCertificateData(text=texto)
        if not texto.strip():
            debug("AI-Extractor", "Extracao complementar com IA pulada: certificado sem texto extraido.")
            return ExtractedCertificateData(text=texto)

        prompt = self._montar_prompt(texto)
        try:
            debug("AI-Extractor", "Chamando IA para complementar extracao de dados.")
            resposta = self.ai_client.complete_json(prompt)
        except Exception as exc:
            debug("AI-Extractor", f"Falha na extracao com IA: {exc}")
            return ExtractedCertificateData(text=texto)

        resultado = ExtractedCertificateData(
            text=texto,
            carga_horaria=self._parse_horas(resposta.get("carga_horaria")),
            datas=self._parse_datas(resposta),
            data_emissao=self._parse_data(resposta.get("data_emissao")),
        )
        debug(
            "AI-Extractor",
            "Extracao complementar com IA concluida: "
            f"carga_horaria={resultado.carga_horaria}, datas={len(resultado.datas)}.",
        )
        return resultado

    def _montar_prompt(self, texto: str) -> str:
        limpo = re.sub(r"\s+", " ", texto or "").strip()
        compacto = limpo[: self.max_caracteres_texto]
        return (
            "Extraia dados estruturados do certificado academico. "
            "Use apenas o texto fornecido. Se nao encontrar um campo, use null ou []. "
            "Responda apenas JSON: "
            "{\"carga_horaria\":null,\"datas\":[],\"data_emissao\":null}."
            f"\nTexto:{compacto}"
        )

    def _parse_horas(self, valor) -> Optional[float]:
        if valor is None:
            return None
        try:
            return float(str(valor).replace(",", "."))
        except (TypeError, ValueError):
            return None

    def _parse_datas(self, resposta: Dict[str, Any]) -> List[date]:
        datas = []
        datas_brutas = resposta.get("datas") or []
        if isinstance(datas_brutas, str):
            datas_brutas = [datas_brutas]

        for item in datas_brutas:
            data_extraida = self._parse_data(item)
            if data_extraida:
                datas.append(data_extraida)

        data_emissao = self._parse_data(resposta.get("data_emissao"))
        if data_emissao and data_emissao not in datas:
            datas.append(data_emissao)

        return datas

    def _parse_data(self, valor) -> Optional[date]:
        if not valor:
            return None

        texto = str(valor).strip()
        padroes = [
            r"^(\d{4})-(\d{1,2})-(\d{1,2})$",
            r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$",
        ]
        for padrao in padroes:
            match = re.match(padrao, texto)
            if not match:
                continue
            try:
                grupos = match.groups()
                if len(grupos[0]) == 4:
                    ano, mes, dia = map(int, grupos)
                else:
                    dia, mes, ano = map(int, grupos)
                return date(ano, mes, dia)
            except ValueError:
                return None

        return None
