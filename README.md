# 📑 Gerador de Barema de Atividades Complementares v1.0.0 - UESC

Este projeto é uma ferramenta para o **Colegiado de Ciência da Computação (COLCIC/UESC)**, permitindo que discentes gerem automaticamente o PDF do Barema de Atividades Complementares, anexando e numerando os certificados de forma organizada. Esta versão adiciona um feedback da coordenação ao documento gerado pelo aluno.

## 🚀 Como Executar o Projeto

### 1. Requisitos Prévios
Certifique-se de ter o Python 3.8+ instalado em sua máquina. Obs: não use o Python 3.14+, foi constatado problemas com o uso dessa versão.

### 2. Configuração do Ambiente Virtual (Recomendado)
No terminal, dentro da pasta do projeto, execute:

```bash
# Cria o ambiente virtual
python -m venv venv

# Ativa o ambiente (Windows)
venv\Scripts\activate

# Ativa o ambiente (Linux/Mac)
source venv/bin/activate
```

### 3. Instalação de Dependências
Com o ambiente ativo, instale os pacotes necessários listados no seu arquivo `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Execução em Modo de Desenvolvimento
Para testar localmente com recarregamento automático (hot-reload):

```bash
python app.py
```
O servidor estará disponível em: `http://127.0.0.1:5000`

### 5. Execução em Produção (WSGI)
Como o projeto possui um arquivo `wsgi.py`, você deve usar um servidor de aplicação como o **Gunicorn** (Linux) ou **Waitress** (Windows):

**No Linux (Gunicorn):**
```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:8000 wsgi:app
```

---

## 🏗️ Arquitetura do Projeto (POO)

O projeto foi refatorado seguindo os princípios de **Clean Architecture** e **Programação Orientada a Objetos**, dividindo as responsabilidades em camadas:

* **`core/entities.py`**: Contém as regras de domínio (`Estudante`, `Atividade`, `ItemBarema`).
* **`core/repository.py`**: Responsável pela persistência e leitura dos dados (CSV).
* **`core/services.py`**: Camada lógica que processa os PDFs e manipula o `ReportLab`.
* **`app.py`**: Controlador Flask que gerencia as rotas e injeção de dependências.
* **`wsgi.py`**: Ponto de entrada para servidores de produção.

---

## 🛠️ Tecnologias Utilizadas

* **Python 3**
* **Flask**: Micro-framework web.
* **ReportLab**: Geração de gráficos e textos em PDF.
* **PyPDF (pypdf)**: Manipulação, junção e contagem de páginas de arquivos PDF.
* **Pandas/CSV**: Gerenciamento das tabelas de atividades.

---

## 📂 Estrutura de Arquivos

```text
├── core/                # Lógica de Negócio (POO)
├── static/              # Ativos estáticos (Logos UESC/COLCIC)
├── templates/           # Interface do usuário (HTML/JinJa2)
├── app.py               # Orquestrador das rotas Flask
├── wsgi.py              # Entrada para servidor de produção
├── barema_antigo.csv    # Regras para ingressantes até 2022.2
└── barema_novo.csv      # Regras para ingressantes a partir de 2023.1
└── database.py                # Banco de Dados
```

---

### 🧪 Rodando Testes Unitários
Para garantir que as regras de horas máximas e contagem de páginas estão funcionando:

```bash
pip install pytest
pytest tests/
```
