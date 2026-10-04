# VERA · asistente de disputas de LATAM Bank

**VERA** (de «verificación») atiende el primer contacto de una disputa transaccional en **LATAM Bank**, el banco sintético del Factored AI & Data Hackathon 2026 (México, Colombia y Argentina; español y portugués). **V**erifica antes de actuar, **E**xplica con la regla y su fuente, **R**egistra y relee el caso, y **A**compaña con una persona siempre disponible.

> **Estado:** en construcción. Esta versión trae la estructura del repositorio y la regla de arquitectura; el resto llega por etapas.
> **Demo:** https://vera.colectivohagamos.com (se publica al primer despliegue).

## Cómo está organizado

Arquitectura hexagonal (puertos y adaptadores): el dominio no depende de la infraestructura.

| Carpeta | Qué contiene |
|---|---|
| `agente/contratos` | Modelos de las fronteras (Pydantic) |
| `agente/puertos` | Interfaces del dominio: identidad, transacciones, tarjetas, casos, derivación, auditoría e intérprete |
| `agente/nucleo` | Flujo de la disputa como máquina de estados |
| `agente/politica` | Reglas de la política (POL-*, PROH-*) y reloj legal por país |
| `agente/herramientas` | Herramientas detrás de una puerta única (confirmación, idempotencia y relectura) |
| `agente/adaptadores` · `agente/llm` · `agente/gateway` | Datos, modelo de lenguaje y entrada del texto del cliente |
| `agente/salida` | Plantillas ES/PT, validador y handoff |
| `api/` · `web/` | API HTTP `/v1` y páginas del cliente y del analista |
| `pipeline/` · `ml/` · `evaluacion/` | Datos, componente aprendido y evaluación |
| `docker/` · `deploy/` | Imágenes y despliegue |
| `docs/adr/` | Decisiones de arquitectura |
| `tests/` | Unitarias, contrato, propiedades, arquitectura y e2e |

## Pruebas

```bash
uv sync
uv run pytest
uv run ruff check .
```

La CI (GitHub Actions) ejecuta en cada PR y en cada push a `development`, `qa` y `production` el lint, el formato, las pruebas y `scripts/verificar_publicacion.py`, que impide publicar datos, secretos, archivos prohibidos o archivos de más de 10 MB.

## Datos

Los datos de LATAM Bank son sintéticos y pertenecen a Factored. **Ningún registro del dataset se versiona en este repositorio**: la preparación corre fuera del repo, la demo usa un subconjunto seudonimizado que vive solo en el servidor y las pruebas usan datos generados por el equipo.

## Licencia

AGPL-3.0 (ver `LICENSE`).
