# ADR 0001 · Un solo repositorio y arquitectura hexagonal

**Fecha:** 2026-10-03 · **Estado:** aceptada

## Contexto

El reto pide un repositorio público con la solución completa: agente, API, interfaz, datos, componente aprendido y evaluación. Pide también que la política y los permisos se apliquen fuera del texto del modelo, que haya un baseline comparable y que el sistema pueda pasar a operación. El equipo tiene pocos días y una sola persona dedicada al backend.

## Decisión

1. **Un solo repositorio** con agente, API, web, pipeline, ML, evaluación, imágenes y despliegue.
2. **Arquitectura hexagonal:**
   - el dominio (`agente/contratos`, `puertos`, `nucleo`, `politica`, `salida`) solo depende de la biblioteca estándar, de Pydantic y de sí mismo;
   - la infraestructura (API, datos, modelo de lenguaje) entra por adaptadores que implementan los puertos;
   - una prueba de arquitectura (`tests/arquitectura`) hace cumplir la regla.
3. **Un solo proceso:** el agente corre como librería dentro de la API. No hay microservicios.

## Alternativas rechazadas

| Alternativa | Por qué no |
|---|---|
| Varios repositorios (agente, API, web) | Más coordinación y versiones cruzadas; el reto pide un repositorio |
| Agente autónomo con herramientas libres para el modelo | La política tiene que vivir fuera del modelo; es menos predecible y más difícil de auditar |
| Microservicios | Más piezas que pueden fallar en un servidor pequeño, sin beneficio a esta escala |

## Consecuencias

- Se cambia de modelo de lenguaje, de base de datos o de fuente de transacciones sin tocar las reglas.
- El dominio se prueba sin red ni datos; la CI usa adaptadores mock.
- Cada puerto necesita al menos dos adaptadores (el real y el mock), y los dos pasan las mismas pruebas de contrato.
