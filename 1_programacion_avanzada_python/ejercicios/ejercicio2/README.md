# E2 — Arquitectura modular, Clean Code y SOLID

## Ejecución

Abre la terminal en `1_programacion_avanzada_python/ejercicios` (la carpeta que contiene `ejercicio2`) y ejecuta:

```bash
python3 -m ejercicio2.cli --input ../Datos/ventas.csv --output ejercicio2/resultados/ventas_limpias.csv
```

Para comprobar el error de lectura:

```bash
python3 -m ejercicio2.cli --input ../Datos/no_existe.csv --output ejercicio2/resultados/prueba.csv
```

Necesita pandas, incluido en las dependencias del curso. Las rutas de los argumentos se interpretan desde la carpeta actual de la terminal.

## Organización

- `__init__.py`: identifica el paquete.
- `loader.py`: carga CSV o JSON, define `DataLoadError` y el contrato `SalesRepository`.
- `validator.py`: valida columnas, define `ValidationError` y separa filas válidas e inválidas.
- `metrics.py`: calcula importes por región, top de productos y clientes recurrentes.
- `cli.py`: recibe argumentos, orquesta y guarda CSV y JSON de calidad.
- `DESIGN.md`: justifica tres principios SOLID con referencias al código.

## Revisión del enunciado

Se mantienen la separación en módulos, las dos excepciones propias, `loader.load(path)`, los argumentos `--input` y `--output`, y tres principios SOLID documentados.

Clean Code: nombres descriptivos (`valid_sales`, `invalid_sales`), constantes para el límite de productos y los umbrales, y logging en lugar de prints de depuración.

El paquete se llama `ejercicio2` y sus módulos están directamente dentro de esa carpeta. El enunciado propone el nombre `ventas_app`; por ello el comando cambia a `python3 -m ejercicio2.cli`. La estructura y el comportamiento se conservan.

La extensión `JsonSalesRepository` está implementada en `loader.py`. El CLI elige el lector según la extensión del archivo. Los dos lectores devuelven un DataFrame y utilizan las mismas funciones de validación y métricas; no se ha añadido lógica de JSON a `metrics.py`.

El JSON de entrada debe ser una lista de objetos con las mismas columnas que el CSV. Para utilizarlo, sustituye el argumento de entrada por la ruta a tu archivo `.json`.

El informe `calidad_datos.json` es un resumen de salida, no un archivo de ventas para volver a cargar.

## Uso de IA

Herramienta utilizada: OpenAI Codex, para ayudar a organizar los módulos, comentar el código y comprobar su funcionamiento.
