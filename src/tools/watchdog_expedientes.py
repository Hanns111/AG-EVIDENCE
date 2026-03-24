# -*- coding: utf-8 -*-
"""
Watchdog de expedientes — Monitor de carpeta incoming
=====================================================
Monitorea data/expedientes/incoming/ y notifica por Telegram
cuando llegan nuevos PDFs.

Uso:
    python -m src.tools.watchdog_expedientes
    python -m src.tools.watchdog_expedientes --carpeta data/expedientes/incoming --intervalo 5

Versión: 1.0.0
Fecha: 2026-03-23
"""

import argparse
import hashlib
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_INCOMING_DIR = _PROJECT_ROOT / "data" / "expedientes" / "incoming"

logger = logging.getLogger("ag_evidence.watchdog")

# Reutilizar la función de Telegram del descargador
try:
    from src.tools.descargador_expedientes import enviar_telegram
except ImportError:
    # Fallback standalone
    def enviar_telegram(mensaje: str) -> bool:
        """Fallback: envía mensaje a Telegram."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
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
            if not token or not chat_id:
                logger.warning("Telegram no configurado")
                return False
        try:
            import requests
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Error Telegram: %s", e)
            return False


@dataclass
class ArchivoDetectado:
    """Metadatos de un archivo detectado."""

    nombre: str
    ruta: str
    tamano_bytes: int
    sha256: str
    timestamp: str


def _sha256_archivo(ruta: Path) -> str:
    """Calcula SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(8192), b""):
            h.update(bloque)
    return h.hexdigest()


def _escanear_carpeta(carpeta: Path, extensiones: Set[str]) -> Dict[str, float]:
    """Retorna dict {ruta_str: mtime} de archivos con extensiones dadas."""
    archivos = {}
    if not carpeta.exists():
        return archivos
    for archivo in carpeta.iterdir():
        if archivo.is_file() and archivo.suffix.lower() in extensiones:
            archivos[str(archivo)] = archivo.stat().st_mtime
    return archivos


class WatchdogExpedientes:
    """Monitor de carpeta que detecta archivos nuevos y notifica."""

    def __init__(
        self,
        carpeta: Path = _INCOMING_DIR,
        intervalo_segundos: int = 5,
        extensiones: Set[str] = None,
    ):
        self.carpeta = carpeta
        self.intervalo = intervalo_segundos
        self.extensiones = extensiones or {".pdf", ".PDF"}
        self._archivos_conocidos: Dict[str, float] = {}
        self._activo = True

    def iniciar(self):
        """Inicia el monitoreo. Bloquea hasta Ctrl+C."""
        self.carpeta.mkdir(parents=True, exist_ok=True)

        # Registrar archivos existentes (no notificar los que ya estaban)
        self._archivos_conocidos = _escanear_carpeta(self.carpeta, self.extensiones)
        n_existentes = len(self._archivos_conocidos)

        logger.info(
            "Watchdog iniciado en %s (%d archivos existentes, intervalo %ds)",
            self.carpeta,
            n_existentes,
            self.intervalo,
        )
        enviar_telegram(
            f"👁️ <b>Watchdog iniciado</b>\n"
            f"Carpeta: <code>{self.carpeta.name}/</code>\n"
            f"Archivos existentes: {n_existentes}\n"
            f"Intervalo: {self.intervalo}s"
        )

        # Manejar SIGINT/SIGTERM
        signal.signal(signal.SIGINT, self._detener)
        signal.signal(signal.SIGTERM, self._detener)

        while self._activo:
            self._verificar_nuevos()
            time.sleep(self.intervalo)

        logger.info("Watchdog detenido")
        enviar_telegram("🛑 <b>Watchdog detenido</b>")

    def _verificar_nuevos(self):
        """Compara estado actual con conocido y notifica nuevos."""
        actuales = _escanear_carpeta(self.carpeta, self.extensiones)

        for ruta_str, mtime in actuales.items():
            if ruta_str not in self._archivos_conocidos:
                self._procesar_nuevo(Path(ruta_str))
            elif mtime > self._archivos_conocidos.get(ruta_str, 0):
                self._procesar_modificado(Path(ruta_str))

        self._archivos_conocidos = actuales

    def _procesar_nuevo(self, ruta: Path):
        """Procesa un archivo nuevo detectado."""
        try:
            tamano = ruta.stat().st_size
            sha = _sha256_archivo(ruta)

            info = ArchivoDetectado(
                nombre=ruta.name,
                ruta=str(ruta),
                tamano_bytes=tamano,
                sha256=sha,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            logger.info("Nuevo archivo: %s (%d bytes, SHA256: %s...)", info.nombre, tamano, sha[:12])

            enviar_telegram(
                f"📄 <b>Nuevo expediente detectado</b>\n"
                f"Archivo: <code>{info.nombre}</code>\n"
                f"Tamaño: {tamano:,} bytes\n"
                f"SHA-256: <code>{sha[:16]}...</code>"
            )
        except Exception as e:
            logger.error("Error procesando %s: %s", ruta.name, e)

    def _procesar_modificado(self, ruta: Path):
        """Procesa un archivo modificado."""
        logger.info("Archivo modificado: %s", ruta.name)

    def _detener(self, signum=None, frame=None):
        """Detiene el watchdog limpiamente."""
        self._activo = False


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(description="Watchdog de expedientes AG-EVIDENCE")
    parser.add_argument(
        "--carpeta",
        default=str(_INCOMING_DIR),
        help="Carpeta a monitorear",
    )
    parser.add_argument(
        "--intervalo",
        type=int,
        default=5,
        help="Intervalo de escaneo en segundos (default: 5)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    watchdog = WatchdogExpedientes(
        carpeta=Path(args.carpeta),
        intervalo_segundos=args.intervalo,
    )
    watchdog.iniciar()


if __name__ == "__main__":
    main()
