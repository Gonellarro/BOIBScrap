"""Interfaz de línea de comandos."""

import argparse
from dataclasses import replace
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from .bulletins import bulletins_in_range, bulletins_on_date, latest_bulletins
from .client import BoibClient
from .search import search_bulletin
from .sections import normalize_section
from .pdfs import download_pdf
from .models import SearchResult
from .telegram import send_document
from .envfile import load_env_file


def _color(text: str, code: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Busca textos en las secciones configuradas del BOIB.")
    parser.add_argument(
        "--fecha", metavar="dd/MM/AAAA",
        help="Busca todos los BOIB de un día concreto (acepta año de 2 o 4 cifras).",
    )
    parser.add_argument(
        "--inicio-fecha", metavar="dd/MM/AAAA",
        help="Inicio inclusivo del rango; sin --fin-fecha, el fin será hoy.",
    )
    parser.add_argument(
        "--fin-fecha", metavar="dd/MM/AAAA",
        help="Fin inclusivo del rango; si no se indica inicio, comienza el día 1 de ese mes.",
    )
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).resolve().parent.parent / "config.json",
        help="Fichero JSON de configuración (por defecto: config.json del proyecto).",
    )
    parser.add_argument("--json", action="store_true", help="Imprime resultados estructurados en JSON.")
    return parser.parse_args(argv)


def _parse_date(value: str) -> date:
    for date_format in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha no válida: {value!r}. Usa dd/MM/AAAA")


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        load_env_file(Path(__file__).resolve().parent.parent / ".env")
        config = json.loads(args.config.read_text(encoding="utf-8"))
        terms = config.get("search_terms", [])
        if not isinstance(terms, list) or not all(isinstance(term, str) for term in terms):
            raise ValueError("search_terms debe ser una lista de textos en config.json")
        raw_together_terms = config.get("search_together_terms", [])
        if not isinstance(raw_together_terms, list):
            raise ValueError("search_together_terms debe ser una lista en config.json")
        terms = [term.strip() for term in terms if term.strip()]
        if not raw_together_terms:
            together_groups = []
        elif all(isinstance(term, str) for term in raw_together_terms):
            # Compatibilidad: la lista plana actual se interpreta como un único grupo AND.
            legacy_group = [term.strip() for term in raw_together_terms if term.strip()]
            together_groups = [legacy_group] if legacy_group else []
        elif all(
            isinstance(group, list) and all(isinstance(term, str) for term in group)
            for group in raw_together_terms
        ):
            together_groups = []
            for index, group in enumerate(raw_together_terms, start=1):
                cleaned_group = [term.strip() for term in group if term.strip()]
                if not cleaned_group:
                    raise ValueError(f"El grupo {index} de search_together_terms está vacío")
                together_groups.append(cleaned_group)
        else:
            raise ValueError(
                "search_together_terms debe ser una lista de textos o una lista de listas de textos"
            )
        if not terms and not together_groups:
            raise ValueError("Añade términos en search_terms o search_together_terms dentro de config.json")
        raw_sections = config.get("sections", ["III"])
        if not isinstance(raw_sections, list) or not all(isinstance(item, str) for item in raw_sections):
            raise ValueError("sections debe ser una lista de secciones en config.json")
        if not raw_sections:
            raise ValueError("Añade al menos una sección en sections dentro de config.json")
        sections = list(dict.fromkeys(normalize_section(item).code for item in raw_sections))

        telegram_config = config.get("telegram", {})
        if not isinstance(telegram_config, dict):
            raise ValueError("telegram debe ser un objeto en config.json")
        telegram_enabled = telegram_config.get("enabled", False)
        if not isinstance(telegram_enabled, bool):
            raise ValueError("telegram.enabled debe ser true o false")
        telegram_chat_id = str(telegram_config.get("chat_id", "")).strip()
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if telegram_enabled and not telegram_chat_id:
            raise ValueError("Indica telegram.chat_id en config.json")
        if telegram_enabled and not telegram_token:
            raise ValueError("Define la variable de entorno TELEGRAM_BOT_TOKEN")

        client = BoibClient(timeout=int(config.get("timeout_seconds", 30)))
        color_stderr = sys.stderr.isatty() and "NO_COLOR" not in os.environ
        color_stdout = sys.stdout.isatty() and "NO_COLOR" not in os.environ

        def progress(message: str) -> None:
            if "coincidencia para" in message:
                message = _color(message, "1;32", color_stderr)
            else:
                message = _color(message, "36", color_stderr)
            print(f"[BOIBScrap] {message}", file=sys.stderr, flush=True)

        if args.fecha and (args.inicio_fecha or args.fin_fecha):
            raise ValueError("Usa --fecha por separado, o --inicio-fecha/--fin-fecha para un rango")

        if args.inicio_fecha or args.fin_fecha:
            if args.inicio_fecha:
                start_date = _parse_date(args.inicio_fecha)
            else:
                end_for_month = _parse_date(args.fin_fecha)
                start_date = end_for_month.replace(day=1)
            end_date = _parse_date(args.fin_fecha) if args.fin_fecha else date.today()
            if start_date > end_date:
                raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin")
            progress(f"buscando boletines del {start_date:%d/%m/%Y} al {end_date:%d/%m/%Y}")
            bulletins = bulletins_in_range(client, start_date, end_date)
            if not bulletins:
                raise RuntimeError(
                    f"No se encontraron boletines entre {start_date:%d/%m/%Y} "
                    f"y {end_date:%d/%m/%Y}"
                )
        elif args.fecha:
            requested_date = _parse_date(args.fecha)
            progress(f"buscando boletines del {requested_date:%d/%m/%Y} en el calendario")
            bulletins = bulletins_on_date(client, requested_date)
            if not bulletins:
                raise RuntimeError(f"No se encontraron boletines para {requested_date:%d/%m/%Y}")
        else:
            progress("consultando la portada para identificar el último BOIB")
            bulletins = latest_bulletins(client)

        progress("boletines a revisar: " + ", ".join(
            f"núm. {bulletin.number} ({bulletin.published_date})" for bulletin in bulletins
        ))
        progress("secciones: " + ", ".join(f"Secció {section}" for section in sections))
        progress(
            f"búsqueda: O ({len(terms)} término(s)); "
            f"Y ({len(together_groups)} grupo(s), "
            f"{sum(len(group) for group in together_groups)} término(s))"
        )
        results = []
        for bulletin in bulletins:
            results.extend(search_bulletin(
                client, bulletin, terms, sections=sections, progress=progress,
                together_terms=together_groups,
            ))
        download_dir = Path(__file__).resolve().parent.parent / "downloads"
        downloaded_results = []
        pdf_failures = 0
        for index, result in enumerate(results, start=1):
            progress(
                f"descargando PDF {index}/{len(results)}: "
                f"BOIB {result.bulletin.number} / {result.section}: {result.document_title}"
            )
            try:
                pdf_url, pdf_path = download_pdf(client, result, download_dir)
                downloaded_results.append(replace(
                    result, pdf_url=pdf_url, pdf_path=str(pdf_path)
                ))
                progress(f"PDF guardado en {pdf_path}")
            except RuntimeError as exc:
                pdf_failures += 1
                downloaded_results.append(result)
                progress(f"no se pudo descargar el PDF: {exc}")
        results = downloaded_results
        telegram_failures = 0
        if telegram_enabled:
            sendable_results = [result for result in results if result.pdf_path]
            if not sendable_results:
                progress("Telegram: no hay PDFs coincidentes disponibles para enviar")
            for index, result in enumerate(sendable_results, start=1):
                caption = (
                    f"BOIB {result.bulletin.number} ({result.bulletin.published_date}) · "
                    f"{result.section}\n{result.document_title}"
                )
                progress(f"enviando PDF {index}/{len(sendable_results)} a Telegram")
                try:
                    send_document(
                        telegram_token,
                        telegram_chat_id,
                        Path(result.pdf_path),
                        caption,
                        timeout=int(config.get("timeout_seconds", 30)),
                    )
                    progress(f"PDF enviado a Telegram: BOIB {result.bulletin.number}")
                except RuntimeError as exc:
                    telegram_failures += 1
                    progress(f"no se pudo enviar el PDF a Telegram: {exc}")

        progress(
            f"búsqueda terminada: {len(results)} disposición(es) con coincidencias; "
            f"{len(results) - pdf_failures} PDF(s) disponible(s)"
        )
        if args.json:
            print(json.dumps({
                "bulletins": [bulletin.to_dict() for bulletin in bulletins],
                "terms": terms,
                "together_terms": together_groups,
                "matches": [result.to_dict() for result in results],
            }, ensure_ascii=False, indent=2))
        else:
            print("Boletines revisados:")
            for bulletin in bulletins:
                print(f"- Núm. {bulletin.number}, {bulletin.published_date}: {bulletin.url}")
            if not results:
                labels = ", ".join(f"Secció {section}" for section in sections)
                print(f"No se encontraron coincidencias en {labels}.")
            for result in results:
                heading = (
                    f"\n✓ Coincidencia en el BOIB {result.bulletin.number} / "
                    f"{result.section}: {result.document_title}"
                )
                print(_color(heading, "1;32", color_stdout))
                print(_color(result.document_url, "4;36", color_stdout))
                if result.pdf_path:
                    print(f"PDF: {result.pdf_path}")
                elif result.pdf_url:
                    print(f"PDF remoto: {result.pdf_url}")
                for match in result.matches:
                    label = _color(f"[{match.logic}: {match.term}]", "1;33", color_stdout)
                    print(f"  {label} {match.excerpt}")
        return 3 if telegram_failures else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
