from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.catalog_seed import build_balanced_catalog
from app.config import runtime_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ferramentas para gerenciar books_365.json")
    parser.add_argument("--list-placeholders", action="store_true", help="Lista dias com placeholder.")
    parser.add_argument("--export-template", type=int, help="Exporta template JSON para o dia informado.")
    parser.add_argument("--apply-file", type=Path, help="Aplica JSON de um dia e salva no books_365.json.")
    parser.add_argument("--rebalance-catalog", action="store_true", help="Regenera books_365.json com curadoria balanceada.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_file = runtime_paths().data_file
    payload = json.loads(data_file.read_text(encoding="utf-8"))

    if args.list_placeholders:
        days = [item["day"] for item in payload if item["author"] == "Autor a definir"]
        print("Dias placeholder:", ", ".join(str(day) for day in days))
        return

    if args.export_template:
        day = args.export_template
        if day < 1 or day > 365:
            raise ValueError("Dia deve estar entre 1 e 365.")
        template = {
            "day": day,
            "title": "Titulo da leitura",
            "author": "Autor",
            "category": "Categoria",
            "theme": "Tema principal",
            "key_ideas": [
                "Ideia 1",
                "Ideia 2",
                "Ideia 3",
                "Ideia 4",
                "Ideia 5",
            ],
            "practical_applications": [
                "Aplicacao 1",
                "Aplicacao 2",
                "Aplicacao 3",
            ],
            "reflection_question": "Pergunta de reflexao",
            "optional_quote": "Citacao opcional curta",
        }
        print(json.dumps(template, ensure_ascii=False, indent=2))
        return

    if args.rebalance_catalog:
        payload = build_balanced_catalog()
        data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        categories = sorted({item["category"] for item in payload})
        print(f"Catalogo balanceado gravado em {data_file}")
        print(f"Total de itens: {len(payload)}")
        print("Categorias:", ", ".join(categories))
        return

    if args.apply_file:
        incoming = json.loads(args.apply_file.read_text(encoding="utf-8"))
        day = int(incoming["day"])
        if day < 1 or day > 365:
            raise ValueError("Campo day invalido no arquivo de entrada.")
        payload[day - 1] = incoming
        data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Dia {day} atualizado em {data_file}")
        return

    raise SystemExit("Use --list-placeholders, --export-template N, --rebalance-catalog ou --apply-file ARQUIVO.")


if __name__ == "__main__":
    main()
