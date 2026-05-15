import unittest

from core.entities import Atividade
from core.repository import BaremaRepository


class BaremaHoursRulesTest(unittest.TestCase):
    def setUp(self):
        self.repo = BaremaRepository(".")

    def test_extracts_minimum_hours_from_one_day_rule(self):
        self.assertEqual(
            self.repo.extract_min_hours("Maximo de 80h desde que nao seja inferior a 1 dia"),
            12,
        )
        self.assertEqual(
            self.repo.extract_min_hours("Maximo de 80h desde que nao sendo inferior a 1 dia"),
            12,
        )

    def test_extracts_minimum_hours_from_activity_description(self):
        self.assertEqual(
            self.repo.extract_min_hours(
                "Maximo de 50h/ano/atividade",
                "curso com no minimo 12h",
            ),
            12,
        )

    def test_activity_below_minimum_hours_is_not_counted(self):
        atividade = Atividade(
            id="3",
            descricao="Participacao em eventos cientificos relacionados a computacao",
            carga_maxima="Maximo de 80h desde que nao seja inferior a 1 dia",
            max_horas_num=80,
            min_horas_num=12,
        )

        self.assertEqual(atividade.aplicar_limite(10), 0)
        self.assertEqual(atividade.aplicar_limite(12), 12)
        self.assertEqual(atividade.aplicar_limite(90), 80)


if __name__ == "__main__":
    unittest.main()
