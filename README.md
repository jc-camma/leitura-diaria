# MBA 15min - leitura diaria com PDF e e-mail

Projeto em Python 3.11+ para gerar uma leitura diaria (Dia 1..365), refinar editorialmente o texto em duas passagens (local + OpenAI), validar qualidade, exportar PDF e enviar por SMTP.

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
OPENAI_MODEL=gpt-4.1-mini

YOUTUBE_API_KEY=

# Opcional: URL publica base para confirmar a leitura por link no e-mail e no PDF
# Exemplo: https://seu-dominio.com/leitura
READ_CONFIRM_BASE_URL=
```

## Pipeline

Ordem do pipeline:

1. `reading_plan.py` seleciona o livro do dia
2. `generator.py` gera rascunho
3. `refiner.py` aplica refino local anti-repeticao
4. `openai_refiner.py` aplica refino editorial OpenAI
5. `quality.py` valida heuristicas de qualidade
6. `formatter.py` preserva estrutura/secoes
7. `pdf_exporter.py` gera PDF
8. `mailer.py` envia e-mail

## Estrutura principal

```text
app/
  main.py
  run.py
  reading_plan.py
  generator.py
  lesson.py
  refiner.py
  openai_refiner.py
  quality.py
  formatter.py
  pdf_exporter.py
  mailer.py
  config.py
  utils.py
  youtube.py
  pdf_gen.py
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

`--day N` gera/envia um dia especifico sem alterar o progresso salvo no `state.json`.

Se houver uma leitura pendente ainda nao confirmada como lida, o proximo `--send-now` fica bloqueado ate a confirmacao. Essa confirmacao pode acontecer de duas formas:

- Link no e-mail e no PDF: configure `READ_CONFIRM_BASE_URL` e rode `python -m app.run --serve-feedback` em um host acessivel.
- Confirmacao manual: rode `python -m app.run --mark-last-read`.

## Testes

```bash
pytest
```

Smoke test da camada editorial (before/after):

```bash
python -c "from app.lesson import load_books,get_entry_for_day; from app.config import runtime_paths; from app.main import refinement_smoke_test; p=runtime_paths(); entry=get_entry_for_day(load_books(p.data_file),1); refinement_smoke_test(entry, p.openai_api_key, p.openai_model)"
```

Setup detalhado: [docs/SETUP.md](docs/SETUP.md)

## Apoie o projeto

Se este projeto te ajudou e voce quiser contribuir com um trocado:

- GitHub Sponsors: https://github.com/sponsors/jc-camma
- Botao "Sponsor" no repositorio (quando habilitado pelo GitHub)

## Licenca

Este projeto esta sob a licenca MIT. Veja [LICENSE](LICENSE).
