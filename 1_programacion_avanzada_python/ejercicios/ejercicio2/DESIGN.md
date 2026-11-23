# Principios SOLID aplicados

- **SRP — Responsabilidad única:** `loader.py` carga datos, `validator.py` los valida y `metrics.py` calcula métricas. Cada módulo tiene una responsabilidad y un motivo de cambio.
- **ISP — Segregación de interfaces:** `SalesRepository`, en `loader.py`, solo exige `load()`. No obliga a implementar operaciones que el procesamiento no necesita.
- **DIP — Inversión de dependencias:** `run()` en `cli.py` recibe un `SalesRepository`. `main()` elige el repositorio CSV o JSON y lo inyecta; el procesamiento puede utilizar otra implementación que respete el contrato.
