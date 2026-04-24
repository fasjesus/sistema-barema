# 📑 Gerador de Barema de Atividades Complementares v1.0.0 - UESC

Este projeto é uma ferramenta para o **Colegiado de Ciência da Computação (COLCIC/UESC)**, permitindo que discentes gerem automaticamente o PDF do Barema de Atividades Complementares, anexando e numerando os certificados de forma organizada. Esta versão adiciona um feedback da coordenação ao documento gerado pelo aluno.

## 🚀 Como Executar o Projeto

### 1. Requisitos Prévios
Certifique-se de ter o Python 3.8+ instalado em sua máquina. Obs: não use o Python 3.14+, foi constatado problemas com o uso dessa versão.

### 2. Configuração das Variáveis de Ambiente (.env)
Antes de iniciar, crie um ficheiro chamado `.env` na raiz do projeto e adicione as seguintes chaves (estas informações são ignoradas pelo Git por segurança):

```env
SECRET_KEY=sua-chave
SENHA_ADMIN_DEV=senha
SENHA_COORDENADOR=senha
``` 

### 3. Configuração do Ambiente Virtual (Recomendado)
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
### 3. Configurar Banco de Dados (Migrations)

```bash
flask db upgrade
```

### 4. Semear utilizadores iniciais (Admin e Coordenador)
```bash
python seed.py
```

### 5. Execução em Modo de Desenvolvimento
Para testar localmente com recarregamento automático (hot-reload):

```bash
python app.py
```
O servidor estará disponível em: `http://127.0.0.1:5000`

### 6. Execução em Produção (WSGI)
Como o projeto possui um arquivo `wsgi.py`, você deve usar um servidor de aplicação como o **Gunicorn** (Linux) ou **Waitress** (Windows):

**No Linux (Gunicorn):**
```bash
pip install gunicorn
gunicorn --bind 0.0.0.0:8000 wsgi:app
```

---

## 🏗️ Arquitetura do Projeto (POO)

O projeto foi refatorado seguindo os princípios de **Clean Architecture** e **Programação Orientada a Objetos**, dividindo as responsabilidades em camadas:

### Camada Core (Domínio e Lógica)

* **`core/entities.py`**: Contém as regras de domínio (`Estudante`, `Atividade`, `ItemBarema`).
* **`core/models.py`**: Definição do esquema da base de dados via `SQLAlchemy`.
* **`core/repository.py`**: Abstração da leitura de dados externos (CSVs) e conversão para entidades.
* **`core/services.py`**: Camada lógica que processa os PDFs e manipula o `ReportLab`.

### Camada de Entrega (Web)

* Blueprints & MethodViews: As rotas foram modularizadas por domínio (aluno, coordenador, auth) utilizando Class-Based Views, permitindo o uso de herança para controlo de acesso (RBAC).

* Migrations: Controlo de versão da base de dados utilizando Flask-Migrate.

## 🛠️ Tecnologias Utilizadas

* **Python 3**
* **Flask**: Micro-framework web.
* **SQLAlchemy**: Banco de Dados SQLite com SQLAlchemy (ORM).
* **Flask-Migrate (Alembic)**: Migrações.
* **Flask-Login**: (Gestão de sessão) e Werkzeug (Hashing de passwords).
* **Flask-Admin**: Interface de gestão da base de dados.
* **ReportLab**: Geração de gráficos e textos em PDF.
* **PyPDF (pypdf)**: Manipulação, junção e contagem de páginas de arquivos PDF.
* **Pandas/CSV**: Gerenciamento das tabelas de atividades.

---

## 📂 Estrutura de Arquivos
```
├── core/
│   ├── data/            # Arquivos CSV (Regras do Barema)
│   ├── entities.py      # Entidades de Domínio
│   ├── models.py        # Modelos da Base de Dados
│   ├── repository.py    # Repositórios de Dados
│   └── services.py      # Lógica de processamento de PDF
├── migrations/          # Histórico de versões da Base de Dados
├── routes/              # Controladores (Blueprints & MethodViews)
├── static/              # CSS, JS, Imagens e Uploads (Ignorados no Git)
├── templates/           # Visões (Jinja2 HTML)
├── app.py               # Inicializador e registo de Blueprints
├── seed.py              # Script de população inicial da base de dados
└── wsgi.py              # Entrada para produção
```

---

### 🧪 Rodando Testes Unitários
Para garantir que as regras de horas máximas e contagem de páginas estão funcionando:

```bash
pip install pytest
pytest tests/
```
