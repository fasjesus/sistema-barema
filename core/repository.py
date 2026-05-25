# repository.py
import os
import csv
import re
from typing import Optional, List
from core.entities import Atividade, SolicitacaoAnalise

class BaremaRepository:
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def _normalizar_horas(self, valor: str, unidade: str) -> Optional[float]:
        try:
            numero = float(valor.replace(',', '.'))
        except (AttributeError, ValueError):
            return None

        if unidade and unidade.lower().startswith('dia'):
            return numero * 12
        return numero

    def extract_max_hours(self, carga_maxima_str):
        if not carga_maxima_str: return None
        text_lower = carga_maxima_str.lower()
        # Lógica original: ignora se contiver unidades específicas
        if any(unidade in text_lower for unidade in ['/ano', 'por ano', '/evento', 'por evento', '/semestre', 'por semestre', '/projeto', 'por projeto', '/atividade', 'por atividade']):
            return None 
        
        # Regex original 1: "máximo de X"
        matches = re.findall(r'm[áa]ximo de\s*(\d+)\s*h?', carga_maxima_str, re.IGNORECASE)
        if matches: return max(int(val) for val in matches)
        
        # Regex original 2: "X h" ou "X horas"
        match = re.fullmatch(r'(\d+)\s*h(oras)?\.?', carga_maxima_str.strip(), re.IGNORECASE)
        if match: return int(match.group(1))
        
        return None

    def extract_min_hours(self, *textos):
        texto_completo = " ".join(texto for texto in textos if texto)
        if not texto_completo:
            return None

        patterns = [
            r'n[ãa]o\s+(?:(?:seja|sendo|ser)\s+)?inferior\s+a\s*(\d+(?:[,.]\d+)?)\s*(h|horas?|dias?)?',
            r'no\s+m[íi]nimo\s*(\d+(?:[,.]\d+)?)\s*(h|horas?|dias?)?',
            r'm[íi]nimo\s+de\s*(\d+(?:[,.]\d+)?)\s*(h|horas?|dias?)?',
        ]

        horas_minimas = []
        for pattern in patterns:
            for valor, unidade in re.findall(pattern, texto_completo, re.IGNORECASE):
                horas = self._normalizar_horas(valor, unidade)
                if horas is not None:
                    horas_minimas.append(horas)

        if horas_minimas:
            return max(horas_minimas)

        return None

    def load_atividades(self, tipo_barema: str) -> List[dict]:
        filename = 'barema_novo.csv' if tipo_barema == 'novo' else 'barema_antigo.csv'
        filepath = os.path.join(self.base_dir, 'core','data', filename)
        atividades = []
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as infile:
                reader = csv.DictReader(infile)
                fieldnames = reader.fieldnames
                # Lógica original de fallback para delimitador ';'
                if not fieldnames or not all(key in fieldnames for key in ['id', 'atividade', 'carga_maxima']):
                    infile.seek(0)
                    reader = csv.DictReader(infile, delimiter=';')
                
                for row in reader:
                    row['max_horas_num'] = self.extract_max_hours(row.get('carga_maxima', ''))
                    row['min_horas_num'] = self.extract_min_hours(
                        row.get('carga_maxima', ''),
                        row.get('atividade', '')
                    )
                    atividades.append(row)
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
        return atividades

    def to_entity(self, data: dict) -> Atividade:
        return Atividade(
            id=data.get('id'),
            descricao=data.get('atividade'),
            carga_maxima=data.get('carga_maxima'),
            max_horas_num=data.get('max_horas_num'),
            min_horas_num=data.get('min_horas_num')
        )


class UsuarioRepository:
    def buscar_por_id(self, usuario_id):
        from core.models import Usuario
        from sqlalchemy.exc import SQLAlchemyError

        try:
            return Usuario.query.get(int(usuario_id))
        except SQLAlchemyError:
            return None

    def buscar_por_username(self, username):
        from core.models import Usuario
        from sqlalchemy.exc import SQLAlchemyError

        try:
            return Usuario.query.filter_by(username=username).first()
        except SQLAlchemyError:
            return None


class AnaliseBaremaRepository:
    def listar_ordenadas_por_data(self):
        from core.models import AnaliseBarema

        return AnaliseBarema.query.order_by(AnaliseBarema.data_solicitacao.desc()).all()

    def buscar_modelo_por_id(self, analise_id):
        from core.models import AnaliseBarema

        return AnaliseBarema.query.get(analise_id)

    def criar(self, solicitacao: SolicitacaoAnalise):
        from core.models import AnaliseBarema, db

        analise = AnaliseBarema(
            matricula=solicitacao.estudante.matricula,
            nome_aluno=solicitacao.estudante.nome,
            email_aluno=solicitacao.estudante.email,
            whatsapp_aluno=solicitacao.whatsapp_aluno,
            metodo_preferencial=solicitacao.metodo_preferencial,
            caminho_pdf=solicitacao.caminho_pdf,
            status=solicitacao.status,
            feedback=solicitacao.feedback,
        )
        db.session.add(analise)
        db.session.commit()
        return analise

    def salvar_entidade(self, analise_modelo, solicitacao: SolicitacaoAnalise):
        from core.models import db

        analise_modelo.atualizar_por_entidade(solicitacao)
        db.session.commit()
        return analise_modelo
