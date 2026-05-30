import os
from io import BytesIO
from typing import Iterable, Optional

from ..certificate_validation_utils import debug

try:
    import fitz
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None


def _flag_ambiente(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return str(valor).strip().lower() in {"1", "true", "yes", "on"}


def _inteiro_ambiente(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, str(padrao)) or padrao)
    except ValueError:
        return padrao


class ExtratorOCR:
    def __init__(
        self,
        habilitado: bool = True,
        idioma: str = "por+eng",
        dpi: int = 220,
        max_paginas: int = 5,
        comando_tesseract: Optional[str] = None,
        enabled: Optional[bool] = None,
        language: Optional[str] = None,
        max_pages: Optional[int] = None,
        tesseract_cmd: Optional[str] = None,
    ):
        if enabled is not None:
            habilitado = enabled
        if language is not None:
            idioma = language
        if max_pages is not None:
            max_paginas = max_pages
        if tesseract_cmd is not None:
            comando_tesseract = tesseract_cmd

        self.habilitado = habilitado
        self.idioma = idioma
        self.dpi = dpi
        self.max_paginas = max_paginas
        self.comando_tesseract = comando_tesseract
        self.enabled = habilitado
        self.language = idioma
        self.max_pages = max_paginas
        self.tesseract_cmd = comando_tesseract

    @classmethod
    def from_env(cls):
        return cls(
            habilitado=_flag_ambiente("CERTIFICATE_OCR_ENABLED", True),
            idioma=os.getenv("CERTIFICATE_OCR_LANG", "por+eng"),
            dpi=_inteiro_ambiente("CERTIFICATE_OCR_DPI", 220),
            max_paginas=_inteiro_ambiente("CERTIFICATE_OCR_MAX_PAGES", 5),
            comando_tesseract=os.getenv("TESSERACT_CMD") or None,
        )

    def extract(self, conteudo: bytes) -> str:
        if not self.habilitado:
            debug("OCR-Extractor", "OCR desabilitado por CERTIFICATE_OCR_ENABLED.")
            return ""
        if pytesseract is None:
            debug("OCR-Extractor", "pytesseract nao instalado; OCR indisponivel.")
            return ""
        if Image is None:
            debug("OCR-Extractor", "Pillow nao instalado; OCR indisponivel.")
            return ""
        if self.comando_tesseract:
            pytesseract.pytesseract.tesseract_cmd = self.comando_tesseract

        textos = []
        for imagem in self._imagens_do_conteudo(conteudo):
            texto = self._imagem_para_texto(imagem)
            if texto.strip():
                textos.append(texto)

        if textos:
            debug("OCR-Extractor", f"OCR extraiu texto de {len(textos)} pagina(s)/imagem(ns).")
        else:
            debug("OCR-Extractor", "OCR nao encontrou texto no certificado.")
        return "\n".join(textos)

    def _imagens_do_conteudo(self, conteudo: bytes) -> Iterable:
        if conteudo.lstrip().startswith(b"%PDF"):
            yield from self._imagens_do_pdf(conteudo)
            return
        imagem = self._imagem_dos_bytes(conteudo)
        if imagem is not None:
            yield imagem

    def _imagens_do_pdf(self, conteudo: bytes) -> Iterable:
        if fitz is None:
            debug("OCR-Extractor", "PyMuPDF nao instalado; nao foi possivel rasterizar PDF para OCR.")
            return
        try:
            with fitz.open(stream=conteudo, filetype="pdf") as documento:
                escala = self.dpi / 72
                matriz = fitz.Matrix(escala, escala)
                for indice in range(min(len(documento), self.max_paginas)):
                    pagina = documento[indice]
                    pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)
                    if Image is None:
                        return
                    yield Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        except Exception as exc:
            debug("OCR-Extractor", f"Falha ao preparar PDF para OCR: {exc}")

    def _imagem_dos_bytes(self, conteudo: bytes):
        try:
            imagem = Image.open(BytesIO(conteudo))
            return imagem.convert("RGB")
        except Exception as exc:
            debug("OCR-Extractor", f"Arquivo nao pode ser lido como imagem para OCR: {exc}")
            return None

    def _imagem_para_texto(self, imagem) -> str:
        try:
            return pytesseract.image_to_string(imagem, lang=self.idioma)
        except Exception as exc:
            if self.idioma != "eng":
                debug("OCR-Extractor", f"OCR com idioma '{self.idioma}' falhou: {exc}. Tentando eng.")
                try:
                    return pytesseract.image_to_string(imagem, lang="eng")
                except Exception as fallback_exc:
                    debug("OCR-Extractor", f"OCR com idioma 'eng' tambem falhou: {fallback_exc}")
                    return ""
            debug("OCR-Extractor", f"OCR falhou: {exc}")
            return ""
