import os
from io import BytesIO
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor 
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_LEFT
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

class PDFService:
    def __init__(self, logo_uesc, logo_colcic):
        self.logo_uesc = logo_uesc
        self.logo_colcic = logo_colcic

    def gerar_completo(self, processo, certificados):
        capa_buffer = self._desenhar_capa(processo)
        merger = PdfWriter()
        merger.append(capa_buffer)
        for cert in certificados:
            cert.seek(0)
            merger.append(cert)
        
        output = BytesIO()
        merger.write(output)
        output.seek(0)
        return self._adicionar_numeracao(output)

    def _desenhar_capa(self, processo):
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=landscape(A4))
        width, height = landscape(A4)
        y_header = height - 2.5*cm 

        # --- LOGOS  ---
        try:
            # Logo UESC - Esquerda
            img_u = ImageReader(self.logo_uesc)
            h_u = 2*cm 
            w_orig, h_orig = img_u.getSize()
            w_u = (h_u / h_orig) * w_orig
            c.drawImage(img_u, 2*cm, y_header - (h_u / 2), height=h_u, width=w_u, mask='auto', preserveAspectRatio=True)
        except Exception as e:
            print(f"Erro logo UESC: {e}")

        try:
            # Logo COLCIC - Direita
            img_c = ImageReader(self.logo_colcic)
            h_c = 1.5*cm 
            w_orig, h_orig = img_c.getSize()
            w_c = (h_c / h_orig) * w_orig
            # O X é a largura total - margem de 2cm - largura da própria imagem
            x_c = width - 2*cm - w_c 
            c.drawImage(img_c, x_c, y_header - (h_c / 2), height=h_c, width=w_c, mask='auto', preserveAspectRatio=True)
        except Exception as e:
            print(f"Erro logo COLCIC: {e}")

        # --- TÍTULOS ---
        c.setFont("Helvetica", 11)
        c.drawCentredString(width/2, y_header + 0.6*cm, "UNIVERSIDADE ESTADUAL DE SANTA CRUZ - UESC")
        c.drawCentredString(width/2, y_header + 0.1*cm, "COLEGIADO DE CIÊNCIA DA COMPUTAÇÃO - COLCIC")
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width/2, y_header - 0.5*cm, "Barema de Atividades Complementares")
        
        c.setFont("Helvetica-Bold", 10)
        sub = f"(Ingressantes {'a partir de 2023.1' if processo.tipo_barema == 'novo' else 'até 2022.2'})"
        c.drawCentredString(width/2, y_header - 1.0*cm, sub)

        # --- DADOS DO DISCENTE (Com Email - Foto 2) ---
        y_data = y_header - 2.2*cm
        c.setFont("Helvetica", 9)
        c.drawString(1.5*cm, y_data, f"Discente: {processo.estudante.nome}")
        c.drawString(9*cm, y_data, f"Matrícula: {processo.estudante.matricula}")
        c.drawString(14*cm, y_data, f"Email: {processo.estudante.email}")
        c.drawString(22.5*cm, y_data, f"Data: {processo.data_envio}")

        # --- TABELA ---
        x_atv, x_max, x_cum, x_folha, x_end = 1.5*cm, 16*cm, 20.5*cm, 23*cm, width - 1.5*cm
        y_h_top = y_data - 0.8*cm
        y_h_bot = y_h_top - 0.6*cm
        
        c.setStrokeColor(HexColor('#DDDDDD'))
        c.line(x_atv, y_h_top, x_end, y_h_top)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x_atv + 0.2*cm, y_h_top - 0.4*cm, "Atividade")
        c.drawString(x_max + 0.2*cm, y_h_top - 0.4*cm, "C.H. Máxima")
        c.drawString(x_cum + 0.2*cm, y_h_top - 0.4*cm, "C.H. Cumprida")
        c.drawString(x_folha + 0.2*cm, y_h_top - 0.4*cm, "Folha")
        c.line(x_atv, y_h_bot, x_end, y_h_bot)

        styles = getSampleStyleSheet()
        style_atv = ParagraphStyle('A', fontSize=8, leading=10)
        style_sub = ParagraphStyle('S', fontSize=7, leading=8)

        y_pos = y_h_bot - 0.5*cm
        total_h = 0

        for item in processo.itens:
           
            val_h = int(item.horas_validas)
            h_str = str(val_h) if val_h > 0 else ""
            
            p_atv = Paragraph(f"{item.atividade.id}. {item.atividade.descricao}", style_atv)
            p_max = Paragraph(item.atividade.carga_maxima, style_sub)
            p_fol = Paragraph(item.intervalo_paginas, style_sub)

            h_p = p_atv.wrapOn(c, (x_max - x_atv) - 0.4*cm, height)[1]
            h_m = p_max.wrapOn(c, (x_cum - x_max) - 0.4*cm, height)[1]
            h_f = p_fol.wrapOn(c, (x_end - x_folha) - 0.4*cm, height)[1]

            line_h = max(h_p, h_m, h_f)
            if y_pos - line_h < 1.5*cm: break

            p_atv.drawOn(c, x_atv + 0.2*cm, y_pos - h_p)
            p_max.drawOn(c, x_max + 0.2*cm, y_pos - h_m)
            c.setFont("Helvetica", 7)
            c.drawString(x_cum + 0.5*cm, y_pos - 8, h_str)
            p_fol.drawOn(c, x_folha + 0.2*cm, y_pos - 8 - (h_f - 7))

            y_pos -= (line_h + 0.3*cm)
            c.line(x_atv, y_pos + 0.15*cm, x_end, y_pos + 0.15*cm)
            total_h += val_h

        # Bordas Verticais
        y_bot_final = y_pos + 0.15*cm
        for x in [x_atv, x_max, x_cum, x_folha, x_end]:
            c.line(x, y_h_top, x, y_bot_final)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_cum - 1*cm, y_pos - 0.6*cm, f"TOTAL HORAS: {total_h}")
        c.save()
        packet.seek(0)
        return packet

    def _adicionar_numeracao(self, stream):
       
        reader = PdfReader(stream)
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            p_num = BytesIO()
            can = canvas.Canvas(p_num, pagesize=(page.mediabox.width, page.mediabox.height))
            can.setFont("Helvetica", 8)
            can.drawRightString(float(page.mediabox.width) - 20, 20, f"Página {i+1} de {len(reader.pages)}")
            can.save()
            p_num.seek(0)
            page.merge_page(PdfReader(p_num).pages[0])
            writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        out.seek(0)
        return out