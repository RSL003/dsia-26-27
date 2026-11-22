const byId = (id) => document.getElementById(id);
const boton = byId("predecir");
const numero = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 });

boton.addEventListener("click", async () => {
  boton.disabled = true;
  byId("estado").textContent = "Calculando la predicción…";
  byId("resultado").hidden = true;
  try {
    const respuesta = await fetch("/predict", { method: "POST" });
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.error || "El servicio no está disponible.");
    const p = datos.prediccion;
    const magnitud = p.magnitud === "8" ? "NO₂" : `Magnitud ${p.magnitud}`;
    byId("serie").textContent = `${p.estacion} · ${magnitud}`;
    byId("prediccion").textContent = `${numero.format(p.valor_predicho)} ${p.unidad}`;
    byId("observado").textContent = `${numero.format(p.ultimo_valor_observado)} ${p.unidad}`;
    byId("objetivo").textContent = p.objetivo_utc.replace("T", " ").replace("+00:00", "");
    byId("modelo").textContent = p.modelo;
    byId("informe").textContent = datos.informe.split("\n").slice(2).join("\n");
    byId("resultado").hidden = false;
    byId("estado").textContent = "Predicción recibida de la API.";
  } catch (error) {
    byId("estado").textContent = error.message;
  } finally {
    boton.disabled = false;
  }
});
