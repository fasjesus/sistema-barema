import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from typing import Callable, List, Optional, Protocol, Sequence

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

LOGGER = logging.getLogger("certificate-validation")


def _debug(component: str, message: str):
    LOGGER.debug("DEBUG [%s]: %s", component, message)
    print(f"DEBUG [{component}]: {message}")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().casefold()


@dataclass
class StudentContext:
    nome: str
    ano_ingresso: int


@dataclass
class ActivityRule:
    id: str
    descricao: str
    min_horas: Optional[float] = None
    max_horas: Optional[float] = None


@dataclass
class ExtractedCertificateData:
    text: str = ""
    qr_urls: List[str] = field(default_factory=list)
    carga_horaria: Optional[float] = None
    datas: List[date] = field(default_factory=list)
    data_emissao: Optional[date] = None


@dataclass
class CertificateValidationResult:
    valido: bool
    dados: ExtractedCertificateData
    erros: List[str] = field(default_factory=list)
    irregularidades: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)


class QRDetector(Protocol):
    def detect(self, content: bytes) -> List[str]:
        ...


class TextExtractor(Protocol):
    def extract(self, content: bytes) -> str:
        ...


class ContextValidator(Protocol):
    def validate(
        self,
        text: str,
        student: StudentContext,
        activity_rule: ActivityRule,
        carga_horaria: Optional[float],
    ) -> List[str]:
        ...


class PyMuPDFTextExtractor:
    def extract(self, content: bytes) -> str:
        if fitz is not None:
            try:
                with fitz.open(stream=content, filetype="pdf") as document:
                    text = "\n".join(page.get_text() for page in document)
                    _debug("Text-Extractor", "Texto extraido com PyMuPDF.")
                    return text
            except Exception as exc:
                _debug("Text-Extractor", f"PyMuPDF nao conseguiu extrair texto: {exc}")

        if PdfReader is not None:
            try:
                reader = PdfReader(BytesIO(content))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                _debug("Text-Extractor", "Texto extraido com pypdf.")
                return text
            except Exception as exc:
                _debug("Text-Extractor", f"pypdf nao conseguiu extrair texto: {exc}")

        _debug("Text-Extractor", "Nenhuma biblioteca de extracao disponivel ou arquivo sem texto.")
        return ""


class QRCodeDetector:
    def detect(self, content: bytes) -> List[str]:
        decoders = [self._detect_with_pyzbar, self._detect_with_opencv]
        for decoder in decoders:
            try:
                urls = decoder(content)
            except Exception as exc:
                _debug("QR-Detector", f"{decoder.__name__} falhou durante a leitura: {exc}")
                continue
            if urls:
                _debug("QR-Detector", "QR Code encontrado e decodificado com sucesso.")
                return urls

        _debug("QR-Detector", "Nenhum QR Code encontrado.")
        return []

    def _detect_with_pyzbar(self, content: bytes) -> List[str]:
        try:
            from PIL import Image
            from pyzbar.pyzbar import decode
        except (ImportError, OSError) as exc:
            _debug("QR-Detector", f"pyzbar indisponivel: {exc}")
            return []

        try:
            images = self._render_pages(content)
            urls = []
            for image_bytes in images:
                image = Image.open(BytesIO(image_bytes))
                urls.extend(item.data.decode("utf-8") for item in decode(image))
            return urls
        except Exception as exc:
            _debug("QR-Detector", f"pyzbar falhou durante a leitura: {exc}")
            return []

    def _detect_with_opencv(self, content: bytes) -> List[str]:
        try:
            import cv2
            import numpy as np
        except ImportError:
            return []

        urls = []
        try:
            detector = cv2.QRCodeDetector()
            for image_bytes in self._render_pages(content):
                array = np.frombuffer(image_bytes, dtype=np.uint8)
                image = cv2.imdecode(array, cv2.IMREAD_COLOR)
                data, _, _ = detector.detectAndDecode(image)
                if data:
                    urls.append(data)
        except Exception as exc:
            _debug("QR-Detector", f"opencv falhou durante a leitura: {exc}")
        return urls

    def _render_pages(self, content: bytes) -> Sequence[bytes]:
        if fitz is not None:
            try:
                with fitz.open(stream=content, filetype="pdf") as document:
                    return [page.get_pixmap(dpi=200).tobytes("png") for page in document]
            except Exception:
                pass
        return [content]


class RegexCertificateParser:
    DATE_PATTERNS = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
    ]
    YEAR_CONTEXT_PATTERNS = [
        r"(?:emitid[oa]|emiss[aã]o|expedid[oa]|conclu[ií]d[oa]|realizad[oa]|participou|evento|curso)\D{0,40}((?:19|20)\d{2})",
    ]

    def extract_hours(self, text: str) -> Optional[float]:
        search_text = _normalize_text(text)
        patterns = [
            r"(?:carga\s*horaria|ch)\D{0,20}(\d+(?:[,.]\d+)?)\s*h",
            r"(\d+(?:[,.]\d+)?)\s*(?:h|horas?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                value = float(match.group(1).replace(",", "."))
                _debug("Regex-Parser", f"Carga horaria extraida: {value}h.")
                return value

        _debug("Regex-Parser", "Carga horaria nao encontrada.")
        return None

    def extract_dates(self, text: str) -> List[date]:
        dates = []
        for pattern in self.DATE_PATTERNS:
            for groups in re.findall(pattern, text or ""):
                parsed = self._parse_date(groups)
                if parsed:
                    dates.append(parsed)

        if not dates:
            for pattern in self.YEAR_CONTEXT_PATTERNS:
                for year in re.findall(pattern, text or "", re.IGNORECASE):
                    dates.append(date(int(year), 12, 31))

        _debug("Regex-Parser", f"{len(dates)} data(s) extraida(s).")
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


class HeuristicContextValidator:
    def validate(
        self,
        text: str,
        student: StudentContext,
        activity_rule: ActivityRule,
        carga_horaria: Optional[float],
    ) -> List[str]:
        irregularidades = []
        normalized_text = _normalize_text(text)
        normalized_name = _normalize_text(student.nome)

        if normalized_name and normalized_name in normalized_text:
            _debug("IA-Validator", "Nome do aluno confirmado.")
        else:
            irregularidades.append("Nome do aluno nao confere com o certificado.")
            _debug("IA-Validator", "Nome do aluno nao confirmado.")

        if activity_rule.min_horas is not None and (
            carga_horaria is None or carga_horaria < activity_rule.min_horas
        ):
            irregularidades.append(f"Carga horaria inferior ao minimo de {activity_rule.min_horas}h.")
            _debug("IA-Validator", "Carga horaria minima da atividade nao atendida.")

        return irregularidades


class CertificateValidationProcessor:
    def __init__(
        self,
        qr_detector: Optional[QRDetector] = None,
        text_extractor: Optional[TextExtractor] = None,
        parser: Optional[RegexCertificateParser] = None,
        context_validator: Optional[ContextValidator] = None,
        trust_validator: Optional[Callable[[str], bool]] = None,
    ):
        self.qr_detector = qr_detector or QRCodeDetector()
        self.text_extractor = text_extractor or PyMuPDFTextExtractor()
        self.parser = parser or RegexCertificateParser()
        self.context_validator = context_validator or HeuristicContextValidator()
        self.trust_validator = trust_validator or self._default_trust_validator

    def validate(
        self,
        certificate_content: bytes,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> CertificateValidationResult:
        erros = []
        irregularidades = []
        avisos = []

        _debug("Processor", "Iniciando validacao do certificado.")
        qr_urls = self.qr_detector.detect(certificate_content)
        if qr_urls:
            if any(self.trust_validator(url) for url in qr_urls):
                _debug("Digital-Trust", "URL de autenticidade aprovada.")
            else:
                irregularidades.append("QR Code encontrado, mas a URL nao foi considerada confiavel.")
                _debug("Digital-Trust", "URL de autenticidade reprovada.")
        else:
            avisos.append("Certificado sem QR Code detectavel.")

        text = self.text_extractor.extract(certificate_content)
        carga_horaria = self.parser.extract_hours(text)
        datas = self.parser.extract_dates(text)
        data_emissao = max(datas) if datas else None
        datas_anteriores_ao_ingresso = [
            data for data in datas if data.year < student.ano_ingresso
        ]

        if datas_anteriores_ao_ingresso:
            irregularidades.append("Certificado emitido antes do ano de ingresso do aluno.")
            _debug("Date-Validator", "Data anterior ao ingresso encontrada no certificado.")
        else:
            _debug("Date-Validator", "Data de emissao aprovada ou ausente.")

        irregularidades.extend(self.context_validator.validate(text, student, activity_rule, carga_horaria))

        dados = ExtractedCertificateData(
            text=text,
            qr_urls=qr_urls,
            carga_horaria=carga_horaria,
            datas=datas,
            data_emissao=data_emissao,
        )
        return CertificateValidationResult(
            valido=True,
            dados=dados,
            erros=erros,
            irregularidades=irregularidades,
            avisos=avisos,
        )

    def _default_trust_validator(self, url: str) -> bool:
        return bool(re.match(r"^https://", url or "", re.IGNORECASE))
