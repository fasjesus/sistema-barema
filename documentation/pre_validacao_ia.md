# Pre-validacao com IA

Esta etapa usa IA como uma camada opcional depois da pre-validacao basica.
A validacao basica continua local e deterministica para nome, carga horaria,
datas, soma de horas e certificados duplicados na mesma atividade.

## Objetivo da IA

A IA atua em duas etapas opcionais.

Na extracao, ela complementa os dados quando a regex local nao encontra carga
horaria ou datas. A resposta esperada e JSON estrito:

```json
{"carga_horaria": null, "datas": [], "data_emissao": null}
```

Na pre-validacao, ela analisa apenas sinais subjetivos ou mais textuais, como:

- se o certificado parece minimamente compativel com a atividade do barema;
- se ha inconsistencias evidentes no texto extraido;
- se vale a pena gerar um aviso para conferencia manual.

O prompt nao envia o PDF inteiro. A classe `CertificateAIPromptOptimizer`
monta um payload compacto com:

- dados essenciais do aluno;
- regra da atividade;
- carga horaria e datas ja extraidas;
- trecho reduzido do texto do certificado;
- lista curta de checks que a IA deve executar.

A extracao local continua sendo a primeira tentativa. A IA so entra como
fallback para campos ausentes, economizando tokens e mantendo o sistema
funcional mesmo sem provedor de IA.

## Provedores

A implementacao usa um provedor configuravel por `.env`.

```env
CERTIFICATE_AI_ENABLED=0
CERTIFICATE_AI_PROVIDER=none
CERTIFICATE_AI_MAX_TEXT_CHARS=2400
```

Os provedores suportados sao:

- `none`: nao chama IA e usa apenas a pre-validacao basica.
- `openai_compatible`: usa qualquer API compativel com `/chat/completions`.
- `ollama`: alias de compatibilidade que usa a API OpenAI-compatible do Ollama.

Se a IA estiver desativada, mal configurada ou indisponivel, a pre-validacao
basica continua funcionando.

## Configuracao generica

Para qualquer provedor que implemente o formato de Chat Completions, como
Ollama, Groq, OpenRouter, Together, DeepSeek, LM Studio, vLLM ou gateways
internos:

```env
CERTIFICATE_AI_ENABLED=1
CERTIFICATE_AI_PROVIDER=openai_compatible
AI_API_KEY=sua-chave-real
AI_BASE_URL=https://api.exemplo.com/v1
AI_MODEL=nome-do-modelo
AI_TIMEOUT=45
CERTIFICATE_AI_MAX_TEXT_CHARS=2400
```

Esse modo envia `Authorization: Bearer <AI_API_KEY>` para
`<AI_BASE_URL>/chat/completions` e espera resposta JSON em
`choices[0].message.content`.

## Ollama local

Instale e execute o Ollama localmente. Depois baixe um modelo pequeno o
suficiente para sua maquina, por exemplo:

```powershell
ollama pull llama3.2:3b
```

No `.env`, habilite a IA usando a configuracao generica:

```env
CERTIFICATE_AI_ENABLED=1
CERTIFICATE_AI_PROVIDER=openai_compatible
AI_API_KEY=ollama
AI_BASE_URL=http://localhost:11434/v1
AI_MODEL=llama3.2:3b
AI_TIMEOUT=45
CERTIFICATE_AI_MAX_TEXT_CHARS=2400
```

O valor `AI_API_KEY=ollama` e exigido pelo formato OpenAI-compatible, mas o
Ollama ignora essa chave.

## Arquivos principais

- `core/services/certificate_extraction_service.py`: extracao de texto, horas e datas.
- `core/services/certificate_pre_validation_service.py`: regras basicas e duplicidade.
- `core/services/certificate_ai_validation_service.py`: otimizador de prompt, fabrica de provedores e clientes IA.
- `core/services/validation_processor.py`: fachada que coordena as etapas.

## Testes

```powershell
python -m unittest discover -s tests
```
