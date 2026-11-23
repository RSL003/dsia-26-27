# Uso de IA — Proyecto II

Se ha utilizado Codex para elaborar la guía de trabajo e implementar el paso 1:
trasladar el pipeline `proyecto_M` del Proyecto I a `aire_app`, adaptar rutas,
preparar una muestra de pruebas, trasladar tests y añadir comprobaciones de
métricas e integración. La procedencia del código base es el propio Proyecto I.

La ayuda de IA en el desarrollo es distinta del futuro cliente de IA generativa
del producto. Ese cliente, el modelo y la inferencia no están implementados en
este paso. Las comprobaciones ejecutadas se documentan en el README.

Después se utilizó Codex para implementar el enriquecimiento con Open-Meteo/ERA5,
consultar la documentación oficial de los bloques horarios y las estaciones,
construir SQLite, añadir caché con procedencia y pruebas sin red, y explicar el
proceso en el README. Se ejecutó la descarga real y se comprobó la cobertura de la
unión completa. El cliente generativo y el entrenamiento siguen pendientes.

En una ampliación posterior se utilizó Codex para preparar variables temporales,
comparar OLS y Random Forest con periodos separados de entrenamiento/validación/test,
calcular diagnósticos de colinealidad y residuos, guardar/cargar modelos joblib y
redactar `MODELADO.md` y `docs/RESULTADOS_MODELOS.md`. Se consultó documentación
oficial de sklearn y statsmodels. Se ejecutó el experimento real y 25 tests.
El entrenamiento comparativo ya está implementado; el cliente generativo y la
integración de inferencia en la CLI habitual siguen pendientes.
