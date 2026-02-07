# 🔴 PROBLEMA: Error MCP `readpdfx`

## DIAGNÓSTICO DEL PROBLEMA

### Problema Identificado:
1. **El MCP `readpdfx` NO EXISTE** como servidor MCP oficial
2. **El nombre correcto es `pdf-handler`**
3. **El error aparece en la interfaz de Cursor** porque:
   - Cursor intenta cargar un MCP llamado `readpdfx`
   - Ese MCP no está instalado ni configurado
   - Por eso muestra el error rojo 🔴

### Ubicación del Error:
- **Interfaz de Cursor**: Panel de MCPs (probablemente en Settings → MCP Servers)
- **NO está en archivos de configuración** (ya verifiqué: no hay referencias en `mcp.json` ni `settings.json`)

---

## SOLUCIÓN

### Opción 1: Para Claude Code (Instrucciones)

```
PROBLEMA: El MCP "readpdfx" muestra error rojo en Cursor.

CAUSA: "readpdfx" no existe. El MCP correcto es "pdf-handler".

ACCIÓN REQUERIDA:
1. Abre Settings de Cursor (Ctrl+,)
2. Busca "MCP Servers" o "Model Context Protocol"
3. Elimina cualquier entrada llamada "readpdfx"
4. Agrega/configura el MCP "pdf-handler" con esta configuración:
   {
     "mcpServers": {
       "pdf-handler": {
         "command": "uvx",
         "args": ["mcp-server-pdf-handler"]
       }
     }
   }
5. Guarda y reinicia Cursor
```

### Opción 2: Manual (Tú lo haces)

**Paso 1: Abrir configuración de MCPs en Cursor**
- `Ctrl+Shift+P` → Buscar "MCP: Configure Servers" o "MCP Settings"
- O ir a: `File → Preferences → Settings → Buscar "MCP"`

**Paso 2: Eliminar `readpdfx`**
- Buscar en la lista de MCPs
- Eliminar cualquier entrada que diga `readpdfx`

**Paso 3: Configurar `pdf-handler`**
- Agregar nuevo MCP con nombre: `pdf-handler`
- Comando: `uvx`
- Args: `["mcp-server-pdf-handler"]`

**Paso 4: Instalar el servidor (si no está instalado)**
```powershell
pip install mcp-server-pdf-handler
```

**Paso 5: Reiniciar Cursor**

---

## ARCHIVO DE CONFIGURACIÓN

El archivo correcto debería estar en:
```
C:\Users\Hans\.cursor\mcp.json
```

Y debería contener:
```json
{
  "mcpServers": {
    "pdf-handler": {
      "command": "uvx",
      "args": [
        "mcp-server-pdf-handler"
      ]
    }
  }
}
```

---

## VERIFICACIÓN

Después de aplicar la solución:
1. Reinicia Cursor completamente
2. `Ctrl+Shift+P` → "MCP: List Servers"
3. Deberías ver `pdf-handler` (sin error rojo)
4. NO deberías ver `readpdfx`

---

## RESUMEN PARA CLAUDE CODE

**Problema**: MCP `readpdfx` muestra error porque no existe.

**Solución**: 
- Eliminar `readpdfx` de la configuración de MCPs en Cursor
- Configurar `pdf-handler` en su lugar
- Instalar `mcp-server-pdf-handler` si falta

**Archivo a modificar**: `C:\Users\Hans\.cursor\mcp.json` (o configuración UI de Cursor)
