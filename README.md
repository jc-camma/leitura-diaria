# MBA 15min - leitura diaria com PDF e e-mail

Projeto em Python 3.11+ para gerar uma leitura diaria (Dia 1..365) com analise academica via OpenAI, salvar texto bruto e exportar PDF com links de confirmacao/proxima leitura.

## Setup rapido (venv)

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuracao (.env)

Use `.env.example` como base:

```env
SMTP_HOST=smtp.seuprovedor.com
SMTP_PORT=587
SMTP_USER=seu_usuario_smtp
SMTP_PASS=sua_senha_ou_app_password
EMAIL_FROM=seu_email@dominio.com
EMAIL_TO=destinatario@dominio.com

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1

YOUTUBE_API_KEY=

# Opcional: URL publica base para confirmar a leitura por link no e-mail e no PDF
# Exemplo: https://seu-dominio.com/leitura
READ_CONFIRM_BASE_URL=
```

## Pipeline

Ordem do pipeline:

1. Gera/reusa catalogo anual de livros relevantes por area
2. Carrega livro do dia
3. Faz 1 chamada OpenAI com analise academica
4. Salva texto bruto em `.md` e `.txt` (sem parser de resumo)
5. Gera PDF direto desse texto (com links de video/confirmacao/proxima leitura)
6. Envia e-mail por SMTP (quando `--send-now`)

## Estrutura principal

```text
app/
  analysis.py
  catalog.py
  main.py
  models.py
  pdf_raw.py
  read_feedback.py
  run.py
  mailer.py
  config.py
  youtube.py
  emailer.py
  state.py
data/
  books_365.json
docs/
  SETUP.md
tests/
out/
```

## Uso CLI

```bash
python -m app.run --preview
python -m app.run --send-now
python -m app.run --send-now --force
python -m app.run --preview --day 12
python -m app.run --send-now --day 12
python -m app.run --mark-last-read
python -m app.run --serve-feedback --host 0.0.0.0 --port 8000
```

Comandos adicionais:

```bash
python -m app.run --preview --day 18 --catalog-year 2026
python -m app.run --preview --catalog-year 2026 --rebuild-catalog
```

`--day N` gera/envia um dia especifico sem alterar o progresso salvo no `state.json`.

Se houver uma leitura pendente ainda nao confirmada como lida, o proximo `--send-now` fica bloqueado ate a confirmacao. Essa confirmacao pode acontecer de duas formas:

- Link no e-mail e no PDF: configure `READ_CONFIRM_BASE_URL` e rode `python -m app.run --serve-feedback` em um host acessivel. O mesmo e-mail/PDF tambem pode trazer um segundo link para enviar a proxima leitura imediatamente.
- Confirmacao manual: rode `python -m app.run --mark-last-read`.

## Testes

```bash
pytest
```

Setup detalhado: [docs/SETUP.md](docs/SETUP.md)

## Apoie o projeto

Se este projeto te ajudou e voce quiser contribuir com um trocado:

- GitHub Sponsors: https://github.com/sponsors/jc-camma
- Botao "Sponsor" no repositorio (quando habilitado pelo GitHub)

## Licenca

Este projeto esta sob a licenca MIT. Veja [LICENSE](LICENSE).
