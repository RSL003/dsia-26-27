# Proyecto I — Programación avanzada en Python (10 %)

## Trabajo desarrollado

Consulta [ENTREGA.md](ENTREGA.md) para ejecutar ambas partes: **A, ventas**, y **B, histórico horario de calidad del aire de Madrid (más de 10.000 filas)**. Datos locales en `datos/`, resultados en `resultados/` y pruebas en `tests/`. Uso de IA documentado en [AI_USAGE.md](AI_USAGE.md).

---

**Temas:** 1  
**Presentación / arranque en clase:** 14 de septiembre de 2026  
**Entrega orientativa:** antes de la sesión de pytest (28 sep), salvo indicación distinta en aula.

## Objetivo

Desarrollar **dos** soluciones en Python que demuestren:

- Estructuras de datos adecuadas
- OOP
- Tratamiento de errores
- Validación y manipulación de datos
- Buenas prácticas y documentación

**Las dos partes son obligatorias** y entran en la misma nota del Proyecto I (10 %).

---

## Parte A — Pipeline de ventas (dataset del curso)

Construye un **pipeline de calidad de datos de ventas** a partir de `Datos/ventas.csv` (o una copia en tu repo):

1. Carga y validación con excepciones de dominio.
2. Métricas de negocio (importe por región/producto, etc.).
3. CLI usable (`python -m ...`).
4. README + docstrings.

Estructura orientativa (la de clase):

```text
ventas_app/
  loader.py
  validator.py
  metrics.py
  cli.py
```

---

## Parte B — Pipeline con datos elegidos de internet

Repite el **mismo tipo de solución** (carga → validación → métricas → CLI), pero con un **dataset público elegido por ti**.

### Requisitos del dataset

1. Debe ser **descargable o enlazable** desde internet (CSV, JSON, API pública, portal open data, Kaggle, datos.gov, etc.).
2. Indica en el README: **URL de origen**, licencia/condiciones de uso y fecha de descarga.
3. Incluye en el repo una **muestra** razonable (p. ej. miles de filas como máximo) o un script de descarga documentado; no subas ficheros enormes.
4. Define **reglas de validación propias** (nulos, rangos, tipos, duplicados, etc.) acordes al dominio elegido.
5. Calcula **al menos 3 métricas / agregaciones** con sentido para esos datos.

### Qué se evalúa de más en la Parte B

- Criterio al elegir y describir el dataset.
- Que el diseño no sea un copiar-pegar ciego: adaptas nombres, reglas y métricas al nuevo dominio.
- Reutilización sensata de ideas de la Parte A (módulos, excepciones, CLI) sin acoplar ambos pipelines en un solo “mega-script”.

Estructura orientativa:

```text
internet_app/          # o el nombre de tu dominio
  loader.py
  validator.py
  metrics.py
  cli.py
```

---

## Entrega (ambas partes)

En el mismo repositorio GitHub (o carpeta del Proyecto I):

| Elemento | Parte A | Parte B |
| --- | --- | --- |
| Código modular + CLI | Obligatorio | Obligatorio |
| README con cómo ejecutar | Obligatorio | Obligatorio (puede ser un README conjunto con dos secciones) |
| Datos | `ventas.csv` del curso | Muestra + URL de origen |
| Secretos / claves | No | No |

Checklist mínimo de entrega:

- [ ] Parte A ejecutable de extremo a extremo
- [ ] Parte B ejecutable de extremo a extremo
- [ ] README con comandos de ambas
- [ ] Origen y licencia del dataset de internet documentados
- [ ] Historial Git con sentido (no un único commit gigante el último día)

---

## Rúbrica orientativa (sobre el 10 % del Proyecto I)

| Criterio | Peso | Notas |
| --- | --- | --- |
| Correctitud funcional (A + B) | 30 % | Las dos partes deben correr |
| Diseño OOP / modularidad | 25 % | Separación loader / validator / metrics / CLI |
| Manejo de errores y validación | 20 % | Reglas explícitas en ambos dominios |
| Claridad, documentación y dataset B | 15 % | README, URL/licencia, métricas con sentido |
| Uso responsable de Git | 10 % | Commits legibles en ambas partes |

Si solo se entrega una de las dos partes, la nota del Proyecto I queda **incompleta** (no se considera entregado el proyecto).
