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
* **`core/services/`**: Camada lógica que processa certificados, pré-valida dados e gera PDFs com `ReportLab`.

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
│   └── services/        # Processamento de PDF, extração e pré-validação
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
Para garantir que as regras de horas e a pré-validação de certificados estão funcionando:

```bash
python -m unittest tests.test_processor
python -m unittest discover -s tests
```

Se `pytest` estiver instalado no ambiente, também é possível rodar:

```bash
python -m pytest tests
```

---

## Extração e Pré-Validação de Certificados

A extração de dados e a pré-validação são funcionalidades separadas.

### Extração de dados

O ponto central da extração fica em `core/services/validation_processor.py`.

* `CertificateDataExtractor.extract(content)` recebe os bytes do PDF.
* `PyMuPDFTextExtractor.extract(content)` tenta extrair o texto com PyMuPDF.
* Se o PyMuPDF não conseguir ler o texto, o extrator tenta o fallback com `pypdf`.
* `RegexCertificateParser` interpreta o texto extraído e procura carga horária e datas.
* O resultado é um `ExtractedCertificateData`, que mantém `text`, `carga_horaria`, `datas` e `data_emissao`.

Nesta etapa, QR Code não participa da extração. O campo `qr_urls` permanece no objeto por compatibilidade, mas o fluxo atual não preenche nem usa esse dado.

### Pré-validação básica

A pré-validação básica também fica em `core/services/validation_processor.py`, mas em outra responsabilidade:

* `BasicCertificatePreValidator.validate_certificate(...)` valida um certificado isolado.
* `BasicCertificatePreValidator.validate_activity_hours(...)` valida a soma de horas dos certificados de uma mesma atividade.
* `CertificateValidationProcessor` funciona como fachada e coordena extração + pré-validação.

As regras por certificado são:

* o nome informado pelo aluno deve aparecer no texto extraído do certificado;
* a carga horária precisa ser encontrada;
* quando a atividade tiver carga mínima, o certificado precisa atender esse mínimo;
* qualquer data anterior ao ano de ingresso do aluno gera irregularidade.

A regra por atividade soma as cargas horárias extraídas de todos os certificados enviados naquela categoria e compara essa soma com a carga cumprida informada no formulário. Se o aluno solicita 50h em eventos e envia certificados de 20h e 30h, a pré-validação considera 50h comprovadas. Se solicita 50h e os certificados somam 30h, a atividade recebe irregularidade.

### Fluxo no sistema

1. `routes/aluno_routes.py` recebe os arquivos enviados em uma atividade.
2. A rota conta as páginas dos certificados para montar os anexos.
3. A rota chama `CertificateValidationProcessor.validate_activity(...)` com todos os certificados daquela atividade.
4. O processador extrai os dados de cada PDF.
5. O pré-validador verifica cada certificado e depois a soma de horas da atividade.
6. As mensagens retornadas viram `observacoes` do `ItemBarema`.
7. `PDFService` escreve essas observações no barema gerado.

QR Code e IA são estratégias futuras de pré-validação e devem ser implementadas como caminhos separados. No fluxo atual, a pré-validação é simples, local e baseada apenas nos dados extraídos do PDF.

### Processo TDD

O módulo foi ajustado com TDD:

1. Os testes de `tests/test_processor.py` foram reescritos primeiro para expressar o novo contrato.
2. A primeira execução falhou porque `CertificateDataExtractor` e o novo fluxo por atividade ainda não existiam.
3. A implementação foi feita até os testes ficarem verdes.
4. A suíte foi rodada novamente para confirmar o comportamento.

Os cenários cobertos incluem extração de carga horária e datas, certificado válido sem QR/IA, nome divergente, carga horária ausente, carga abaixo do mínimo, data anterior ao ingresso, soma de múltiplos certificados na mesma atividade e garantia de que o processador atual não chama o detector de QR Code.
