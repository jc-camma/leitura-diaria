# MBA 15min - Leitura diária com PDF + e-mail

Projeto em Python 3.11+ que gera uma lição diária (Dia 1..365), cria um PDF A4 e envia por e-mail via SMTP com TLS.

## Recursos

- 365 leituras em `data/books_365.json` (dias 1..20 preenchidos; 21..365 placeholders editáveis).
- Geração de lição em português com formato prático de 10-15 minutos.
- Refino opcional com OpenAI quando `OPENAI_API_KEY` estiver configurada.
- Persistência local em JSON (`data/state.json`) sem banco de dados.
- Idempotência diária: não reenvia no mesmo dia sem `--force`.
- CLI para envio, preview e dia específico de teste.
- Compatível com Windows e Linux.

## Estrutura

```text
app/
  __init__.py
  run.py
  lesson.py
  pdf_gen.py
  emailer.py
  state.py
  config.py
data/
  books_365.json
  state.json (gerado automaticamente)
docs/
  SETUP.md
tests/
  test_json_loading.py
  test_state_idempotency.py
  test_pdf_filename.py
  test_emailer_mock.py
out/ (gerado)
```

## CLI

```bash
python -m app.run --preview
python -m app.run --send-now
python -m app.run --send-now --force
python -m app.run --preview --day 12
python -m app.run --send-now --day 12
```

`--day N` gera/envia um dia específico sem alterar o progresso salvo no `state.json`.

## Completar placeholders (dias 21..365)

```bash
python -m app.content_tools --list-placeholders
python -m app.content_tools --export-template 21 > dia21.json
python -m app.content_tools --apply-file dia21.json
```

## Testes

```bash
pytest
```

## Setup completo

Veja [docs/SETUP.md](/c:/Users/Joao/Dev/Leitura%20diária/docs/SETUP.md).
