from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Atividade:
    id: str
    descricao: str
    carga_maxima: str
    max_horas_num: Optional[int] = None

@dataclass
class Estudante:
    nome: str
    matricula: str
    email: str

@dataclass
class ItemBarema:
    atividade: Atividade
    horas_input: str  # String bruta do formulário
    tipo_barema: str
    intervalo_paginas: str = ""

    @property
    def horas_validas(self) -> float:
        """Lógica de trava de 100h para o Barema Antigo."""
        try:
            val = float(self.horas_input) if self.horas_input else 0.0
        except (ValueError, TypeError):
            val = 0.0
            
        if self.tipo_barema == 'antigo' and str(self.atividade.id) == '1':
            if val > 100:
                return 100.0
        return val

@dataclass
class ProcessoBarema:
    estudante: Estudante
    tipo_barema: str
    data_envio: str
    itens: List[ItemBarema] = field(default_factory=list)

    def adicionar_item(self, item: ItemBarema):
        self.itens.append(item)