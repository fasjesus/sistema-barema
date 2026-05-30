from io import BytesIO

from ..certificate_validation_utils import debug

try:
    import fitz
except ImportError:
    fitz = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


class ExtratorTextoPDF:
    def extract(self, conteudo: bytes) -> str:
        if not conteudo.lstrip().startswith(b"%PDF"):
            debug("Text-Extractor", "Arquivo nao e PDF; extracao textual direta pulada.")
            return ""

        if fitz is not None:
            try:
                with fitz.open(stream=conteudo, filetype="pdf") as documento:
                    texto = "\n".join(pagina.get_text() for pagina in documento)
                    debug("Text-Extractor", "Texto extraido com PyMuPDF.")
                    return texto
            except Exception as exc:
                debug("Text-Extractor", f"PyMuPDF nao conseguiu extrair texto: {exc}")

        if PdfReader is not None:
            try:
                leitor = PdfReader(BytesIO(conteudo))
                texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
                debug("Text-Extractor", "Texto extraido com pypdf.")
                return texto
            except Exception as exc:
                debug("Text-Extractor", f"pypdf nao conseguiu extrair texto: {exc}")

        debug("Text-Extractor", "Nenhuma biblioteca de extracao disponivel ou arquivo sem texto.")
        return ""
