from typing import Optional

from ..certificate_validation_models import ExtractedCertificateData, TextExtractor
from ..certificate_validation_utils import debug, normalize_text
from .analisador_regex_certificado import AnalisadorRegexCertificado
from .extrator_ia_certificado import ExtratorIACertificado
from .extrator_ocr import ExtratorOCR
from .extrator_texto_pdf import ExtratorTextoPDF


class ExtratorDadosCertificado:
    def __init__(
        self,
        extrator_texto: Optional[TextExtractor] = None,
        extrator_ocr: Optional[TextExtractor] = None,
        analisador: Optional[AnalisadorRegexCertificado] = None,
        extrator_ia: Optional[ExtratorIACertificado] = None,
        text_extractor: Optional[TextExtractor] = None,
        ocr_text_extractor: Optional[TextExtractor] = None,
        parser: Optional[AnalisadorRegexCertificado] = None,
        ai_extractor: Optional[ExtratorIACertificado] = None,
    ):
        self.extrator_texto = extrator_texto or text_extractor or ExtratorTextoPDF()
        self.extrator_ocr = extrator_ocr or ocr_text_extractor or ExtratorOCR.from_env()
        self.analisador = analisador or parser or AnalisadorRegexCertificado()
        self.extrator_ia = extrator_ia or ai_extractor or ExtratorIACertificado.from_env()
        self.text_extractor = self.extrator_texto
        self.ocr_text_extractor = self.extrator_ocr
        self.parser = self.analisador
        self.ai_extractor = self.extrator_ia

    def extract(self, conteudo: bytes) -> ExtractedCertificateData:
        debug("Extractor", "Iniciando extracao de dados do certificado.")
        texto = self.extrator_texto.extract(conteudo)
        carga_horaria = self.analisador.extract_hours(texto)
        datas = self.analisador.extract_dates(texto)

        if self._precisa_ocr(texto):
            debug("Extractor", "Texto extraido insuficiente; acionando OCR.")
            texto_ocr = self.extrator_ocr.extract(conteudo)
            if texto_ocr.strip():
                texto = self._mesclar_texto(texto, texto_ocr)
                carga_horaria = self.analisador.extract_hours(texto)
                datas = self.analisador.extract_dates(texto)
            else:
                debug("Extractor", "OCR nao retornou texto aproveitavel.")

        if carga_horaria is None or not datas:
            debug(
                "Extractor",
                "Acionando extracao complementar com IA porque regex nao encontrou "
                f"{'carga horaria' if carga_horaria is None else 'todas as datas'}.",
            )
            dados_ia = self.extrator_ia.extract(texto)
            carga_horaria = carga_horaria if carga_horaria is not None else dados_ia.carga_horaria
            datas = datas or dados_ia.datas
        else:
            debug(
                "Extractor",
                "Extracao complementar com IA nao acionada: regex encontrou carga horaria e data.",
            )

        data_emissao = max(datas) if datas else None

        return ExtractedCertificateData(
            text=texto,
            carga_horaria=carga_horaria,
            datas=datas,
            data_emissao=data_emissao,
        )

    def _precisa_ocr(self, texto: str) -> bool:
        return len(normalize_text(texto)) < 30

    def _mesclar_texto(self, original: str, texto_ocr: str) -> str:
        if not original.strip():
            return texto_ocr
        return f"{original}\n{texto_ocr}"
