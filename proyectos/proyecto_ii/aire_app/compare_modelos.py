"""Comparación reproducible OLS / Random Forest con test cronológico reservado."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import platform
import sqlite3
import sys

import joblib
import numpy as np
import pandas as pd
from pandas.errors import DatabaseError
import sklearn
import statsmodels.api as sm
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera

from .features import BASE_FEATURES, WEATHER_FEATURES, construir_ejemplos, dividir_temporal

BASE = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


def metricas(y, pred):
    error = np.asarray(y) - np.asarray(pred)
    return {"MAE": float(mean_absolute_error(y, pred)),
            "RMSE": float(np.sqrt(mean_squared_error(y, pred))),
            "R2": float(r2_score(y, pred)), "sesgo_pred_menos_real": float(-error.mean()),
            "error_absoluto_p95": float(np.quantile(abs(error), .95)),
            "predicciones_negativas": int((np.asarray(pred) < 0).sum())}


def multicolinealidad(X):
    z = pd.DataFrame(StandardScaler().fit_transform(X), columns=X.columns)
    design = sm.add_constant(z)
    vif = {col: float(variance_inflation_factor(design.values, i + 1)) for i, col in enumerate(X.columns)}
    corr = X.corr()
    pares = [{"a": a, "b": b, "correlacion": float(corr.loc[a, b])}
             for i, a in enumerate(X.columns) for b in X.columns[i + 1:]
             if abs(corr.loc[a, b]) >= .8]
    return {"VIF": vif, "numero_condicion_estandarizado": float(np.linalg.cond(design)),
            "rango": int(np.linalg.matrix_rank(design)), "columnas_con_intercepto": design.shape[1],
            "correlaciones_abs_ge_0_8": pares}


def tramo_contiguo(frame):
    groups = frame.objetivo_utc.diff().ne(pd.Timedelta(hours=1)).cumsum()
    return frame.loc[groups.eq(groups.value_counts().idxmax())]


def diagnostico_residuos(frame, y_pred, columnas):
    """Pruebas sobre el tramo horario continuo más largo, sin comprimir huecos."""
    tmp = frame.copy()
    tmp["pred"] = np.asarray(y_pred)
    tramo = tramo_contiguo(tmp)
    resid = tramo.objetivo - tramo.pred
    lags = [lag for lag in [1, 6, 24] if lag < len(resid) // 5]
    lb = acorr_ljungbox(resid, lags=lags, return_df=True)
    X = sm.add_constant(StandardScaler().fit_transform(tramo[columnas]))
    bp = het_breuschpagan(resid, X)
    jb = jarque_bera(resid)
    return {"n_tramo": len(tramo), "inicio": str(tramo.objetivo_utc.iloc[0]),
            "fin": str(tramo.objetivo_utc.iloc[-1]), "durbin_watson_descriptivo": float(durbin_watson(resid)),
            "acf": {str(lag): float(resid.autocorr(lag)) for lag in lags},
            "ljung_box": {str(lag): {"estadistico": float(lb.loc[lag, "lb_stat"]),
                                       "p": float(lb.loc[lag, "lb_pvalue"])} for lag in lags},
            "breusch_pagan_LM": float(bp[0]), "breusch_pagan_p": float(bp[1]),
            "jarque_bera": float(jb[0]), "jarque_bera_p": float(jb[1]),
            "asimetria": float(jb[2]), "curtosis": float(jb[3])}


def guardar_coeficientes_hac(train, cols, output):
    # HAC requiere una secuencia equiespaciada: usar tramo continuo de train.
    tramo = tramo_contiguo(train)
    X = sm.add_constant(tramo[cols])
    fit = sm.OLS(tramo.objetivo, X).fit(cov_type="HAC", cov_kwds={"maxlags": 24})
    ci = fit.conf_int()
    pd.DataFrame({"variable": fit.params.index, "coeficiente": fit.params.values,
                  "error_estandar_HAC24": fit.bse.values, "p_HAC24": fit.pvalues.values,
                  "IC95_inferior": ci[0].values, "IC95_superior": ci[1].values}).to_csv(output, index=False)
    influence = fit.get_influence().cooks_distance[0]
    return {"n_tramo_train": len(tramo), "inicio": str(tramo.objetivo_utc.iloc[0]),
            "fin": str(tramo.objetivo_utc.iloc[-1]),
            "max_cook": float(influence.max()),
            "cook_supera_4_n": int((influence > 4 / len(tramo)).sum()),
            "nota": "Ajuste diagnóstico separado sobre tramo de train; no es el modelo final train+val. HAC24 no corrige endogeneidad."}


def representar(test, preds, output, magnitud, unidad):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from statsmodels.graphics.tsaplots import plot_acf
    fig, axes = plt.subplots(3, 2, figsize=(13, 12))
    tramo = tramo_contiguo(test).iloc[:168]
    axes[0, 0].plot(tramo.objetivo_utc, tramo.objetivo, label="Real", linewidth=1.5)
    modelos_meteorologia = ("ols_meteorologia", "forest_meteorologia")
    for nombre in modelos_meteorologia:
        axes[0, 0].plot(tramo.objetivo_utc, preds[nombre][tramo.index], label=nombre, alpha=.8)
    axes[0, 0].set_title("Primeros 7 días de un tramo continuo de test")
    etiqueta = "NO₂" if magnitud == "8" else f"Magnitud {magnitud}"
    unidades = f" ({unidad})" if unidad != "ver catálogo" else ""
    axes[0, 0].set_ylabel(etiqueta + unidades)
    axes[0, 0].tick_params(axis="x", rotation=25)
    axes[0, 0].legend()
    labels = list(preds)
    axes[0, 1].barh(labels, [mean_absolute_error(test.objetivo, preds[k]) for k in labels])
    axes[0, 1].set_xlabel("MAE en test" + unidades)
    axes[0, 1].set_title("Mismas observaciones para todos los modelos")
    for col, nombre in enumerate(modelos_meteorologia):
        resid = test.objetivo.to_numpy() - preds[nombre]
        axes[1, col].scatter(preds[nombre], resid, s=5, alpha=.3)
        axes[1, col].axhline(0, color="black", linewidth=.7)
        axes[1, col].set(xlabel="Predicción" + unidades, ylabel="Real − predicción" + unidades, title=nombre)
        full = tramo_contiguo(test)
        if len(full) > 1:
            plot_acf(resid[full.index], lags=min(48, len(full) - 1), ax=axes[2, col], zero=False)
        axes[2, col].set(title=f"ACF de residuos: {nombre}", xlabel="Retardo (horas)")
    fig.tight_layout()
    fig.savefig(output / "diagnosticos.png", dpi=160)
    plt.close(fig)


def comparar(database: Path, output: Path, modelos: Path, estacion="28079004", magnitud="8"):
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        serie = pd.read_sql_query("SELECT * FROM aire_enriquecido WHERE estacion_id=? AND MAGNITUD=? ORDER BY timestamp_utc",
                                  con, params=(estacion, magnitud))
        if serie.empty:
            raise ValueError(f"No hay datos para la estación {estacion} y la magnitud {magnitud}")
        procedencia = json.loads(con.execute("SELECT json FROM ejecucion").fetchone()[0])
    frame, cobertura = construir_ejemplos(serie)
    train, val, test = dividir_temporal(frame)
    output.mkdir(parents=True, exist_ok=True)
    modelos.mkdir(parents=True, exist_ok=True)
    # Índices locales para guardar y representar predicciones sin desalineación.
    train, val, test = [x.reset_index(drop=True) for x in [train, val, test]]
    resumen = {"estacion": estacion, "nombre": str(serie.nombre_estacion.iloc[0]),
               "magnitud": magnitud, "unidad": "µg/m³" if magnitud == "8" else "ver catálogo",
               "cobertura": cobertura, "origen_datos": procedencia,
               "semilla": 42, "seleccion": "MAE de validación; test no interviene",
               "python": platform.python_version(), "sklearn": sklearn.__version__,
               "creacion_utc": datetime.now(timezone.utc).isoformat(), "particiones": {},
               "multicolinealidad_train": {}, "coeficientes_HAC_train": {}, "modelos": {}}
    for nombre, datos in [("train", train), ("validacion", val), ("test", test)]:
        resumen["particiones"][nombre] = {"n": len(datos), "inicio_objetivo": str(datos.objetivo_utc.min()),
                                          "fin_objetivo": str(datos.objetivo_utc.max()),
                                          "media_objetivo": float(datos.objetivo.mean()),
                                          "std_objetivo": float(datos.objetivo.std())}
    grids, elegidos = [], {}
    sets = {"base": BASE_FEATURES, "meteorologia": BASE_FEATURES + WEATHER_FEATURES}
    for grupo, cols in sets.items():
        resumen["multicolinealidad_train"][grupo] = multicolinealidad(train[cols])
        resumen["coeficientes_HAC_train"][grupo] = guardar_coeficientes_hac(train, cols, output / f"coeficientes_hac_{grupo}.csv")
        ols = make_pipeline(StandardScaler(), LinearRegression()).fit(train[cols], train.objetivo)
        elegidos[f"ols_{grupo}"] = (ols, cols, {})
        mejor = None
        for profundidad in [8, 16, None]:
            for hoja in [5, 20]:
                params = {"n_estimators": 150, "max_depth": profundidad,
                          "min_samples_leaf": hoja, "max_features": 1.0,
                          "random_state": 42, "n_jobs": 2}
                LOG.info("Validando forest %s: depth=%s leaf=%s", grupo, profundidad, hoja)
                forest = RandomForestRegressor(**params).fit(train[cols], train.objetivo)
                score = mean_absolute_error(val.objetivo, forest.predict(val[cols]))
                grids.append({"variables": grupo, **params, "MAE_validacion": float(score)})
                if mejor is None or score < mejor[0]:
                    mejor = (score, forest, params)
        elegidos[f"forest_{grupo}"] = (mejor[1], cols, mejor[2])
    pd.DataFrame(grids).to_csv(output / "busqueda_validacion.csv", index=False)
    # Congelar selección antes de predecir test; referencia también puede ganar.
    val_scores = {k: mean_absolute_error(val.objetivo, est.predict(val[cols]))
                  for k, (est, cols, _) in elegidos.items()}
    val_scores["persistencia"] = mean_absolute_error(val.objetivo, val.valor_actual)
    ganador = min(val_scores, key=val_scores.get)
    resumen["elegido_antes_de_test"] = ganador
    predicciones = {"persistencia": test.valor_actual.to_numpy()}
    resumen["modelos"]["persistencia"] = {
        "train": metricas(train.objetivo, train.valor_actual),
        "validacion": metricas(val.objetivo, val.valor_actual),
        "test": metricas(test.objetivo, test.valor_actual),
        "diagnostico_test": diagnostico_residuos(test, test.valor_actual, BASE_FEATURES)}
    train_val = pd.concat([train, val], ignore_index=True)
    for nombre, (modelo, cols, params) in elegidos.items():
        LOG.info("Congelado %s; reajuste train+val y evaluación test", nombre)
        pred_train = modelo.predict(train[cols])
        pred_val = modelo.predict(val[cols])
        modelo_final = clone(modelo).fit(train_val[cols], train_val.objetivo)
        pred_test = modelo_final.predict(test[cols])
        predicciones[nombre] = pred_test
        fit_stats = metricas(train_val.objetivo, modelo_final.predict(train_val[cols]))
        registro = {"variables": cols, "parametros": params,
                    "train": metricas(train.objetivo, pred_train),
                    "validacion": metricas(val.objetivo, pred_val),
                    "ajuste_train_mas_validacion": fit_stats,
                    "test": metricas(test.objetivo, pred_test),
                    "diagnostico_validacion": diagnostico_residuos(val, pred_val, cols),
                    "diagnostico_test": diagnostico_residuos(test, pred_test, cols)}
        if nombre.startswith("forest"):
            registro["importancia_impureza_no_causal"] = dict(zip(cols, modelo_final.feature_importances_.tolist()))
        # Comparación de error de test respecto a persistencia.
        registro["mejora_MAE_test_pct"] = 100 * (1 - registro["test"]["MAE"] / resumen["modelos"]["persistencia"]["test"]["MAE"])
        resumen["modelos"][nombre] = registro
        artifact = {"estimator": modelo_final, "features": cols, "estacion_id": estacion,
                    "magnitud": magnitud, "horizonte_horas": 1,
                    "entrenado_hasta_objetivo_utc": str(train_val.objetivo_utc.max()),
                    "sklearn": sklearn.__version__, "evaluacion": registro["test"],
                    "uso": "retrospectivo ERA5; no representa disponibilidad meteorológica en tiempo real"}
        archivo = modelos / f"{nombre}.joblib"
        joblib.dump(artifact, archivo, compress=3)
        loaded = joblib.load(archivo)
        np.testing.assert_allclose(loaded["estimator"].predict(test[cols].head(10)), pred_test[:10])
    test_export = test[["origen_utc", "objetivo_utc", "objetivo", "valor_actual"]].copy()
    for nombre, pred in predicciones.items():
        test_export[f"pred_{nombre}"] = pred
    test_export.to_csv(output / "predicciones_test.csv", index=False)
    frame["particion"] = "embargo"
    for nombre, datos in [("train", train), ("validacion", val), ("test", test)]:
        frame.loc[frame.origen_utc.isin(datos.origen_utc), "particion"] = nombre
    frame.to_csv(output / "ejemplos.csv", index=False)
    metadata = {"seleccionado": ganador, "archivo": f"{ganador}.joblib" if ganador != "persistencia" else None,
                "criterio": resumen["seleccion"], "estacion": estacion, "magnitud": magnitud,
                "horizonte_horas": 1, "sklearn": sklearn.__version__,
                "MAE_validacion": float(val_scores[ganador]),
                "advertencia": "ERA5 retrospectivo; selección congelada antes de consultar test"}
    (modelos / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    (output / "evaluacion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    guardar_metricas_comparacion(resumen, output)
    representar(test, predicciones, output, magnitud, resumen["unidad"])
    return resumen


def guardar_metricas_comparacion(resumen: dict, output: Path) -> None:
    """Exporta una fila por candidato con las métricas de validación y test."""
    filas = []
    for nombre, registro in resumen["modelos"].items():
        fila = {"modelo": nombre}
        for particion in ("validacion", "test"):
            for metrica in ("MAE", "RMSE", "R2"):
                fila[f"{metrica}_{particion}"] = registro[particion][metrica]
        filas.append(fila)
    pd.DataFrame(filas).to_csv(output / "metricas_modelos.csv", index=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=BASE / "datos/aire_meteo.sqlite")
    parser.add_argument("--output", type=Path, default=BASE / "resultados/comparacion")
    parser.add_argument("--models", type=Path, default=BASE / "modelos")
    parser.add_argument("--station", default="28079004")
    parser.add_argument("--magnitude", default="8")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        resultado = comparar(args.database, args.output, args.models, args.station, args.magnitude)
    except (OSError, ValueError, sqlite3.Error, DatabaseError) as exc:
        print(f"Error al comparar modelos: {exc}", file=sys.stderr)
        return 1
    print("Elegido por validación:", resultado["elegido_antes_de_test"])
    print(f"{'Modelo':<24} {'MAE val.':>10} {'R² val.':>10} {'MAE test':>10} {'RMSE test':>10} {'R² test':>10}")
    for nombre, registro in resultado["modelos"].items():
        validacion, test = registro["validacion"], registro["test"]
        print(f"{nombre:<24} {validacion['MAE']:>10.3f} {validacion['R2']:>10.3f} "
              f"{test['MAE']:>10.3f} {test['RMSE']:>10.3f} {test['R2']:>10.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
