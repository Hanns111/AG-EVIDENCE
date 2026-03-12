"""
Tests de integración VLM — Tarea #22 (Fase 3)

Verifica que qwen3-vl:8b está operativo vía Ollama y responde
correctamente a prompts con imágenes de comprobantes.

Estos tests requieren Ollama corriendo con qwen3-vl:8b cargado.
Se marcan con @pytest.mark.vlm para poder skippear en CI.
"""

import base64
import io
import json
from unittest.mock import patch

import pytest

from config.settings import VISION_CONFIG, VLM_CONFIG

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def vlm_config():
    """Retorna la configuración VLM actual."""
    return VLM_CONFIG.copy()


@pytest.fixture
def sample_image_b64():
    """Genera una imagen PNG simple en base64 para tests."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow no disponible")

    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _ollama_disponible():
    """Verifica si Ollama está corriendo."""
    try:
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _modelo_cargado(modelo: str) -> bool:
    """Verifica si un modelo específico está disponible en Ollama."""
    try:
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            nombres = [m["name"] for m in data.get("models", [])]
            return modelo in nombres
    except Exception:
        return False


skip_sin_ollama = pytest.mark.skipif(
    not _ollama_disponible(),
    reason="Ollama no está corriendo en localhost:11434",
)

skip_sin_qwen3vl = pytest.mark.skipif(
    not _modelo_cargado("qwen3-vl:8b"),
    reason="qwen3-vl:8b no está cargado en Ollama",
)


# =============================================================================
# Tests de configuración (siempre corren)
# =============================================================================


class TestVLMConfig:
    """Tests de configuración VLM en settings.py."""

    def test_vlm_config_existe(self):
        assert VLM_CONFIG is not None
        assert isinstance(VLM_CONFIG, dict)

    def test_modelo_es_qwen3_vl_8b(self):
        assert VLM_CONFIG["model"] == "qwen3-vl:8b"

    def test_fallback_model_existe(self):
        assert VLM_CONFIG["fallback_model"] == "qwen2.5vl:7b"

    def test_ollama_url(self):
        assert VLM_CONFIG["ollama_url"] == "http://localhost:11434"

    def test_timeout_ampliado(self):
        """Timeout >= 60s por latencia de thinking tokens."""
        assert VLM_CONFIG["timeout_seconds"] >= 60

    def test_max_tokens(self):
        assert VLM_CONFIG["max_tokens"] >= 4096

    def test_temperature_baja(self):
        """Temperature baja para extracción determinista."""
        assert VLM_CONFIG["temperature"] <= 0.3

    def test_no_think_desactivado(self):
        """no_think=False porque /no_think en content causa respuesta vacía en qwen3-vl."""
        assert VLM_CONFIG["no_think"] is False

    def test_max_retries(self):
        """Max retries para JSON corrupto (dato Viáticos AI)."""
        assert VLM_CONFIG["max_retries"] >= 1
        assert VLM_CONFIG["max_retries"] <= 3

    def test_enabled(self):
        assert VLM_CONFIG["enabled"] is True

    def test_vision_config_coherente(self):
        """VISION_CONFIG y VLM_CONFIG deben ser coherentes."""
        assert VISION_CONFIG["max_dimension_px"] >= 1000
        assert VISION_CONFIG["dpi_render_pdf"] >= 150


class TestMetodoExtraccion:
    """Verifica que QWEN_VL existe como método de extracción."""

    def test_enum_qwen_vl_existe(self):
        from src.extraction.expediente_contract import MetodoExtraccionContrato

        assert hasattr(MetodoExtraccionContrato, "QWEN_VL")
        assert MetodoExtraccionContrato.QWEN_VL.value == "qwen_vl"


# =============================================================================
# Tests de conectividad (requieren Ollama)
# =============================================================================


class TestOllamaConectividad:
    """Tests que verifican conexión con Ollama."""

    @skip_sin_ollama
    def test_ollama_responde(self):
        """Ollama server responde en localhost:11434."""
        assert _ollama_disponible()

    @skip_sin_ollama
    def test_qwen3_vl_8b_cargado(self):
        """qwen3-vl:8b está disponible en Ollama."""
        assert _modelo_cargado("qwen3-vl:8b")

    @skip_sin_ollama
    def test_fallback_model_cargado(self):
        """qwen2.5vl:7b (fallback) está disponible en Ollama."""
        assert _modelo_cargado("qwen2.5vl:7b")

    @skip_sin_ollama
    def test_healthcheck_completo(self):
        """Healthcheck: Ollama + modelo principal + fallback."""
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        nombres = [m["name"] for m in data.get("models", [])]
        assert VLM_CONFIG["model"] in nombres, (
            f"Modelo principal {VLM_CONFIG['model']} no encontrado"
        )


# =============================================================================
# Tests de invocación VLM (requieren Ollama + modelo)
# =============================================================================


class TestVLMInvocacion:
    """Tests que invocan el modelo VLM real."""

    @skip_sin_ollama
    @skip_sin_qwen3vl
    def test_vlm_responde_a_imagen(self, sample_image_b64):
        """qwen3-vl:8b responde a un prompt con imagen."""
        import urllib.request

        payload = {
            "model": "qwen3-vl:8b",
            "messages": [
                {
                    "role": "user",
                    "content": "Describe this image in one sentence.",
                    "images": [sample_image_b64],
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 256,
            },
        }

        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        assert "message" in data
        assert "content" in data["message"]
        assert len(data["message"]["content"]) > 0
        # Modelo debe responder algo sobre la imagen
        assert data["message"]["role"] == "assistant"

    @skip_sin_ollama
    @skip_sin_qwen3vl
    def test_vlm_extrae_texto_de_imagen(self, sample_image_b64):
        """qwen3-vl:8b puede extraer texto de una imagen con texto."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            pytest.skip("Pillow no disponible")

        # Crear imagen con texto "RUC 20341841357" en tamaño grande
        img = Image.new("RGB", (800, 200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Usar fuente grande para que VLM pueda leerlo
        try:
            from PIL import ImageFont

            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except (OSError, ImportError):
            font = ImageFont.load_default()
        draw.text((20, 60), "RUC 20341841357", fill=(0, 0, 0), font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        import urllib.request

        payload = {
            "model": "qwen3-vl:8b",
            "messages": [
                {
                    "role": "user",
                    "content": "Extract the RUC number from this image. Reply with ONLY the number, nothing else.",
                    "images": [img_b64],
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 64,
            },
        }

        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        content = data["message"].get("content", "")
        thinking = data["message"].get("thinking", "")
        # El RUC debe aparecer en content o thinking
        combined = (content + " " + thinking).replace(" ", "")
        assert "20341841357" in combined, (
            f"VLM no extrajo RUC. content={content!r}, thinking={thinking[:100]!r}"
        )
