from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Atividade:
    id: str
    descricao: str
    carga_maxima: str
    max_horas_num: Optional[float] = None # Mudado para float para suportar limites quebrados

    def aplicar_limite(self, horas_solicitadas: float) -> float:
        
        if self.max_horas_num is not None and horas_solicitadas > self.max_horas_num:
            return self.max_horas_num
        return horas_solicitadas


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
    def horas_solicitadas(self) -> float:
        """Apenas higieniza e converte o que o aluno digitou."""
        if not self.horas_input:
            return 0.0
        try:
            # Proteção extra: caso o aluno digite "10,5" em vez de "10.5"
            val = self.horas_input.replace(',', '.')
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @property
    def horas_validas(self) -> float:
       
        return self.atividade.aplicar_limite(self.horas_solicitadas)


@dataclass
class ProcessoBarema:
    estudante: Estudante
    tipo_barema: str
    data_envio: str
    itens: List[ItemBarema] = field(default_factory=list)

    def adicionar_item(self, item: ItemBarema):
        self.itens.append(item)

    @property
    def total_horas(self) -> float:
        
        return sum(item.horas_validas for item in self.itens)