# repository.py
import os
import csv
import re
from typing import Optional, List
from core.entities import Atividade

class BaremaRepository:
    def __init__(self, base_dir):
        self.base_dir = base_dir

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
                    atividades.append(row)
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
        return atividades

    def to_entity(self, data: dict) -> Atividade:
        return Atividade(
            id=data.get('id'),
            descricao=data.get('atividade'),
            carga_maxima=data.get('carga_maxima'),
            max_horas_num=data.get('max_horas_num')
        )