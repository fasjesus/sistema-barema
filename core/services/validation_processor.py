import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from typing import List, Optional, Protocol, Sequence

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


def _format_hours(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _parse_hours(value) -> Optional[float]:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text.replace(",", "."))
    except (TypeError, ValueError):
        return None


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


@dataclass
class ActivityValidationResult:
    valido: bool
    certificados: List[CertificateValidationResult] = field(default_factory=list)
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
        dados: ExtractedCertificateData,
        student: StudentContext,
        activity_rule: ActivityRule,
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


class CertificateDataExtractor:
    def __init__(
        self,
        text_extractor: Optional[TextExtractor] = None,
        parser: Optional[RegexCertificateParser] = None,
    ):
        self.text_extractor = text_extractor or PyMuPDFTextExtractor()
        self.parser = parser or RegexCertificateParser()

    def extract(self, content: bytes) -> ExtractedCertificateData:
        _debug("Extractor", "Iniciando extracao de dados do certificado.")
        text = self.text_extractor.extract(content)
        carga_horaria = self.parser.extract_hours(text)
        datas = self.parser.extract_dates(text)
        data_emissao = max(datas) if datas else None

        return ExtractedCertificateData(
            text=text,
            qr_urls=[],
            carga_horaria=carga_horaria,
            datas=datas,
            data_emissao=data_emissao,
        )


class BasicCertificatePreValidator:
    def validate_certificate(
        self,
        dados: ExtractedCertificateData,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> List[str]:
        irregularidades = []
        normalized_text = _normalize_text(dados.text)
        normalized_name = _normalize_text(student.nome)

        if normalized_name and normalized_name in normalized_text:
            _debug("Basic-Validator", "Nome do aluno confirmado.")
        else:
            irregularidades.append("Nome do aluno nao confere com o certificado.")
            _debug("Basic-Validator", "Nome do aluno nao confirmado.")

        if dados.carga_horaria is None:
            irregularidades.append("Carga horaria nao encontrada no certificado.")
            _debug("Basic-Validator", "Carga horaria nao encontrada.")
        elif activity_rule.min_horas is not None and dados.carga_horaria < activity_rule.min_horas:
            minimo = _format_hours(activity_rule.min_horas)
            irregularidades.append(f"Carga horaria inferior ao minimo de {minimo}h.")
            _debug("Basic-Validator", "Carga horaria minima da atividade nao atendida.")

        datas_anteriores_ao_ingresso = [
            data for data in dados.datas if data.year < student.ano_ingresso
        ]
        if datas_anteriores_ao_ingresso:
            irregularidades.append("Certificado emitido antes do ano de ingresso do aluno.")
            _debug("Basic-Validator", "Data anterior ao ingresso encontrada no certificado.")
        else:
            _debug("Basic-Validator", "Data de emissao aprovada ou ausente.")

        return irregularidades

    def validate_activity_hours(
        self,
        horas_solicitadas,
        certificados_extraidos: Sequence[ExtractedCertificateData],
    ) -> List[str]:
        solicitadas = _parse_hours(horas_solicitadas)
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
                f"({_format_hours(solicitadas)}h) superior ao total comprovado nos "
                f"certificados ({_format_hours(total_comprovado)}h)."
            ]

        _debug("Basic-Validator", "Carga horaria solicitada comprovada pelos certificados.")
        return []


class CertificateValidationProcessor:
    def __init__(
        self,
        extractor: Optional[CertificateDataExtractor] = None,
        text_extractor: Optional[TextExtractor] = None,
        parser: Optional[RegexCertificateParser] = None,
        pre_validator: Optional[BasicCertificatePreValidator] = None,
        qr_detector: Optional[QRDetector] = None,
        context_validator: Optional[ContextValidator] = None,
        trust_validator=None,
    ):
        self.extractor = extractor or CertificateDataExtractor(
            text_extractor=text_extractor,
            parser=parser,
        )
        self.pre_validator = pre_validator or BasicCertificatePreValidator()

    def validate_certificate(
        self,
        certificate_content: bytes,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> CertificateValidationResult:
        _debug("Processor", "Iniciando pre-validacao basica do certificado.")
        dados = self.extractor.extract(certificate_content)
        irregularidades = self.pre_validator.validate_certificate(dados, student, activity_rule)

        return CertificateValidationResult(
            valido=True,
            dados=dados,
            erros=[],
            irregularidades=irregularidades,
            avisos=[],
        )

    def validate_activity(
        self,
        certificate_contents: Sequence[bytes],
        student: StudentContext,
        activity_rule: ActivityRule,
        horas_solicitadas,
    ) -> ActivityValidationResult:
        certificados = [
            self.validate_certificate(content, student, activity_rule)
            for content in certificate_contents
        ]
        dados_extraidos = [resultado.dados for resultado in certificados]
        irregularidades = self.pre_validator.validate_activity_hours(
            horas_solicitadas,
            dados_extraidos,
        )

        return ActivityValidationResult(
            valido=True,
            certificados=certificados,
            erros=[],
            irregularidades=irregularidades,
            avisos=[],
        )

    def validate(
        self,
        certificate_content: bytes,
        student: StudentContext,
        activity_rule: ActivityRule,
    ) -> CertificateValidationResult:
        return self.validate_certificate(certificate_content, student, activity_rule)
