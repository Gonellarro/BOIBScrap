"""Envío de documentos al Bot API de Telegram."""

import json
import secrets
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def send_document(
    token: str,
    chat_id: str,
    document: Path,
    caption: str,
    timeout: int = 30,
) -> None:
    """Envía un archivo con multipart/form-data sin mostrar el token en errores."""
    boundary = "----BOIBScrap" + secrets.token_hex(16)
    filename = document.name.replace('"', "")
    fields = {
        "chat_id": chat_id,
        "caption": caption[:1024],
    }
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
            value.encode("utf-8"),
            b"\r\n",
        ])
    chunks.extend([
        f"--{boundary}\r\n".encode("ascii"),
        (
            f'Content-Disposition: form-data; name="document"; '
            f'filename="{filename}"\r\n'
        ).encode("utf-8"),
        b"Content-Type: application/pdf\r\n\r\n",
        document.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode("ascii"),
    ])
    request = Request(
        f"https://api.telegram.org/bot{token}/sendDocument",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Telegram respondió con HTTP {exc.code} al enviar el PDF") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"No se pudo conectar con Telegram: {exc.reason if isinstance(exc, URLError) else exc}") from None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Telegram devolvió una respuesta no válida: {exc}") from None

    if not result.get("ok"):
        description = result.get("description", "error no especificado")
        raise RuntimeError(f"Telegram no aceptó el PDF: {description}")
