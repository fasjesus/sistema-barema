import re
from datetime import date
from typing import List, Optional

from ..certificate_validation_utils import debug, normalize_text


class AnalisadorRegexCertificado:
    PADROES_DATA = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
    ]
    PADRAO_ANO_COM_CONTEXTO = (
        r"(?:emitid[oa]|emissao|expedid[oa]|concluid[oa]|realizad[oa]|"
        r"participou|evento|curso)\D{0,40}((?:19|20)\d{2})"
    )

    def extract_hours(self, texto: str) -> Optional[float]:
        texto_busca = normalize_text(texto)
        padroes = [
            r"(?:carga\s*horaria|ch)\D{0,20}(\d+(?:[,.]\d+)?)\s*h",
            r"(\d+(?:[,.]\d+)?)\s*(?:h|horas?)",
        ]

        for padrao in padroes:
            match = re.search(padrao, texto_busca, re.IGNORECASE)
            if match:
                valor = float(match.group(1).replace(",", "."))
                debug("Regex-Parser", f"Carga horaria extraida: {valor}h.")
                return valor

        debug("Regex-Parser", "Carga horaria nao encontrada.")
        return None

    def extract_dates(self, texto: str) -> List[date]:
        datas = []
        for padrao in self.PADROES_DATA:
            for grupos in re.findall(padrao, texto or ""):
                data_extraida = self._parse_data(grupos)
                if data_extraida:
                    datas.append(data_extraida)

        if not datas:
            texto_normalizado = normalize_text(texto)
            for ano in re.findall(self.PADRAO_ANO_COM_CONTEXTO, texto_normalizado, re.IGNORECASE):
                datas.append(date(int(ano), 12, 31))

        debug("Regex-Parser", f"{len(datas)} data(s) extraida(s).")
        return datas

    def _parse_data(self, grupos: tuple) -> Optional[date]:
        try:
            if len(grupos[0]) == 4:
                ano, mes, dia = map(int, grupos)
            else:
                dia, mes, ano = map(int, grupos)
            return date(ano, mes, dia)
        except ValueError:
            return None
