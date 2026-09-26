# BOIBScrap

Consulta los boletines oficiales de las Illes Balears y busca términos en las secciones del BOIB que elijas en la configuración.

## Configuración

Al clonar el repositorio, crea tu configuración local desde la plantilla y edítala. `config.json` contiene tus búsquedas y se excluye de Git:

```bash
cp config.example.json config.json
```

Después, ajusta en `config.json` las búsquedas, secciones y datos de Telegram. La plantilla contiene valores de ejemplo; no los uses sin cambiarlos.

`search_terms` funciona con lógica O: basta con que aparezca uno de esos términos. `search_together_terms` acepta grupos de términos: todos los términos de un mismo subgrupo deben aparecer en el documento (Y), y basta con que coincida uno de los subgrupos (O). Los términos no tienen que estar juntos ni en el mismo orden. También se acepta la lista plana anterior como un único grupo AND. Un documento coincide si cumple `search_terms` o alguno de los grupos. La comparación ignora mayúsculas y tildes. Puedes dejar vacío cualquiera de los grupos. `sections` acepta las secciones `I`, `II`, `III` y `V`; también puedes escribir sus etiquetas, por ejemplo `"Secció III"`. Si no se indica, se usa `III`.

## Entorno virtual en Linux

Desde la carpeta del proyecto, crea el entorno virtual y actívalo:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Si el comando `venv` no está disponible, instala el paquete de Python correspondiente a tu distribución (por ejemplo, `python3-venv` en Debian o Ubuntu) y vuelve a crear el entorno.

El proyecto solo usa la biblioteca estándar, así que no hace falta instalar paquetes adicionales. Con el entorno activado, configura `config.json` y ejecuta:

```bash
python main.py
python main.py --fecha 22/09/2026
python main.py --inicio-fecha 01/09/2026 --fin-fecha 23/09/2026
python main.py --inicio-fecha 01/09/2026
python main.py --fin-fecha 23/09/2026
```

Para salir del entorno virtual, ejecuta `deactivate`.

## Uso

```bash
python3 main.py
python3 main.py --fecha 22/09/2026
python3 main.py --inicio-fecha 01/09/2026 --fin-fecha 23/09/2026
python3 main.py --inicio-fecha 01/09/2026
python3 main.py --fin-fecha 23/09/2026
python3 main.py --inicio-fecha 01/09/2026 --fin-fecha 23/09/2026 --json
```

Sin argumentos de fecha, el programa sigue el enlace oficial al último boletín e incluye los extraordinarios publicados ese mismo día. `--fecha` consulta un día concreto. El rango `--inicio-fecha`/`--fin-fecha` es inclusivo: si se omite el fin, usa hoy; si se omite el inicio, comienza el primer día del mes de fin. Las fechas se escriben como `dd/MM/AAAA`.

Cuando una disposición coincide, el programa descarga su PDF oficial en la carpeta `downloads/` del proyecto. El nombre incluye el número del BOIB, la sección y el título; si ya existe una copia válida, la reutiliza. La ruta local aparece en consola y en el campo `pdf_path` de la salida `--json`. Solo se descargan los PDFs de las disposiciones coincidentes.

El comando devuelve un código distinto de cero si hay un error de configuración o de conexión. `--json` produce una salida estructurada para integrarla más adelante con una tarea programada.

## Telegram

Para enviar cada PDF coincidente como documento, configura `telegram.enabled` como `true` y pon el identificador de destino en `telegram.chat_id`. El token se guarda en `.env`, separado de `config.json` y excluido de Git.

Si aún no tienes `.env`, créalo desde la plantilla y limita sus permisos:

```bash
cp .env_example .env
chmod 600 .env
nano .env
```

Dentro de `.env`, sustituye el valor de `TELEGRAM_BOT_TOKEN` por el token nuevo de BotFather, sin compartirlo ni añadirlo a Git. El programa carga ese valor automáticamente al ejecutarse. El `.env` de este espacio de trabajo ya está creado con permisos `600`.

Los PDFs se envían individualmente con el número y la fecha del BOIB, la sección y el título en el texto del documento. Si Telegram no está habilitado en la configuración, el scraper solo descarga los archivos. Si no hay coincidencias, no envía mensajes. El código de salida es `3` si falla algún envío.

## Módulos

- `client.py`: conexión HTTP.
- `bulletins.py`: calendario, último día publicado y selección de fechas y rangos.
- `sections.py`: catálogo y validación de secciones del BOIB.
- `dispositions.py`: enlace a las categorías y listado de disposiciones.
- `search.py`: normalización y búsqueda en texto HTML.
- `pdfs.py`: localización, validación y descarga de los PDFs coincidentes.
- `telegram.py`: envío de documentos al bot configurado.
- `models.py`: datos estructurados para los resultados.
- `cli.py`: argumentos y presentación.

Requiere Python 3.10 o posterior y solo usa la biblioteca estándar.
