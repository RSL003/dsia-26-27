# Proyecto 1 

Realmente son dos proyectos, ventas y otro con los datos de la calidad del aire de Madrid. Se llamaran a partir de ahora proyecto V y proeyecto M.

# Proyecto V

```bash
python -m ventas_app
```

Lee `datos/ventas/ventas.csv`, valida las ventas y guarda los resultados en `resultados/ventas/`.

Reglas: fecha válida YYYY-MM-DD; región Norte, Sur, Este u Oeste; producto y cliente no vacíos; unidades enteras positivas dentro del rango de 64 bits; precio positivo y números finitos. No se eliminan ventas repetidas porque no existe identificador de transacción.

Resultados obtenidos: 140 ventas válidas, 10 rechazadas y un importe total 96.598,17. Se generan `ventas_limpias.csv`, `ventas_rechazadas.csv` y `calidad_datos.json`, los importes estan por egión, producto y mes, unidades y clientes recurrentes. El importe medio es por fila.

## Parte B: calidad del aire

Fuente: [histórico horario del Ayuntamiento de Madrid](https://datos.madrid.es/dataset/201200-0-calidad-aire-horario/information), recurso Desde 2025. [Descarga CSV](https://datos.madrid.es/dataset/201200-0-calidad-aire-horario/resource/201200-1-calidad-aire-horario-csv/download/201200-1-calidad-aire-horario-csv.csv). Actualización mensual y licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), con atribución al Ayuntamiento de Madrid.
Obtenido por codex

La copia descargada contiene 76.513 filas, de enero de 2025 a agosto de 2026. Cada fila tiene 24 medidas horarias.
Para descargar los datos hay que ejecutar el archivo madrid.py y esta es la ruta datos/internet/madrid.py. Guarda los archivos `datos/internet/aire.csv` y `origen.json` con la URL, fecha de ultima descarga y huella SHA-256. Actualizarla sustituye la copia local.

Para analizar la copia local, sin conexión:

```bash
python -m datos_internet_app
```

Reglas: fecha válida, identificadores presentes, estado V, valor numérico finito y no negativo. Se excluyen todas las apariciones de claves horarias duplicadas. Un cero con estado V se conserva. No se imputan datos. 

Se generan `aire_limpio.csv`, `aire_excluido.csv` y `resumen.json` en `resultados/aire/`. Incluyen recuentos, porcentaje utilizable, estaciones con datos, medias y máximos por estación y magnitud, medias por magnitud y bloque horario.

Los resultados comprobados son1.836.312 observaciones horarias, de las que 1.795.279 son utilizables y 41.033 se excluyen. Se conservan los códigos de magnitud y los bloques H01–H24. (etiquetas de las horas del 1 al 24). No se mezclan contaminantes ni se convierten los bloques a horas con zona horaria. Las medias corresponden a los datos disponibles. Se excluyen negativos por no tener sentido.
Por su tamaño los CSV demasiado grandes (datos/internet/aire.csv, resultados/aire/aire_limpio.csv , resultados/aire/aire_excluido.csv) se excluyen de Git; se reproducen con el script y la CLI. El script documentado cumple la alternativa a incluir una muestra que permite el enunciado.

## Código y Tests

En cada paquete, `loader.py` carga, `validator.py` valida, `metrics.py` calcula y `cli.py` coordina la ejecución. Se mantienen clases pequeñas y excepciones propias. Los motivos de rechazo se guardan como texto y cada observación conserva su fila original.

Hay 32 Tests. de ellos 14 son de ventas, 12 son de aire, y 6 se aplican a ambos.

