# Comparación de modelos: OLS y bosque aleatorio

El estudio usa **NO₂ (magnitud 8, µg/m³) en Plaza de España (28079004)**.
Se eligió una serie con amplia cobertura por disponibilidad de datos, no por el
resultado de sus predicciones. No se mezclan contaminantes ni estaciones y las
conclusiones no se extrapolan automáticamente a otras series.

## Qué se predice y con qué variables

Se predice el valor del bloque siguiente `y(t+1)` a partir de información hasta
el bloque `t`. Es una evaluación retrospectiva de **un paso con observaciones
actualizadas**: para cada hora de test se conoce el valor real de la hora anterior.
No es una predicción recursiva de cuatro meses desde un único instante inicial.

| Conjunto | Variables |
| --- | --- |
| `base` (7 columnas) | Valor actual, valor anterior, media de t−2/t−1/t, seno/coseno del bloque objetivo, seno/coseno del día de semana objetivo |
| `meteorologia` (13 columnas) | Las 7 anteriores, temperatura, humedad, velocidad de viento, seno/coseno de dirección del viento y precipitación de t |

Son las cinco entradas conceptuales de la guía, más las cinco meteorológicas;
las codificaciones cíclicas aumentan el número de columnas numéricas a 7 y 13.
Estación y magnitud son constantes de selección, no variables predictoras.

`features.py` reindexa a una rejilla horaria UTC y no rellena huecos. Para cada
ejemplo exige mediciones consecutivas t−2, t−1, t y t+1 y variables completas.
Ambos conjuntos se evalúan sobre exactamente las mismas filas completas para
que quitar meteorología no cambie la muestra. El calendario de H24 se asocia al
día cuyo bloque termina, como en el CSV municipal.

ERA5 es un reanálisis publicado con retraso: incluso usando meteorología de t,
el experimento no reproduce toda la disponibilidad de información en tiempo real.
No se introduce meteorología de t+1. Una versión operativa requeriría observaciones
disponibles entonces o pronósticos archivados con su fecha de emisión.

## Entrenamiento, validación y test

Los cortes se fijan antes de comparar errores y son cronológicos, sin barajar:

| Partición | Periodo del objetivo en UTC | Uso |
| --- | --- | --- |
| Entrenamiento | Antes del 01/01/2026 | Ajustar modelos y examinar VIF/correlaciones |
| Validación | Enero–abril de 2026 | Elegir profundidad/hojas del bosque y candidato por MAE |
| Test | Mayo–agosto de 2026 | Evaluación final de las configuraciones congeladas |

Se omite un objetivo en cada frontera cuando su origen aún pertenece a la partición
anterior. El objetivo máximo de train precede al origen mínimo de validación;
lo mismo entre validación y test. Usar valores históricos anteriores al corte para
construir retardos es válido: ya eran conocidos al predecir.

Cada candidato se ajusta en train y se mide en validación. La familia/conjunto y
los parámetros se congelan con MAE de validación; se reajustan en train+validación
y se mide test. Se muestran todos los candidatos congelados por transparencia,
pero no se cambia de ganador basándose en test. Si se hacen cambios tras mirar
test, ese periodo deja de ser una evaluación independiente para la nueva versión.

Es una sola división por fechas, no una validación cruzada temporal de varios
orígenes. El test cae principalmente en meses cálidos; sus resultados no prueban
la misma calidad en invierno. Antes de producción convendría una evaluación
walk-forward con más periodos y nuevos datos reservados.

## Modelos y referencia

- **Persistencia:** predecir `y(t+1) = y(t)`. Es una referencia esencial en series
  horarias y también puede ganar la selección de validación.
- **OLS:** `StandardScaler` + `LinearRegression` de sklearn, con intercepto y sin
  regularización. El escalador se ajusta exclusivamente con el conjunto de ajuste.
  Escalar no elimina multicolinealidad ni introduce una penalización.
- **Random Forest:** 150 árboles, profundidades 8/16/sin límite y mínimo de muestras
  por hoja 5/20: seis combinaciones por conjunto de variables. Semilla 42 y dos
  procesos de trabajo. La selección se hace con MAE de validación, no con OOB ni
  con particiones aleatorias. Los árboles individuales sí usan bootstrap interno;
  la evaluación externa sigue siendo temporal.

Se guardan cuatro artefactos `.joblib`: `ols_base`, `ols_meteorologia`,
`forest_base` y `forest_meteorologia`.
Joblib es el formato de persistencia; no es el modelo. Cada archivo contiene
`estimator`, nombres/orden de variables, estación, magnitud, horizonte, fecha
máxima del objetivo utilizado para ajustar y versión de sklearn. El estimador ya
incluye el escalado cuando corresponde. La transformación de datos crudos sigue
en `features.py`: no se puede pasar directamente el CSV original al estimador.

## Métricas y diagnósticos

| Diagnóstico | Interpretación y límites |
| --- | --- |
| MAE y RMSE | Error en µg/m³; RMSE penaliza más los errores grandes. MAE elige los candidatos |
| R² | Comparación con la media del objetivo; puede ser negativo y no sustituye comparar con persistencia |
| Sesgo y percentil 95 del error absoluto | Error sistemático y comportamiento en errores grandes |
| Error de ajuste frente a validación/test | Diferencias grandes pueden indicar sobreajuste, además de cambios estacionales |
| VIF | Colinealidad entre entradas en train; por encima de 5 merece revisión y por encima de 10 es una alerta orientativa |
| Correlación y número de condición estandarizado | Complementan VIF; el rango comprueba si hay dependencia lineal exacta |
| ACF y Ljung–Box a 1/6/24 horas | Dependencia temporal remanente en residuos; p pequeña cuestiona residuos sin autocorrelación |
| Durbin–Watson | Resumen descriptivo de dependencia de primer orden. No usar sus tablas como prueba concluyente con objetivo retardado entre las entradas |
| Breusch–Pagan | Exploración de varianza residual no constante; la autocorrelación puede afectar la calibración de su p-valor |
| Jarque–Bera | Exploración de normalidad; no es requisito para que el bosque prediga ni para obtener el ajuste OLS |
| Cook en OLS | Observaciones influyentes; superar 4/n señala casos para investigar, no para borrar automáticamente |
| Coeficientes OLS con errores HAC, 24 retardos | Inferencia exploratoria robusta a dependencia/heterocedasticidad; no demuestra causalidad ni corrige endogeneidad |

No se comprimen los huecos al calcular autocorrelación: las pruebas usan el tramo
continuo más largo de validación o test, y el informe indica su tamaño y fechas.
Los coeficientes HAC se ajustan en el tramo continuo más largo de train mediante
statsmodels, como diagnóstico separado; no son los coeficientes del estimador
final reajustado en train+validación. Sus p-valores son exploratorios.

No se utiliza MAPE como criterio: las concentraciones nulas o cercanas a cero
vuelven inestable el error porcentual. Ninguna prueba aislada de residuos certifica
que el modelo esté bien especificado.

La colinealidad puede volver inestables los coeficientes OLS aunque prediga bien.
En el bosque no existe la misma hipótesis sobre coeficientes, pero variables
redundantes reparten su importancia y dificultan interpretarla. Las importancias
por reducción de impureza se guardan como descriptivas, no como efectos causales.
El bosque puede sobreajustar y no extrapola bien fuera del rango de entrenamiento;
OLS puede generar concentraciones negativas, que se cuentan sin recortarlas a cero.

## Reproducir y leer los resultados

La sección [Reproducir la entrega](README.md#reproducir-la-entrega) reconstruye
SQLite con la serie fija del estudio y entrena sin red. Para entrenar sobre la
base completa, construye primero `datos/aire_meteo.sqlite` y ejecuta desde
`proyectos/proyecto_ii`:

```bash
python -m aire_app.compare_modelos
python -m pytest -q
```

En el entorno del repositorio se puede sustituir `python` por
`../../.venv/bin/python`. Opciones: `--database`, `--output`, `--models`,
`--station` y `--magnitude`. Cambiar serie implica un experimento distinto;
comprobar su unidad y cobertura antes de interpretar resultados.

Se generan:

- `resultados/comparacion/evaluacion.json`: particiones, métricas y diagnósticos.
- `busqueda_validacion.csv`: las doce configuraciones de bosque evaluadas.
- `coeficientes_hac_base.csv` y `coeficientes_hac_meteorologia.csv`: ajuste diagnóstico.
- `predicciones_test.csv`: objetivos y predicciones emparejadas.
- `ejemplos.csv`: tabla preparada con marcas de partición/frontera.
- `diagnosticos.png`: errores, predicciones y ACF de residuos.
- `modelos/*.joblib`: candidatos reajustados; la carga se verifica contra predicciones.

Los resultados y modelos grandes son reproducibles y se excluyen de Git. El
resumen interpretado se conserva en `docs/RESULTADOS_MODELOS.md`.

Fuentes técnicas: [RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html),
[evaluación temporal](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html),
[VIF](https://www.statsmodels.org/stable/generated/statsmodels.stats.outliers_influence.variance_inflation_factor.html)
y [diagnósticos de statsmodels](https://www.statsmodels.org/stable/stats.html).
