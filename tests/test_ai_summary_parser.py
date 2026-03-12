from app.lesson import BookEntry
from app.main import _lesson_from_ai_summary_text


def test_ai_summary_parser_builds_lesson() -> None:
    entry = BookEntry(
        day=1,
        title="Habitos Atomicos",
        author="James Clear",
        theme="Construcao de habitos consistentes",
        key_ideas=[
            "Pequenas melhorias diarias geram crescimento composto.",
            "Ambiente desenhado supera motivacao eventual.",
            "Identidade guia comportamento sustentavel.",
            "Sistemas vencem metas isoladas.",
            "Rastreamento visual reforca consistencia.",
        ],
        practical_applications=[
            "Definir um habito minimo de 2 minutos para comecar hoje.",
            "Remover um atrito fisico de uma tarefa importante.",
            "Registrar a execucao do habito por 7 dias consecutivos.",
        ],
        reflection_question="Qual identidade profissional voce quer reforcar com um habito diario simples?",
        optional_quote="Voce nao sobe ao nivel das metas; cai ao nivel dos sistemas.",
    )

    text = """
TITULO DO LIVRO
Habitos Atomicos
Autor
James Clear
Tema principal
Construcao de habitos consistentes

1. Ideia central
O livro mostra que pequenas mudancas diarias se acumulam e alteram resultados de longo prazo.
Tambem explica que o foco deve estar no sistema e nao apenas na meta.

2. Por que este livro importa
A obra ganhou relevancia por traduzir ciencia comportamental em linguagem simples e acionavel.

3. Conceitos fundamentais do livro
Conceito: Crescimento composto
Explicacao: Pequenos ganhos repetidos viram grandes ganhos no longo prazo.
Exemplo: Melhorar 1% por dia em uma habilidade.

Conceito: Design de ambiente
Explicacao: O ambiente facilita ou atrapalha o habito.
Exemplo: Deixar o livro visivel e o celular longe na hora de estudar.

Conceito: Identidade
Explicacao: O habito se sustenta quando reforca quem voce quer ser.
Exemplo: Treinar diariamente para reforcar a identidade de pessoa saudavel.

Conceito: Sistemas
Explicacao: Metas definem direcao, sistemas sustentam execucao.
Exemplo: Escrever 300 palavras por dia em vez de pensar apenas no livro pronto.

Conceito: Rastreamento
Explicacao: Medir execucao aumenta consistencia.
Exemplo: Marcar no calendario os dias cumpridos.

4. Modelo mental ou estrutura apresentada pelo autor
As quatro leis da mudanca de comportamento organizam como criar habitos melhores.

5. Exemplo ou historia marcante do livro
A estrategia de ganhos marginais no ciclismo britanico ilustra o poder do ajuste incremental.

6. Aplicacao pratica
1. Definir um habito de dois minutos para iniciar.
2. Ajustar o ambiente para reduzir atrito.
3. Registrar execucao diaria por uma semana.

7. Limitacoes ou criticas possiveis
A abordagem pode ser lenta para contextos que exigem mudancas imediatas.

8. Sintese final
A principal licao e que progresso sustentavel vem de repeticao consistente, nao de motivacao pontual.
""".strip()

    lesson = _lesson_from_ai_summary_text(entry, text)
    assert lesson is not None
    assert "pequenas mudancas diarias" in lesson.central_idea.lower()
    assert len(lesson.concepts) >= 5
    assert lesson.concepts[0].startswith("1. Crescimento composto")
    assert len(lesson.practical_applications) >= 3
    assert any("A obra ganhou relevancia" in item for item in lesson.guided_reading)
    assert not any(item.startswith("2. Por que este livro importa") for item in lesson.guided_reading)


def test_ai_summary_parser_keeps_full_section_6_content() -> None:
    entry = BookEntry(
        day=4,
        title="Trabalho Focado",
        author="Cal Newport",
        theme="Concentracao profunda e produtividade",
        key_ideas=["I1", "I2", "I3", "I4", "I5"],
        practical_applications=["A1", "A2", "A3"],
        reflection_question="Como proteger blocos de foco?",
        optional_quote=None,
    )

    text = """
1. Ideia central
Texto central suficiente para o parser.

2. Por que este livro importa
Contexto da obra.

3. Conceitos fundamentais do livro
Conceito: Trabalho profundo
Explicacao: Foco sem distracoes.
Exemplo: Blocos de 90 minutos.

Conceito: Ritual de inicio
Explicacao: Sinaliza inicio de concentracao.
Exemplo: Preparar ambiente antes de iniciar.

Conceito: Planejamento
Explicacao: Agenda blocos de foco.
Exemplo: Reservar manha para tarefas cognitivas.

Conceito: Gestao de distracoes
Explicacao: Reduz interrupcoes frequentes.
Exemplo: Desligar notificacoes no horario critico.

Conceito: Revisao semanal
Explicacao: Ajusta estrategia de execucao.
Exemplo: Revisar agenda e resultados da semana.

4. Modelo mental ou estrutura apresentada pelo autor
Modelo de blocos de concentracao.

5. Exemplo ou historia marcante do livro
Exemplo pratico de rotina de foco.

6. Aplicacao pratica
Aqui estão algumas ações práticas que podem ser implementadas já na próxima semana:

1. **Bloquear 90 minutos de trabalho sem notificações:** Reserve um período fixo no dia para tarefa de alta prioridade
   e mantenha o celular fora do alcance.
2. **Definir um ritual fixo de início:** Use sempre o mesmo gatilho para iniciar tarefa complexa, como uma breve caminhada ou preparação do ambiente.
3. **Encerrar o dia com checklist:** Liste no fim do dia as prioridades do próximo dia para iniciar com clareza.

7. Limitacoes ou criticas possiveis
Pode ser dificil em ambientes com alta interrupcao.

8. Sintese final
A licao principal e proteger tempo de foco para trabalho cognitivo.
""".strip()

    lesson = _lesson_from_ai_summary_text(entry, text)
    assert lesson is not None
    assert any(section == "6. Aplicacao pratica" for section in lesson.guided_reading)
    assert any(section.startswith("a. Bloquear 90 minutos") for section in lesson.guided_reading)
    assert any(section == "3. Conceitos fundamentais do livro" for section in lesson.guided_reading)
    assert any(section.startswith("a. Trabalho profundo") for section in lesson.guided_reading)
    assert any("Bloquear 90 minutos" in item for item in lesson.practical_applications)
    assert any("mantenha o celular fora do alcance" in item for item in lesson.practical_applications)
    assert all("**" not in item for item in lesson.concepts)
    assert all("**" not in item for item in lesson.practical_applications)


def test_ai_summary_parser_keeps_more_than_five_concepts() -> None:
    entry = BookEntry(
        day=9,
        title="Livro",
        author="Autor",
        theme="Tema",
        key_ideas=["K1", "K2", "K3", "K4", "K5", "K6"],
        practical_applications=["A1", "A2", "A3"],
        reflection_question="Pergunta?",
        optional_quote=None,
    )
    concepts_block = "\n\n".join(
        [
            (
                f"Conceito: Conceito {idx}\n"
                f"Explicacao: Explicacao do conceito {idx} com contexto aplicado.\n"
                f"Exemplo: Exemplo pratico do conceito {idx}."
            )
            for idx in range(1, 7)
        ]
    )
    text = (
        "1. Ideia central\nTexto base.\n\n"
        "2. Por que este livro importa\nContexto.\n\n"
        "3. Conceitos fundamentais do livro\n"
        f"{concepts_block}\n\n"
        "4. Modelo mental ou estrutura apresentada pelo autor\nModelo.\n\n"
        "5. Exemplo ou historia marcante do livro\nExemplo.\n\n"
        "6. Aplicacao pratica\n1. Acao um detalhada.\n2. Acao dois detalhada.\n3. Acao tres detalhada.\n\n"
        "7. Limitacoes ou criticas possiveis\nLimites.\n\n"
        "8. Sintese final\nSintese."
    )

    lesson = _lesson_from_ai_summary_text(entry, text)
    assert lesson is not None
    assert len(lesson.concepts) == 6
    assert lesson.concepts[-1].startswith("6. Conceito 6")
