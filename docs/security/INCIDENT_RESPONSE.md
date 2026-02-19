# Plan de Respuesta a Incidentes — AG-EVIDENCE

> Procedimiento formal para gestionar incidentes de seguridad
> que afecten la integridad de datos procesados o del sistema.

**Identificador:** SEC-INC-001
**Version:** 1.0.0
**Fecha:** 2026-02-19
**Alineamiento:** NIS2 Art.23, NIST CSF RS, ISO 27035

---

## 1. Definicion de Incidente

Un incidente de seguridad en AG-EVIDENCE es cualquier evento que:

1. **Comprometa la integridad** de datos extraidos o procesados.
2. **Exponga datos sensibles** de expedientes fuera del entorno local.
3. **Modifique la cadena de custodia** sin registro.
4. **Permita que la IA genere datos probatorios** sin fuente verificable.
5. **Corrompa o destruya** documentos fuente o resultados de auditoria.

---

## 2. Clasificacion de Severidad

| Nivel | Nombre | Descripcion | Tiempo de respuesta |
|-------|--------|-------------|---------------------|
| **S1** | CRITICO | Datos de expediente expuestos externamente; integridad de hash rota en cadena de custodia | Inmediato (< 1 hora) |
| **S2** | ALTO | IA local generando datos probatorios sin bloqueo; perdida de archivos de expediente | < 4 horas |
| **S3** | MEDIO | Archivos temporales con datos sensibles sin limpiar; dependencia comprometida | < 24 horas |
| **S4** | BAJO | Log sin rotacion excediendo espacio; warning de seguridad en tests | < 1 semana |

---

## 3. Procedimiento de Respuesta

### 3.1 Deteccion

**Fuentes de deteccion:**
- Tests automatizados (pytest) detectan regresion en controles de seguridad.
- Logger JSONL registra operaciones anomalas.
- Verificacion de hash SHA-256 detecta alteraciones.
- Review manual de expedientes procesados.

**Indicadores de compromiso (IoC):**
- Hash de documento no coincide con registro en cadena de custodia.
- Campos probatorios con fuente no trazable.
- Archivos en `output/` no generados por el pipeline.
- Logs JSONL con trace_ids no reconocidos.

### 3.2 Contencion

1. **Detener el pipeline** — no procesar nuevos expedientes.
2. **Aislar los datos afectados** — mover a directorio de cuarentena.
3. **Preservar evidencia** — no modificar logs ni archivos temporales.
4. **Verificar integridad** — ejecutar verificacion de hash en todos los expedientes recientes.

```bash
# Script de contencion rapida
python -c "
from src.ingestion.custody_chain import verificar_integridad
# Verificar ultimos expedientes procesados
"
```

### 3.3 Investigacion

1. **Revisar logs JSONL** — buscar trace_ids anomalos.
2. **Verificar cadena de custodia** — confirmar hashes SHA-256.
3. **Auditar cambios en git** — `git log --oneline -20` + `git diff`.
4. **Verificar modelos Ollama** — checksum de modelos descargados.
5. **Revisar archivos temporales** — contenido de `output/ocr_temp/`.

### 3.4 Erradicacion

Segun el tipo de incidente:

| Tipo | Accion |
|------|--------|
| Datos probatorios fabricados | Reprocesar expediente desde cero con pipeline limpio |
| Cadena de custodia corrupta | Restaurar desde backup; regenerar hashes |
| Dependencia comprometida | Pin version segura; pip install desde hash verificado |
| Archivo temporal expuesto | Eliminar; verificar que no se copio externamente |

### 3.5 Recuperacion

1. **Restaurar desde backup** — `python scripts/backup_local.py --restore`.
2. **Reprocesar expedientes** afectados con pipeline verificado.
3. **Verificar resultados** contra documentos fuente originales.
4. **Actualizar controles** que fallaron.

### 3.6 Lecciones Aprendidas

Despues de cada incidente S1 o S2:
1. Documentar en RISK_REGISTER.md con fecha, causa, impacto, remediacion.
2. Crear test de regresion que detecte la condicion.
3. Actualizar SECURITY_BASELINE.md si cambian controles.
4. Revisar si el incidente requiere nuevo ADR.

---

## 4. Contactos

| Rol | Persona | Medio |
|-----|---------|-------|
| Propietario del sistema | Hans | Directo (operador unico) |
| Soporte tecnico IA | Claude Code | Sesion activa |

> AG-EVIDENCE es un sistema mono-operador. El "equipo de respuesta"
> es Hans + las herramientas automatizadas del pipeline.

---

## 5. Procedimientos Especificos

### 5.1 Incidente: IA genera datos probatorios

**Deteccion:** Test en local_analyst.py falla; campo probatorio aparece con fuente "IA_LOCAL".

**Respuesta:**
1. Verificar que `LOCAL_ANALYST_CONFIG["enabled"]` sea `False`.
2. Si esta `True`: desactivar inmediatamente en config/settings.py.
3. Revisar todos los expedientes procesados con IA activa.
4. Verificar que `_bloquear_valores_probatorios()` funciona correctamente.
5. Reprocesar expedientes afectados sin Capa C.

### 5.2 Incidente: Hash de cadena de custodia no coincide

**Deteccion:** `verificar_integridad()` retorna FALSO para un documento.

**Respuesta:**
1. Preservar el documento actual y el registro de custodia.
2. Comparar hash del archivo actual con el hash registrado.
3. Si el archivo fue modificado: restaurar desde backup.
4. Si el registro fue alterado: investigar quien/que modifico el JSONL.
5. Reprocesar el expediente desde el documento original.

### 5.3 Incidente: Datos de expediente expuestos

**Deteccion:** Archivos de `data/expedientes/` o `output/` encontrados fuera del entorno local.

**Respuesta:**
1. Identificar que datos fueron expuestos y a donde.
2. Si fue via git: verificar .gitignore; hacer `git rm --cached` si necesario.
3. Si fue via copia manual: documentar y reportar segun normativa peruana.
4. Revisar todos los expedientes en el mismo directorio.
5. Considerar notificacion a las partes afectadas si hay datos personales (GDPR Art.33-34, Ley 29733 Peru).

---

## 6. Pruebas del Plan

El plan se prueba anualmente (o antes de cada nueva fase) con:

- **Tabletop exercise:** Simular un escenario S2 y recorrer el procedimiento.
- **Verificacion de backups:** Confirmar que `backup_local.py` genera ZIPs validos.
- **Test de integridad:** Ejecutar verificacion de hash en todos los expedientes.

---

## Historial de Versiones

| Version | Fecha | Cambio |
|---------|-------|--------|
| 1.0.0 | 2026-02-19 | Plan inicial |

---

*Documento generado por Claude Code bajo instruccion directa de Hans.*
