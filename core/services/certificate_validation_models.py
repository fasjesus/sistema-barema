from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Protocol


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


@dataclass
class AIValidationResult:
    erros: List[str] = field(default_factory=list)
    irregularidades: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)


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


class AIClient(Protocol):
    def complete_json(self, prompt: str) -> Dict[str, Any]:
        ...
