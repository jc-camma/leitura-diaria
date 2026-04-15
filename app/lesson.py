from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookEntry:
    day: int
    title: str
    author: str
    theme: str
    key_ideas: list[str]
    practical_applications: list[str]
    reflection_question: str
    category: str | None = None
    optional_quote: str | None = None


@dataclass(frozen=True)
class Lesson:
    day: int
    title: str
    author: str
    theme: str
    central_idea: str
    concepts: list[str]
    practical_applications: list[str]
    reflection_question: str
    guided_reading: list[str]
    summary_bullets: list[str]
    optional_quote: str | None = None

    def word_count(self) -> int:
        text_parts: list[str] = [
            self.central_idea,
            self.reflection_question,
            *self.concepts,
            *self.practical_applications,
            *self.guided_reading,
            *(self.summary_bullets or []),
        ]
        if self.optional_quote:
            text_parts.append(self.optional_quote)
        return sum(len(part.split()) for part in text_parts)


def load_books(path: Path) -> list[BookEntry]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    books = [BookEntry(**item) for item in payload]
    if len(books) != 365:
        raise ValueError("books_365.json precisa conter exatamente 365 itens.")

    days = {item.day for item in books}
    expected_days = set(range(1, 366))
    if days != expected_days:
        raise ValueError("books_365.json precisa ter dias de 1 a 365 sem lacunas.")
    return sorted(books, key=lambda item: item.day)


def get_entry_for_day(books: list[BookEntry], day: int) -> BookEntry:
    if day < 1 or day > 365:
        raise ValueError("Dia precisa estar entre 1 e 365.")
    return books[day - 1]


def generate_first_draft(entry: BookEntry) -> Lesson:
    if entry.category:
        return _build_category_aware_lesson(entry)
    return _build_base_lesson(entry)


def build_lesson(
    entry: BookEntry,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4.1-mini",
) -> Lesson:
    from app.formatter import lesson_from_refinement_text, lesson_to_refinement_text, normalize_lesson_lists
    from app.openai_refiner import refine_text_with_openai
    from app.quality import evaluate_lesson_quality
    from app.refiner import refine_lesson_local

    draft = generate_first_draft(entry)
    locally_refined = normalize_lesson_lists(refine_lesson_local(draft))

    candidate = locally_refined
    if openai_api_key:
        previous_key = os.getenv("OPENAI_API_KEY")
        previous_model = os.getenv("OPENAI_MODEL")
        try:
            os.environ["OPENAI_API_KEY"] = openai_api_key
            os.environ["OPENAI_MODEL"] = openai_model
            serialized = lesson_to_refinement_text(locally_refined)
            ai_refined_text = refine_text_with_openai(serialized)
            parsed = lesson_from_refinement_text(locally_refined, ai_refined_text)
            if parsed is None:
                logger.warning("Refino OpenAI retornou estrutura invalida; mantendo versao local.")
            else:
                candidate = normalize_lesson_lists(parsed)
        finally:
            if previous_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_key
            if previous_model is None:
                os.environ.pop("OPENAI_MODEL", None)
            else:
                os.environ["OPENAI_MODEL"] = previous_model

    report = evaluate_lesson_quality(candidate)
    _log_quality_issues(report.issues)
    if report.has_blocking_errors:
        logger.warning("Qualidade bloqueante detectada; usando versao local refinada.")
        candidate = locally_refined

    min_words = min(900, locally_refined.word_count())
    if candidate.word_count() < min_words:
        logger.warning(
            "Refino final ficou curto demais (%s palavras); mantendo versao local.",
            candidate.word_count(),
        )
        return locally_refined

    if candidate.word_count() > 1600:
        logger.warning("Refino final excedeu 1600 palavras; mantendo versao local.")
        return locally_refined
    return candidate


def _build_category_aware_lesson(entry: BookEntry) -> Lesson:
    ideas = _ensure_length(entry.key_ideas, 1, "Conceito essencial")
    applications = _ensure_length(entry.practical_applications, 3, "Aplicacao pratica recomendada")
    concepts = [f"{idx}. {idea}" for idx, idea in enumerate(ideas, start=1)]
    practical = [f"{idx}. {app}" for idx, app in enumerate(applications[:3], start=1)]
    guided_reading = _build_category_guided_reading(entry, ideas)
    summary = [
        f"Tese central: {entry.theme}.",
        f"Categoria de leitura: {entry.category}.",
        f"Sintese critica: {_category_summary_line(entry.category)}",
    ]
    central = _build_category_central_idea(entry)

    lesson = Lesson(
        day=entry.day,
        title=entry.title,
        author=entry.author,
        theme=entry.theme,
        central_idea=central,
        concepts=concepts,
        practical_applications=practical,
        reflection_question=entry.reflection_question.strip(),
        guided_reading=guided_reading,
        summary_bullets=summary,
        optional_quote=entry.optional_quote.strip() if entry.optional_quote else None,
    )
    return _ensure_target_word_count_generic(lesson)


def _category_family(category: str | None) -> str:
    lowered = (category or "").lower()
    if "ficcao" in lowered:
        return "fiction"
    if "filosofia" in lowered:
        return "philosophy"
    if "psicologia" in lowered:
        return "psychology"
    if "economia" in lowered:
        return "economy"
    if "geopolitica" in lowered:
        return "geopolitics"
    if "historia" in lowered:
        return "history"
    if "ciencia" in lowered:
        return "science"
    if "sociologia" in lowered:
        return "sociology"
    if "biografia" in lowered or "memorias" in lowered:
        return "biography"
    return "strategy"


def _build_category_central_idea(entry: BookEntry) -> str:
    family = _category_family(entry.category)
    if family == "fiction":
        return (
            f"\"{entry.title}\", de {entry.author}, trabalha \"{entry.theme}\" por meio de personagens, "
            "conflito e atmosfera. Em vez de oferecer uma tese direta, a obra transforma dilemas humanos "
            "em experiencia concreta: desejos colidem com regras, afetos esbarram em estruturas sociais e "
            "cada escolha revela custo moral, simbolico ou politico. Ler bem este livro significa observar "
            "como forma narrativa, voz e contexto historico ampliam o sentido do enredo e ajudam o leitor a "
            "reconhecer no presente problemas que a ficcao torna mais visiveis."
        )
    if family == "philosophy":
        return (
            f"\"{entry.title}\", de {entry.author}, toma \"{entry.theme}\" como problema filosofico central. "
            "A obra nao pede adesao apressada, mas leitura paciente de premissas, distincoes conceituais e "
            "implicacoes praticas. O valor do texto esta em obrigar o leitor a sair de opinioes vagas e a "
            "formular melhor perguntas sobre verdade, dever, liberdade, poder ou sentido. A leitura conecta "
            "conceito abstrato e decisao concreta, transformando argumento em criterio de julgamento."
        )
    if family == "psychology":
        return (
            f"\"{entry.title}\", de {entry.author}, organiza \"{entry.theme}\" como problema de comportamento, "
            "percepcao e contexto. A obra interessa porque aproxima mecanismo mental e vida real: vieses, "
            "emocao, memoria, relacoes e ambiente deixam de ser intuicoes soltas e passam a ser observados "
            "como padroes. Em vez de prometer mudanca magica, o livro convida o leitor a identificar gatilhos, "
            "efeitos e limites, usando a psicologia como instrumento de leitura mais precisa de si e dos outros."
        )
    if family == "economy":
        return (
            f"\"{entry.title}\", de {entry.author}, examina \"{entry.theme}\" a partir de incentivos, instituicoes "
            "e distribuicao de custos e beneficios. O livro ajuda a trocar julgamento moral rapido por analise "
            "de mecanismos: quem decide, quem captura valor, quem assume risco e quais efeitos indiretos surgem "
            "ao longo do tempo. A leitura fica mais util quando teoria, historia e politica publica sao ligadas "
            "a casos concretos, permitindo olhar o debate economico com menos slogan e mais estrutura."
        )
    if family == "geopolitics":
        return (
            f"\"{entry.title}\", de {entry.author}, aborda \"{entry.theme}\" como problema de poder, territorio "
            "e ordem internacional. Em geopolitica, declaracoes publicas importam menos do que capacidade material, "
            "restricoes geograficas, percepcao de risco e memoria historica. A obra ajuda a separar narrativa "
            "diplomatica de interesse estrategico e mostra por que rivalidades persistem mesmo quando todos dizem "
            "buscar estabilidade. Ler este livro e treinar a leitura de atores, incentivos e escalas de conflito."
        )
    if family == "history":
        return (
            f"\"{entry.title}\", de {entry.author}, ilumina \"{entry.theme}\" ao reconstruir processos de longa "
            "duracao, rupturas e permanencias institucionais. O livro mostra que historia nao e acumulacao de fatos, "
            "mas interpretacao de causas, ritmos e estruturas que continuam agindo no presente. A leitura ganha "
            "forca quando o leitor resiste ao presentismo facil e aprende a comparar epocas sem apagar diferencas. "
            "Assim, o passado vira repertorio para interpretar mudancas atuais com mais profundidade."
        )
    if family == "science":
        return (
            f"\"{entry.title}\", de {entry.author}, organiza \"{entry.theme}\" em torno de evidencia, metodo e "
            "limite de inferencia. O ganho da leitura esta em aprender a perguntar melhor: quais dados sustentam "
            "a conclusao, que modelo esta por tras da explicacao e onde a incerteza ainda precisa ser respeitada. "
            "Em temas cientificos e sistemicos, a clareza nasce menos de respostas instantaneas e mais da capacidade "
            "de distinguir observacao, interpretacao e efeito colateral."
        )
    if family == "sociology":
        return (
            f"\"{entry.title}\", de {entry.author}, observa \"{entry.theme}\" como producao social de normas, "
            "papel, linguagem e poder. O livro desloca o olhar do caso individual para a estrutura: aquilo que "
            "parece natural, privado ou espontaneo passa a ser visto como resultado de instituicoes, hierarquias "
            "e disputas simbolicas. A leitura ajuda a transformar indignacao difusa em pergunta analitica mais "
            "forte, mostrando como cultura e organizacao social moldam comportamento e oportunidade."
        )
    if family == "biography":
        return (
            f"\"{entry.title}\", de {entry.author}, trata \"{entry.theme}\" por meio de uma vida concreta e de "
            "seus encontros com contexto, limite e oportunidade. Biografias e memorias funcionam bem quando o "
            "leitor evita tanto a idolatria quanto o cinismo: o importante e observar escolha, consequencia, "
            "contradicao e custo. A obra ajuda a converter experiencia singular em criterio de vida, trabalho e "
            "julgamento, sem transformar trajetoria excepcional em receita simplista."
        )
    return (
        f"\"{entry.title}\", de {entry.author}, aborda \"{entry.theme}\" como problema de foco, decisao e "
        "execucao. A leitura mostra que resultado consistente depende menos de impulso isolado e mais de "
        "prioridade clara, criterio de escolha, rotina observavel e revisao continua. Em vez de repetir "
        "frases motivacionais, a obra ajuda o leitor a ligar ideia e metodo, transformando principio abstrato "
        "em acao verificavel no trabalho e na vida."
    )


def _build_category_guided_reading(entry: BookEntry, ideas: list[str]) -> list[str]:
    family = _category_family(entry.category)
    intros = {
        "fiction": (
            f"Conceitos centrais de \"{entry.title}\": a obra usa \"{entry.theme}\" para organizar conflito, "
            "voz narrativa e tensao moral. Ler ficcao com mais proveito significa perguntar o que a historia "
            "revela sobre personagem, contexto, simbolo e permanencia do dilema no presente."
        ),
        "philosophy": (
            f"Conceitos centrais de \"{entry.title}\": o texto parte de \"{entry.theme}\" para construir um "
            "problema conceitual. A leitura rende mais quando cada bloco e examinado por definicao, argumento, "
            "exemplo, limite e implicacao pratica."
        ),
        "psychology": (
            f"Conceitos centrais de \"{entry.title}\": o livro usa \"{entry.theme}\" para ligar mente, contexto "
            "e comportamento observavel. A leitura fica mais util quando cada conceito e tratado por mecanismo, "
            "gatilho, exemplo cotidiano e teste pratico."
        ),
        "economy": (
            f"Conceitos centrais de \"{entry.title}\": a obra parte de \"{entry.theme}\" para mostrar como "
            "incentivos, restricoes e instituicoes alteram decisao e distribuicao de resultados."
        ),
        "geopolitics": (
            f"Conceitos centrais de \"{entry.title}\": o livro trabalha \"{entry.theme}\" relacionando atores, "
            "territorio, recursos, equilibrio de poder e risco de escalada."
        ),
        "history": (
            f"Conceitos centrais de \"{entry.title}\": a leitura examina \"{entry.theme}\" por processo, "
            "contexto, causalidade e permanencias institucionais."
        ),
        "science": (
            f"Conceitos centrais de \"{entry.title}\": o texto usa \"{entry.theme}\" para treinar leitura de "
            "evidencia, limite metodologico e efeitos sistemicos."
        ),
        "sociology": (
            f"Conceitos centrais de \"{entry.title}\": o livro observa \"{entry.theme}\" como efeito de norma, "
            "linguagem, instituicao e disputa por prestigio, reconhecimento ou controle."
        ),
        "biography": (
            f"Conceitos centrais de \"{entry.title}\": a obra ilumina \"{entry.theme}\" por escolhas, perdas, "
            "contexto historico e revisoes de rumo na vida narrada."
        ),
        "strategy": (
            f"Conceitos centrais de \"{entry.title}\": o livro parte de \"{entry.theme}\" para mostrar como "
            "prioridade, execucao e revisao criam resultado mais consistente que intensidade ocasional."
        ),
    }
    paragraphs = [intros[family]]
    anchors = _ensure_length(entry.practical_applications, 3, "Aplicacao pratica recomendada")
    for idx, idea in enumerate(ideas, start=1):
        anchor = anchors[(idx - 1) % len(anchors)]
        paragraphs.append(_build_concept_explainer(entry.title, idea, idx, anchor, family=family))
    endings = {
        "fiction": "Resumo em uma frase: grandes obras de ficcao sobrevivem porque transformam conflito historico em pergunta humana recorrente.",
        "philosophy": "Resumo em uma frase: filosofia vale quando melhora o rigor das perguntas que orientam vida, etica e politica.",
        "psychology": "Resumo em uma frase: compreender mecanismo e contexto reduz autoengano e melhora a qualidade da acao.",
        "economy": "Resumo em uma frase: pensar economicamente e enxergar incentivo, restricao e efeito indireto antes de julgar resultado.",
        "geopolitics": "Resumo em uma frase: ordem internacional e equilibrio instavel entre poder, geografia, percepcao de risco e negociacao.",
        "history": "Resumo em uma frase: o passado ensina menos por analogia rapida e mais por estrutura, contexto e sequencia causal.",
        "science": "Resumo em uma frase: pensar cientificamente e sustentar curiosidade com metodo, evidencia e respeito ao limite da inferencia.",
        "sociology": "Resumo em uma frase: ver o social e tornar visivel a estrutura que organiza comportamentos aparentemente privados.",
        "biography": "Resumo em uma frase: vidas concretas ensinam criterio quando observamos contexto, escolha e custo sem mitificar o personagem.",
        "strategy": "Resumo em uma frase: execucao consistente nasce de prioridade clara, critico simples e revisao continua.",
    }
    paragraphs.append(endings[family])
    return paragraphs


def _category_summary_line(category: str | None) -> str:
    family = _category_family(category)
    lines = {
        "fiction": "a obra literaria ilumina o presente ao encenar conflitos permanentes em forma narrativa.",
        "philosophy": "o texto melhora a qualidade do juizo ao exigir definicao, argumento e exame de premissas.",
        "psychology": "o livro ganha valor quando transforma mecanismo mental em observacao concreta de comportamento.",
        "economy": "a leitura ajuda a enxergar incentivos, restricoes e efeitos indiretos com mais rigor.",
        "geopolitics": "a obra mostra como poder, geografia e risco moldam escolhas internacionais.",
        "history": "o passado deixa de ser arquivo e vira estrutura para interpretar mudancas do presente.",
        "science": "a principal licao e pensar com evidencia, modelo explicativo e respeito a incerteza.",
        "sociology": "o texto revela estruturas invisiveis que organizam status, comportamento e oportunidade.",
        "biography": "a trajetoria narrada converte experiencia singular em criterio de vida e julgamento.",
        "strategy": "resultado sustentavel depende de foco, metodo e aprendizagem deliberada.",
    }
    return lines[family]


def _build_base_lesson(entry: BookEntry) -> Lesson:
    ideas = _ensure_length(entry.key_ideas, 1, "Conceito essencial")
    applications = _ensure_length(entry.practical_applications, 3, "Aplicacao pratica recomendada")
    concepts = [f"{idx}. {idea}" for idx, idea in enumerate(ideas, start=1)]
    practical = [f"{idx}. {app}" for idx, app in enumerate(applications[:3], start=1)]
    guided_reading = _build_guided_reading(entry, ideas)
    summary = [
        f"Tese central: {entry.theme}.",
        f"Eixo conceitual dominante: {ideas[0]}.",
        "Sintese critica: progresso consistente supera mudancas bruscas.",
    ]
    central = (
        f"\"{entry.title}\", de {entry.author}, aborda \"{entry.theme}\" de forma direta: "
        "resultados grandes surgem da repeticao de pequenas decisoes corretas. Em vez de depender "
        "de motivacao intensa ou de mudancas radicais, o livro mostra um caminho de melhoria "
        "incremental, com foco em sistema, constancia e ajuste continuo. A leitura conecta ideia, "
        "mecanismo e aplicacao pratica, ajudando o leitor a transformar principio abstrato em rotina "
        "observavel no dia a dia."
    )

    lesson = Lesson(
        day=entry.day,
        title=entry.title,
        author=entry.author,
        theme=entry.theme,
        central_idea=central,
        concepts=concepts,
        practical_applications=practical,
        reflection_question=entry.reflection_question.strip(),
        guided_reading=guided_reading,
        summary_bullets=summary,
        optional_quote=entry.optional_quote.strip() if entry.optional_quote else None,
    )

    return _ensure_target_word_count(lesson)


def _build_guided_reading(entry: BookEntry, ideas: list[str]) -> list[str]:
    paragraphs: list[str] = []
    paragraphs.append(
        f"Conceitos centrais de \"{entry.title}\": o livro parte de \"{entry.theme}\" para mostrar "
        "que o resultado final e consequencia do processo repetido. A leitura fica mais util quando "
        "cada conceito e tratado com quatro perguntas: o que significa, por que funciona, como aparece "
        "na pratica e qual passo concreto voce pode testar hoje."
    )
    anchors = _ensure_length(entry.practical_applications, 3, "Aplicacao pratica recomendada")
    for idx, idea in enumerate(ideas, start=1):
        anchor = anchors[(idx - 1) % len(anchors)]
        paragraphs.append(_build_concept_explainer(entry.title, idea, idx, anchor))
    paragraphs.append(
        "Resumo em uma frase: desempenho consistente raramente nasce de uma decisao heroica; ele surge "
        "da soma de pequenas melhorias praticadas por tempo suficiente para gerar efeito composto."
    )
    return paragraphs


def _build_concept_explainer(title: str, idea: str, idx: int, anchor: str, family: str = "strategy") -> str:
    clean_idea = idea.strip().rstrip(".")
    lowered = clean_idea.lower()

    if family == "strategy" and idx == 1 and _looks_like_compound_growth_idea(lowered):
        return (
            f"Conceito {idx} de {title}: {clean_idea}. Esse conceito e um dos pilares da obra. "
            "A logica e simples: pequenas melhorias diarias se acumulam e criam um salto de resultado "
            "ao longo do tempo, de forma parecida com juros compostos. Exemplo numerico classico: "
            "1.01^365 ~= 37, enquanto 0.99^365 ~= 0.03. Em outras palavras, pequenas escolhas positivas "
            "repetidas elevam desempenho, e pequenas escolhas negativas repetidas corroem progresso. "
            f"Passo pratico de hoje: {anchor}"
        )

    openings = [
        f"Conceito {idx} de {title}",
        f"Seguindo o raciocinio do livro, o conceito {idx}",
        f"Ja no conceito {idx}",
        f"No conceito {idx}",
        f"Por fim, no conceito {idx}",
    ]
    opening = openings[(idx - 1) % len(openings)]
    mechanism = _concept_mechanism_hint(lowered, family=family)
    example = _concept_example_hint(lowered, family=family)
    action_label = "Exercicio de leitura de hoje" if family in {"fiction", "philosophy", "history", "biography"} else "Passo pratico de hoje"

    return (
        f"{opening}: {clean_idea}. Em linguagem direta, {mechanism} "
        f"Exemplo pratico: {example} {action_label}: {anchor}"
    )


def _looks_like_compound_growth_idea(idea: str) -> bool:
    triggers = ["melhoria", "crescimento composto", "acumul", "1%", "composto"]
    return any(token in idea for token in triggers)


def _concept_mechanism_hint(idea: str, family: str = "strategy") -> str:
    if "ambiente" in idea:
        return (
            "o ambiente reduz ou aumenta atrito para o comportamento. Quando a acao desejada fica "
            "visivel, simples e acessivel, a execucao depende menos de motivacao momentanea."
        )
    if "identidade" in idea:
        return (
            "o comportamento tende a se manter quando reforca a identidade que a pessoa quer construir. "
            "A pergunta deixa de ser 'o que eu quero atingir' e vira 'quem eu quero me tornar'."
        )
    if "sistema" in idea or "meta" in idea:
        return (
            "metas apontam direcao, mas sistema define repeticao. Sem rotina clara, o objetivo vira "
            "intencao; com rotina, vira progresso mensuravel."
        )
    if "rastreamento" in idea or "visual" in idea:
        return (
            "feedback visual imediato aumenta consistencia, porque torna a execucao observavel e ajuda "
            "a interromper quedas antes que virem padrao."
        )
    family_hints = {
        "fiction": (
            "o conflito literario transforma essa ideia em experiencia concreta e mostra como desejo, medo, "
            "instituicao e contexto social moldam as escolhas."
        ),
        "philosophy": (
            "o conceito organiza uma pergunta filosofica central e ajuda a testar definicoes, premissas e "
            "limites do argumento."
        ),
        "psychology": (
            "o principio liga percepcao, emocao, contexto e comportamento, permitindo observar padroes antes "
            "de tirar conclusoes precipitadas."
        ),
        "economy": (
            "a ideia ganha forca quando observada em incentivo, restricao, distribuicao de risco e desenho "
            "institucional."
        ),
        "geopolitics": (
            "o conceito aparece na disputa entre poder, territorio, aliancas, recursos e percepcao de ameaca."
        ),
        "history": (
            "o principio fica mais claro quando colocado em sequencia causal, contexto institucional e mudanca "
            "de longa duracao."
        ),
        "science": (
            "o ponto central e ligar evidencia, metodo, modelo explicativo e limite de inferencia em vez de "
            "confiar apenas em autoridade ou intuicao."
        ),
        "sociology": (
            "o conceito mostra como norma, linguagem, classe, genero, raca, midia ou instituicao moldam o que "
            "parece escolha individual."
        ),
        "biography": (
            "a ideia ganha densidade quando observada em escolhas, custos, revisoes de rumo e oportunidades da "
            "trajetoria narrada."
        ),
    }
    if family in family_hints:
        return family_hints[family]
    return (
        "o principio transforma uma ideia ampla em comportamento repetivel. A forca do conceito aparece "
        "quando ele e aplicado em ciclos curtos de teste, medicao e ajuste."
    )


def _concept_example_hint(idea: str, family: str = "strategy") -> str:
    if "ambiente" in idea:
        return (
            "deixar livro na mesa e celular fora do alcance na hora de estudar aumenta a chance de leitura "
            "sem exigir disciplina heroica."
        )
    if "identidade" in idea:
        return (
            "quem quer ser 'uma pessoa saudavel' pode manter um treino curto diario, mesmo em dias corridos, "
            "para reforcar esse auto-conceito."
        )
    if "sistema" in idea or "meta" in idea:
        return (
            "em vez de focar em 'escrever um livro', definir 300 palavras por dia cria progresso estavel e "
            "acumulativo."
        )
    if "rastreamento" in idea or "visual" in idea:
        return "marcar um calendario apos cada execucao do habito ajuda a manter sequencia e detectar recaidas."
    family_hints = {
        "fiction": (
            "mapear uma decisao critica de personagem e perguntar qual medo, desejo ou pressao social guiou a cena."
        ),
        "philosophy": (
            "escrever sua posicao inicial sobre o problema do capitulo e depois testar se ela resiste aos argumentos do autor."
        ),
        "psychology": (
            "observar um episodio real da semana e registrar gatilho, resposta e consequencia ajuda a ver o mecanismo em acao."
        ),
        "economy": (
            "comparar uma politica, investimento ou regra de mercado pelos incentivos que cria para cada parte envolvida."
        ),
        "geopolitics": (
            "ler um conflito atual listando atores, recursos, restricoes geograficas e risco de escalada melhora a interpretacao."
        ),
        "history": (
            "reconstruir uma cadeia curta de causa e efeito antes de tirar uma licao evita analogia historica apressada."
        ),
        "science": (
            "separar dado, interpretacao e limite metodologico em uma noticia ajuda a aplicar a disciplina do livro."
        ),
        "sociology": (
            "analisar uma situacao cotidiana e identificar que norma invisivel ou instituicao organiza aquela interacao."
        ),
        "biography": (
            "comparar uma escolha dificil do personagem central com uma decisao propria ajuda a extrair criterio sem imitacao cega."
        ),
    }
    if family in family_hints:
        return family_hints[family]
    return "reservar 15 minutos diarios para a mesma atividade gera acumulacao visivel apos algumas semanas."


def _ensure_length(items: list[str], minimum: int, prefix: str) -> list[str]:
    result = [item.strip() for item in items if item.strip()]
    while len(result) < minimum:
        result.append(f"{prefix} {len(result) + 1}")
    return result


def _ensure_target_word_count_generic(lesson: Lesson) -> Lesson:
    additions = [
        (
            "Roteiro de aprofundamento em 7 dias: no primeiro dia, registrar a pergunta central da obra; no "
            "segundo, identificar o conceito ou conflito que organiza a leitura; do terceiro ao quinto, anotar "
            "exemplos, tensoes e discordancias; no sexto, comparar o texto com uma situacao atual; no setimo, "
            "escrever em uma pagina o que mudou no seu modo de interpretar o tema principal."
        ),
        (
            "Erros comuns de leitura: reduzir uma obra complexa a frase de efeito, ignorar contexto historico, "
            "procurar concordancia imediata em vez de entendimento e pular o trabalho de formular exemplos "
            "proprios. A leitura fica mais forte quando o leitor aceita sustentar ambiguidade por mais tempo, "
            "testa a tese em casos concretos e registra onde o livro amplia ou corrige intuicoes anteriores."
        ),
        (
            "Checklist de consolidacao: resumir a tese central em linguagem simples, listar quais conceitos ou "
            "personagens carregam o peso do argumento, anotar um exemplo marcante, registrar uma discordancia "
            "honesta e definir que pergunta fica aberta para novas leituras. Esse fechamento evita consumo passivo "
            "e transforma leitura em repertorio utilizavel."
        ),
        (
            "Modelo de revisao apos a leitura: o que o livro ajuda a ver com mais nitidez, que explicacao parece "
            "mais forte agora, onde ainda ha duvida e que implicacao pratica ou interpretativa merece observacao "
            "na proxima semana. Com esse ciclo curto, o texto deixa de ser lembranca vaga e passa a funcionar como "
            "criterio de pensamento."
        ),
    ]
    updated = lesson
    idx = 0
    while updated.word_count() < 900 and idx < len(additions):
        updated = replace(updated, guided_reading=[*updated.guided_reading, additions[idx]])
        idx += 1
    if updated.word_count() < 900:
        updated = replace(
            updated,
            guided_reading=[
                *updated.guided_reading,
                (
                    "Fechamento final: escolha uma ideia do livro para observar no mundo real nesta semana e "
                    "registre como ela aparece, onde falha e o que ainda exige interpretacao mais cuidadosa."
                ),
            ],
        )
    return updated


def _ensure_target_word_count(lesson: Lesson) -> Lesson:
    additions = [
        (
            "Aplicacao em 7 dias: escolha um habito de ate 10 minutos e execute no mesmo horario durante "
            "uma semana. No fim do periodo, registre tres pontos: o que ficou facil, onde houve atrito e "
            "qual ajuste reduz a chance de falha na semana seguinte. No dia 1, foque apenas em iniciar no "
            "horario combinado. Do dia 2 ao dia 4, mantenha o mesmo gatilho para reduzir decisao. Do dia 5 "
            "ao dia 7, acompanhe continuidade e descreva em uma frase o que ajudou ou atrapalhou a execucao."
        ),
        (
            "Erros comuns ao aplicar os conceitos: tentar mudar tudo de uma vez, depender apenas de motivacao, "
            "nao medir execucao e abandonar o processo apos poucos dias sem resultado visivel. O livro reforca "
            "que consistencia e mais importante que intensidade pontual. Outro erro frequente e definir meta "
            "ambiciosa sem desenhar o contexto de execucao: sem horario, local e gatilho claros, a rotina vira "
            "boa intencao. Correcao pratica: reduzir escopo, manter frequencia e revisar o sistema semanalmente."
        ),
        (
            "Checklist de consolidacao: manter o gatilho do habito visivel, reduzir friccao para iniciar, "
            "registrar a execucao diariamente e revisar o sistema uma vez por semana. Essa rotina simples "
            "costuma gerar melhoria sustentavel sem exigir mudancas radicais. Para manter aderencia, escolha "
            "um indicador simples de processo (dias executados, minutos dedicados ou repeticoes concluidas) "
            "e um indicador de resultado (qualidade percebida, velocidade ou estabilidade)."
        ),
        (
            "Modelo de revisao semanal: o que funcionou, o que travou e qual unico ajuste entra na proxima "
            "semana. Esse fechamento evita acumulacao de tentativas desconectadas e cria aprendizado pratico. "
            "Com revisoes curtas e constantes, o sistema evolui sem ruptura e sem depender de motivacao alta."
        ),
    ]
    updated = lesson
    idx = 0
    while updated.word_count() < 900 and idx < len(additions):
        updated = replace(updated, guided_reading=[*updated.guided_reading, additions[idx]])
        idx += 1
    if updated.word_count() < 900:
        updated = replace(
            updated,
            guided_reading=[
                *updated.guided_reading,
                (
                    "Ajuste final: escolha uma acao objetiva para hoje, acompanhe sua execucao e "
                    "registre o aprendizado em linguagem simples para consolidar a evolucao."
                ),
            ],
        )
    return updated


def _log_quality_issues(issues: list[object]) -> None:
    for issue in issues:
        severity = getattr(issue, "severity", "warning")
        message = getattr(issue, "message", str(issue))
        code = getattr(issue, "code", "quality_issue")
        if severity == "error":
            logger.error("Quality [%s]: %s", code, message)
        else:
            logger.warning("Quality [%s]: %s", code, message)
