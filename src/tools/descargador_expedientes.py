# -*- coding: utf-8 -*-
"""
Descargador de expedientes via Chrome CDP + Playwright
======================================================
Conecta a una instancia de Chrome ya abierta (puerto 9222) para
navegar y descargar PDFs de expedientes a data/expedientes/incoming/.

Uso:
    # Primero lanzar Chrome con remote debugging:
    # chrome.exe --remote-debugging-port=9222

    python -m src.tools.descargador_expedientes --url "https://ejemplo.gob.pe/expedientes"

Versión: 1.0.0
Fecha: 2026-03-23
"""

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Directorio raíz del proyecto
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_INCOMING_DIR = _PROJECT_ROOT / "data" / "expedientes" / "incoming"

logger = logging.getLogger("ag_evidence.descargador")


# ==============================================================================
# Configuración
# ==============================================================================

CDP_ENDPOINT = os.getenv("CDP_ENDPOINT", "http://localhost:9222")
DOWNLOAD_TIMEOUT_MS = int(os.getenv("DOWNLOAD_TIMEOUT_MS", "60000"))


@dataclass
class ResultadoDescarga:
    """Resultado de una operación de descarga."""

    url: str
    archivo: str
    exito: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None
    tamano_bytes: int = 0


# ==============================================================================
# Telegram
# ==============================================================================


def _cargar_telegram_config() -> tuple:
    """Carga TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID desde .env o entorno."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        # Intentar cargar desde .env del proyecto
        env_path = _PROJECT_ROOT / ".env"
        if env_path.exists():
            for linea in env_path.read_text(encoding="utf-8").splitlines():
                linea = linea.strip()
                if linea.startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                k, v = k.strip(), v.strip().strip("'\"")
                if k == "TELEGRAM_BOT_TOKEN":
                    token = v
                elif k == "TELEGRAM_CHAT_ID":
                    chat_id = v

    return token, chat_id


def enviar_telegram(mensaje: str) -> bool:
    """Envía mensaje a Telegram. Retorna True si tuvo éxito."""
    token, chat_id = _cargar_telegram_config()
    if not token or not chat_id:
        logger.warning("Telegram no configurado (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return False

    try:
        import requests

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Notificación Telegram enviada")
            return True
        else:
            logger.warning("Telegram respondió %d: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.warning("Error enviando Telegram: %s", e)
        return False


# ==============================================================================
# Descargador CDP
# ==============================================================================


def conectar_chrome(cdp_endpoint: str = CDP_ENDPOINT):
    """
    Conecta a Chrome via CDP usando Playwright.
    Retorna (playwright, browser, context) o lanza excepción.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright no instalado. Ejecutar:\n"
            "  pip install playwright && playwright install chromium"
        )

    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(cdp_endpoint)
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    logger.info("Conectado a Chrome CDP en %s", cdp_endpoint)
    return pw, browser, context


def descargar_pdf(
    page,
    url: str,
    destino: Optional[Path] = None,
    timeout_ms: int = DOWNLOAD_TIMEOUT_MS,
) -> ResultadoDescarga:
    """
    Navega a una URL y descarga el PDF resultante.

    Si la URL apunta directamente a un PDF, lo guarda.
    Si la página dispara una descarga, la intercepta.
    """
    if destino is None:
        destino = _INCOMING_DIR

    destino.mkdir(parents=True, exist_ok=True)

    try:
        # Interceptar descargas
        with page.expect_download(timeout=timeout_ms) as download_info:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        download = download_info.value
        nombre = download.suggested_filename or f"expediente_{int(time.time())}.pdf"
        ruta_final = destino / nombre

        download.save_as(str(ruta_final))
        tamano = ruta_final.stat().st_size

        logger.info("Descargado: %s (%d bytes)", nombre, tamano)

        return ResultadoDescarga(
            url=url,
            archivo=str(ruta_final),
            exito=True,
            tamano_bytes=tamano,
        )

    except Exception as e:
        # Fallback: tal vez la página cargó un PDF en el viewer
        return _intentar_guardar_pdf_directo(page, url, destino, str(e))


def _intentar_guardar_pdf_directo(
    page, url: str, destino: Path, error_previo: str
) -> ResultadoDescarga:
    """Fallback: intenta obtener el PDF via response si no hubo descarga."""
    try:
        response = page.goto(url, wait_until="load", timeout=30000)
        content_type = response.headers.get("content-type", "")

        if "pdf" in content_type.lower():
            body = response.body()
            nombre = f"expediente_{int(time.time())}.pdf"
            ruta_final = destino / nombre
            ruta_final.write_bytes(body)
            tamano = len(body)

            logger.info("PDF directo guardado: %s (%d bytes)", nombre, tamano)
            return ResultadoDescarga(
                url=url, archivo=str(ruta_final), exito=True, tamano_bytes=tamano
            )

        return ResultadoDescarga(
            url=url,
            archivo="",
            exito=False,
            error=f"No se detectó PDF. Content-Type: {content_type}. Error previo: {error_previo}",
        )
    except Exception as e2:
        return ResultadoDescarga(
            url=url,
            archivo="",
            exito=False,
            error=f"{error_previo} → fallback: {e2}",
        )


def descargar_multiples(
    urls: List[str],
    cdp_endpoint: str = CDP_ENDPOINT,
) -> List[ResultadoDescarga]:
    """Descarga múltiples PDFs y notifica por Telegram."""
    resultados = []
    pw, browser, context = conectar_chrome(cdp_endpoint)

    try:
        page = context.new_page()

        for url in urls:
            logger.info("Procesando: %s", url)
            resultado = descargar_pdf(page, url)
            resultados.append(resultado)

            if resultado.exito:
                enviar_telegram(
                    f"📥 <b>PDF descargado</b>\n"
                    f"Archivo: <code>{Path(resultado.archivo).name}</code>\n"
                    f"Tamaño: {resultado.tamano_bytes:,} bytes"
                )
            else:
                enviar_telegram(
                    f"⚠️ <b>Descarga fallida</b>\n"
                    f"URL: {url}\n"
                    f"Error: {resultado.error}"
                )

        page.close()
    finally:
        browser.close()
        pw.stop()

    # Resumen
    exitosas = sum(1 for r in resultados if r.exito)
    enviar_telegram(
        f"📊 <b>Resumen descarga</b>\n"
        f"Total: {len(resultados)} | OK: {exitosas} | Fallos: {len(resultados) - exitosas}"
    )

    return resultados


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(description="Descargador de expedientes AG-EVIDENCE")
    parser.add_argument("--url", nargs="+", required=True, help="URL(s) de PDFs a descargar")
    parser.add_argument("--cdp", default=CDP_ENDPOINT, help="Chrome CDP endpoint")
    parser.add_argument("--destino", default=str(_INCOMING_DIR), help="Carpeta destino")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    resultados = descargar_multiples(args.url, cdp_endpoint=args.cdp)

    for r in resultados:
        status = "OK" if r.exito else "FAIL"
        print(f"  [{status}] {r.url} → {r.archivo or r.error}")


if __name__ == "__main__":
    main()
