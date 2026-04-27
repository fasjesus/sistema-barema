import os
from io import BytesIO
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor 
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.utils import ImageReader

class CertificateProcessor:
    @staticmethod
    def get_page_info(current_page: int, file_storage) -> tuple:
        """Lógica original para contar páginas dos certificados."""
        try:
            reader = PdfReader(file_storage)
            count = len(reader.pages)
            file_storage.seek(0)
            intervalo = f"{current_page}-{current_page + count - 1}" if count > 1 else str(current_page)
            return current_page + count, intervalo
        except:
            return current_page + 1, str(current_page)
