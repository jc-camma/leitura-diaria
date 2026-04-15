# Setup Completo (Windows + Linux)

## 1) Pre-requisitos

- Python 3.11 ou superior
- Conta SMTP valida (Gmail, Outlook ou outro provedor com TLS)

## 2) Criar e ativar venv

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## 3) Configurar `.env`

Crie o arquivo `.env` na raiz do projeto com base no `.env.example`:

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
READ_CONFIRM_BASE_URL=
```

## 4) Execucao manual

Preview (gera PDF sem enviar):

```bash
python -m app.run --preview
```

Envio imediato:

```bash
python -m app.run --send-now
```

Forcar reenvio no mesmo dia:

```bash
python -m app.run --send-now --force
```

Teste de dia especifico sem alterar estado:

```bash
python -m app.run --send-now --day 7
python -m app.run --preview --day 7
```

Marcar a leitura pendente atual como lida:

```bash
python -m app.run --mark-last-read
```

## 5) Agendamento Linux (cron as 07:00)

Abra o crontab:

```bash
crontab -e
```

Adicione a linha (ajuste o caminho):

```cron
0 7 * * * cd /caminho/para/projeto && /caminho/para/projeto/.venv/bin/python -m app.run --send-now >> /caminho/para/projeto/out/cron.log 2>&1
```

## 6) Agendamento Windows (Task Scheduler as 07:00)

### Opcao GUI

1. Abra `Task Scheduler`.
2. Crie `Create Task...`.
3. Trigger: Daily, 07:00.
4. Action: Start a program.
5. Program/script: caminho para `python.exe` da venv, ex.: `C:\Users\SeuUsuario\Dev\Projeto\.venv\Scripts\python.exe`
6. Add arguments: `-m app.run --send-now`
7. Start in: pasta raiz do projeto.

### Opcao via `schtasks`

```powershell
schtasks /Create /SC DAILY /ST 07:00 /TN "MBA15min" /TR "\"C:\Users\SeuUsuario\Dev\Projeto\.venv\Scripts\python.exe\" -m app.run --send-now" /F
```

## 7) SMTP (Gmail / Outlook generico)

### Gmail

- Host: `smtp.gmail.com`
- Port: `587`
- TLS: sim
- Usuario: seu e-mail Gmail
- Senha: use `App Password` (com 2FA), nao a senha normal da conta.

### Outlook / Microsoft 365

- Host: `smtp.office365.com`
- Port: `587`
- TLS: sim
- Usuario: e-mail completo
- Senha: senha da conta ou app password/politica corporativa.

## 8) Estado e idempotencia

- Estado salvo em `data/state.json`.
- Se ja enviou no dia atual, o script nao reenvia.
- Se a ultima leitura ainda nao foi confirmada como lida, o proximo envio fica bloqueado.
- `--force` permite reenviar no mesmo dia sem avancar o indice.
- `--day N` nao altera o estado (modo de teste).

## 9) Confirmacao de leitura por link

- Configure `READ_CONFIRM_BASE_URL` com uma URL publica base, por exemplo `https://seu-dominio.com/leitura`.
- Inicie o servidor HTTP de confirmacao:

```bash
python -m app.run --serve-feedback --host 0.0.0.0 --port 8000
```

- O e-mail e o PDF passarao a incluir um link do tipo `/confirm-read?token=...`.
- Quando o link for acessado, a leitura atual sera marcada como lida.
- Se quiser continuar no mesmo dia, o e-mail e o PDF tambem podem incluir um link `/send-next-reading?token=...`, que confirma a leitura atual e envia a proxima imediatamente.
- Depois disso, o proximo `--send-now` volta a ficar liberado quando a leitura pendente mais recente for confirmada.

## 10) Regenerar catalogo balanceado

Gerar novamente o `books_365.json` com a curadoria balanceada de ficcao, filosofia, psicologia, economia, geopolitica e outras categorias:

```bash
python -m app.content_tools --rebalance-catalog
```

Se quiser inspecionar se ainda existe algum placeholder residual:

```bash
python -m app.content_tools --list-placeholders
```

## 11) Ajustar um dia especifico manualmente

Exportar template de um dia:

```bash
python -m app.content_tools --export-template 21 > dia21.json
```

Editar `dia21.json` e aplicar:

```bash
python -m app.content_tools --apply-file dia21.json
```
