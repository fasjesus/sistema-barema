# Gerador de Barema de Atividades Complementares - UESC

Este projeto e uma ferramenta web para o **Colegiado de Ciencia da Computacao (COLCIC/UESC)**. O sistema permite que discentes montem automaticamente o PDF do barema de atividades complementares, anexem certificados, recebam uma pre-validacao das informacoes e, quando desejado, solicitem uma analise previa da coordenacao.

## Como executar

### 1. Requisitos

- Python 3.8 ou superior.
- Evite Python 3.14+, pois ja foram observados problemas de compatibilidade com algumas dependencias.

### 2. Variaveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
SECRET_KEY=sua-chave
SENHA_ADMIN_DEV=senha
SENHA_COORDENADOR=senha
```

As integracoes externas sao opcionais:

```env
SENDGRID_API_KEY=sua-chave
EMAIL_FROM=email@exemplo.com
TWILIO_ACCOUNT_SID=sua-sid
TWILIO_AUTH_TOKEN=seu-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+5500000000000
```

O OCR para certificados digitalizados tambem e opcional. Para usar essa etapa,
instale o Tesseract OCR no sistema operacional e, se necessario, informe o
caminho do executavel:

```env
CERTIFICATE_OCR_ENABLED=1
CERTIFICATE_OCR_LANG=por+eng
CERTIFICATE_OCR_DPI=220
CERTIFICATE_OCR_MAX_PAGES=5
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### 3. Ambiente virtual e dependencias

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Banco de dados e usuarios iniciais

```bash
flask db upgrade
python seed.py
```

O script `seed.py` cria:

- `admin_dev`, com cargo `admin`;
- `colcic`, com cargo `coordenador`.

### 5. Execucao em desenvolvimento

```bash
python app.py
```

O servidor fica disponivel em `http://127.0.0.1:5000`.

## Arquitetura

O projeto usa uma organizacao em camadas inspirada em MVC:

- **Views:** templates Jinja2 em `templates/`.
- **Controllers:** blueprints e `MethodView` em `routes/`.
- **Dominio:** entidades puras em `core/entities.py`.
- **Persistencia:** modelos SQLAlchemy em `core/models.py`.
- **Repositorios:** leitura de CSVs e acesso ao banco em `core/repository.py`.
- **Servicos:** regras de aplicacao, PDF, validacao, IA e notificacoes em `core/services/`.

### Entidades de dominio

`core/entities.py` concentra classes que representam conceitos do sistema sem depender de Flask ou SQLAlchemy:

- `Atividade`: regra de uma atividade complementar e seus limites de horas.
- `Estudante`: dados do discente que monta o barema.
- `ItemBarema`: atividade preenchida pelo discente, com horas, paginas e observacoes.
- `ProcessoBarema`: conjunto de itens de um barema de um estudante.
- `Usuario`: usuario autenticado da area administrativa, com cargo `admin` ou `coordenador`.
- `SolicitacaoAnalise`: pedido de analise previa feito pelo discente, incluindo status e parecer.

Essa separacao torna o diagrama de classes mais fiel ao dominio: o estudante usa o fluxo publico sem login, enquanto o coordenador e um usuario autenticado que pode registrar pareceres sobre solicitacoes.

### Modelos de persistencia

`core/models.py` contem as tabelas SQLAlchemy:

- `Usuario`: persistencia de login, senha com hash e cargo.
- `AnaliseBarema`: persistencia das solicitacoes enviadas por discentes.

Os modelos possuem metodos de conversao para entidades de dominio, evitando que regras importantes fiquem presas apenas ao ORM.

### Repositorios

`core/repository.py` encapsula acesso a dados:

- `BaremaRepository`: le CSVs de regras do barema e cria entidades `Atividade`.
- `UsuarioRepository`: busca usuarios para autenticacao e carregamento de sessao.
- `AnaliseBaremaRepository`: lista, cria e atualiza solicitacoes de analise no banco.


### Servicos de aplicacao

`core/services/analise_barema_service.py` centraliza o fluxo administrativo da analise:

- registra uma nova `SolicitacaoAnalise`;
- lista solicitacoes para o painel do coordenador;
- registra parecer apenas quando o usuario autenticado tem cargo de coordenador;
- atualiza status para `Analisado`;
- dispara notificacao por e-mail/WhatsApp quando configurado.


## Fluxo principal

1. O discente acessa a tela inicial.
2. Informa nome, matricula e e-mail.
3. A matricula define automaticamente o tipo de barema.
4. O discente informa horas e anexa certificados por atividade.
5. O sistema pre-valida certificados, horas e possiveis irregularidades.
6. O `PDFService` gera o PDF consolidado.
7. Opcionalmente, o discente solicita analise previa da coordenacao.
8. A coordenacao acessa o painel autenticado e registra parecer.
9. O sistema atualiza a solicitacao e tenta notificar o discente.

## Testes

Execute a suite completa:

```bash
python -m unittest discover -s tests
```

Testes relevantes desta versao:

- regras de horas e pre-validacao de certificados;
- limitacao de tentativas de login;
- entidades de dominio `Usuario` e `SolicitacaoAnalise`;
- servico de registro de parecer da coordenacao.

## Estrutura de arquivos

```text
core/
  data/                 Regras do barema em CSV
  entities.py           Entidades de dominio
  models.py             Modelos SQLAlchemy
  repository.py         Repositorios de CSV, usuarios e analises
  services/             PDF, validacao, IA, notificacao e analise
routes/                 Controllers Flask
templates/              Views Jinja2
static/                 CSS, JS, imagens e uploads
migrations/             Migracoes Alembic/Flask-Migrate
tests/                  Testes automatizados
documentation/          Documentacao e arquivos do TCC
```

