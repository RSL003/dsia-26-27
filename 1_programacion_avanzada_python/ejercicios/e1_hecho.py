from pathlib import Path
import pandas as pd
import json

ruta = Path(__file__).resolve().parent.parent / "Datos" / "ventas.csv"

ventas = pd.read_csv(ruta)

print("Dimensiones:")
print(ventas.shape)

print("\nTipos:")
print(ventas.dtypes)

print("\nValores ausentes:")
print(ventas.isna().sum())

def validar_ventas(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
	datos = frame.copy()

	datos["unidades"] = pd.to_numeric(
		datos["unidades"], errors="coerce"
	)
	datos["precio_unitario"] = pd.to_numeric(
		datos["precio_unitario"], errors="coerce"
	)

	validos_mask = (
		datos["unidades"].gt(0)
		& datos["precio_unitario"].gt(0)
	)

	validos = datos[validos_mask].copy()
	errores = datos[~validos_mask].copy()

	# Son inválidas las filas con unidades o precio ausentes, cero o negativos.
	validos["importe"] = (
		validos["unidades"] * validos["precio_unitario"]
	)

	return validos, errores


validos, errores = validar_ventas(ventas)

print("\nFilas válidas:", len(validos))
print("Filas inválidas:", len(errores))
print("\nFilas inválidas y sus valores:")
print(errores)

importe_por_region = (
	validos.groupby("region")["importe"]
	.sum()
	.sort_values(ascending=False)
)

print("\nImporte total por región:")
print(importe_por_region)

top_productos = (
	validos.groupby("producto")["importe"]
	.sum()
	.sort_values(ascending=False)
	.head(3)
)

print("\nTop 3 productos por importe:")
print(top_productos)

clientes_recurrentes = (
	validos.groupby("cliente_id")
	.size()
	.loc[lambda compras: compras > 1]
	.sort_values(ascending=False)
)

print("\nClientes con más de una compra:")
print(clientes_recurrentes)

datos_dir = Path(__file__).resolve().parent.parent / "Datos"
validos.to_csv(datos_dir / "ventas_limpias.csv", index=False)

calidad = {
	"filas_totales": len(ventas),
	"filas_validas": len(validos),
	"filas_invalidas": len(errores),
	"importe_total": round(float(validos["importe"].sum()), 2),
}

with (datos_dir / "calidad_datos.json").open("w", encoding="utf-8") as archivo:
	json.dump(calidad, archivo, indent=2, ensure_ascii=False)