import re
from datetime import date
from io import BytesIO
from typing import Any, Dict, List, Optional

from .certificate_validation_models import AIClient, ExtractedCertificateData, TextExtractor
from .certificate_validation_utils import debug, normalize_text

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


class PyMuPDFTextExtractor:
    def extract(self, content: bytes) -> str:
        if fitz is not None:
            try:
                with fitz.open(stream=content, filetype="pdf") as document:
                    text = "\n".join(page.get_text() for page in document)
                    debug("Text-Extractor", "Texto extraido com PyMuPDF.")
                    return text
            except Exception as exc:
                debug("Text-Extractor", f"PyMuPDF nao conseguiu extrair texto: {exc}")

        if PdfReader is not None:
            try:
                reader = PdfReader(BytesIO(content))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                debug("Text-Extractor", "Texto extraido com pypdf.")
                return text
            except Exception as exc:
                debug("Text-Extractor", f"pypdf nao conseguiu extrair texto: {exc}")

        debug("Text-Extractor", "Nenhuma biblioteca de extracao disponivel ou arquivo sem texto.")
        return ""


class RegexCertificateParser:
    DATE_PATTERNS = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
    ]
    YEAR_CONTEXT_PATTERN = (
        r"(?:emitid[oa]|emissao|expedid[oa]|concluid[oa]|realizad[oa]|"
        r"participou|evento|curso)\D{0,40}((?:19|20)\d{2})"
    )

    def extract_hours(self, text: str) -> Optional[float]:
        search_text = normalize_text(text)
        patterns = [
            r"(?:carga\s*horaria|ch)\D{0,20}(\d+(?:[,.]\d+)?)\s*h",
            r"(\d+(?:[,.]\d+)?)\s*(?:h|horas?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                value = float(match.group(1).replace(",", "."))
                debug("Regex-Parser", f"Carga horaria extraida: {value}h.")
                return value

        debug("Regex-Parser", "Carga horaria nao encontrada.")
        return None

    def extract_dates(self, text: str) -> List[date]:
        dates = []
        for pattern in self.DATE_PATTERNS:
            for groups in re.findall(pattern, text or ""):
                parsed = self._parse_date(groups)
                if parsed:
                    dates.append(parsed)

        if not dates:
            normalized = normalize_text(text)
            for year in re.findall(self.YEAR_CONTEXT_PATTERN, normalized, re.IGNORECASE):
                dates.append(date(int(year), 12, 31))

        debug("Regex-Parser", f"{len(dates)} data(s) extraida(s).")
        return dates

    def _parse_date(self, groups: tuple) -> Optional[date]:
        try:
            if len(groups[0]) == 4:
                year, month, day = map(int, groups)
            else:
                day, month, year = map(int, groups)
            return date(year, month, day)
        except ValueError:
            return None


class CertificateAIDataExtractor:
    def __init__(
        self,
        ai_client: Optional[AIClient] = None,
        enabled: bool = False,
        max_text_chars: int = 2400,
    ):
        self.ai_client = ai_client
        self.enabled = enabled
        self.max_text_chars = max_text_chars

    @classmethod
    def from_env(cls):
        from .certificate_ai_validation_service import (
            _env_flag,
            _env_int,
            build_ai_client_from_env,
        )

        if not _env_flag("CERTIFICATE_AI_ENABLED"):
            debug("AI-Extractor", "Extracao complementar com IA desabilitada por CERTIFICATE_AI_ENABLED.")
            return cls(enabled=False)

        client = build_ai_client_from_env()
        if client is None:
            debug("AI-Extractor", "Extracao complementar com IA habilitada, mas cliente indisponivel.")
        else:
            debug("AI-Extractor", "Extracao complementar com IA habilitada.")

        return cls(
            ai_client=client,
            enabled=True,
            max_text_chars=_env_int("CERTIFICATE_AI_MAX_TEXT_CHARS", 2400),
        )

    def extract(self, text: str) -> ExtractedCertificateData:
        if not self.enabled:
            debug("AI-Extractor", "Extracao complementar com IA pulada: recurso desabilitado.")
            return ExtractedCertificateData(text=text)
        if self.ai_client is None:
            debug("AI-Extractor", "Extracao complementar com IA pulada: cliente IA indisponivel.")
            return ExtractedCertificateData(text=text)
        if not text.strip():
            debug("AI-Extractor", "Extracao complementar com IA pulada: certificado sem texto extraido.")
            return ExtractedCertificateData(text=text)

        prompt = self._build_prompt(text)
        try:
            debug("AI-Extractor", "Chamando IA para complementar extracao de dados.")
            response = self.ai_client.complete_json(prompt)
        except Exception as exc:
            debug("AI-Extractor", f"Falha na extracao com IA: {exc}")
            return ExtractedCertificateData(text=text)

        result = ExtractedCertificateData(
            text=text,
            carga_horaria=self._parse_hours(response.get("carga_horaria")),
            datas=self._parse_dates(response),
            data_emissao=self._parse_date(response.get("data_emissao")),
        )
        debug(
            "AI-Extractor",
            "Extracao complementar com IA concluida: "
            f"carga_horaria={result.carga_horaria}, datas={len(result.datas)}.",
        )
        return result

    def _build_prompt(self, text: str) -> str:
        clean = re.sub(r"\s+", " ", text or "").strip()
        compact = clean[: self.max_text_chars]
        return (
            "Extraia dados estruturados do certificado academico. "
            "Use apenas o texto fornecido. Se nao encontrar um campo, use null ou []. "
            "Responda apenas JSON: "
            "{\"carga_horaria\":null,\"datas\":[],\"data_emissao\":null}."
            f"\nTexto:{compact}"
        )

    def _parse_hours(self, value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None

    def _parse_dates(self, response: Dict[str, Any]) -> List[date]:
        dates = []
        raw_dates = response.get("datas") or []
        if isinstance(raw_dates, str):
            raw_dates = [raw_dates]

        for item in raw_dates:
            parsed = self._parse_date(item)
            if parsed:
                dates.append(parsed)

        data_emissao = self._parse_date(response.get("data_emissao"))
        if data_emissao and data_emissao not in dates:
            dates.append(data_emissao)

        return dates

    def _parse_date(self, value) -> Optional[date]:
        if not value:
            return None

        text = str(value).strip()
        patterns = [
            r"^(\d{4})-(\d{1,2})-(\d{1,2})$",
            r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$",
        ]
        for pattern in patterns:
            match = re.match(pattern, text)
            if not match:
                continue
            try:
                groups = match.groups()
                if len(groups[0]) == 4:
                    year, month, day = map(int, groups)
                else:
                    day, month, year = map(int, groups)
                return date(year, month, day)
            except ValueError:
                return None

        return None


class CertificateDataExtractor:
    def __init__(
        self,
        text_extractor: Optional[TextExtractor] = None,
        parser: Optional[RegexCertificateParser] = None,
        ai_extractor: Optional[CertificateAIDataExtractor] = None,
    ):
        self.text_extractor = text_extractor or PyMuPDFTextExtractor()
        self.parser = parser or RegexCertificateParser()
        self.ai_extractor = ai_extractor or CertificateAIDataExtractor.from_env()

    def extract(self, content: bytes) -> ExtractedCertificateData:
        debug("Extractor", "Iniciando extracao de dados do certificado.")
        text = self.text_extractor.extract(content)
        carga_horaria = self.parser.extract_hours(text)
        datas = self.parser.extract_dates(text)
        if carga_horaria is None or not datas:
            debug(
                "Extractor",
                "Acionando extracao complementar com IA porque regex nao encontrou "
                f"{'carga horaria' if carga_horaria is None else 'todas as datas'}.",
            )
            ai_data = self.ai_extractor.extract(text)
            carga_horaria = carga_horaria if carga_horaria is not None else ai_data.carga_horaria
            datas = datas or ai_data.datas
        else:
            debug(
                "Extractor",
                "Extracao complementar com IA nao acionada: regex encontrou carga horaria e data.",
            )

        data_emissao = max(datas) if datas else None

        return ExtractedCertificateData(
            text=text,
            carga_horaria=carga_horaria,
            datas=datas,
            data_emissao=data_emissao,
        )
