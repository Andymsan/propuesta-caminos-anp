import sys
import warnings

import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

warnings.filterwarnings("ignore")
CRS = 32614
C = {"activo": "#1b9e4b", "vehicular": "#e07b00", "caminata": "#1b9e4b", "agua": "#2c7fb8",
     "corriente": "#7fb7d9", "bordo": "#8c5a2b", "anp": "#2f6b2f", "zi": "#cfe8f3", "urbano": "#d9d9d9",
     "conector": "#d62728", "saca": "#b8860b"}


def leer(g, capa):
    return gpd.read_file(g, layer=capa)


def png(capas, red, pts, ruta):
    fig, ax = plt.subplots(figsize=(11, 13), dpi=200)
    anp = leer(capas, "anp")
    caja = pd.concat([anp.geometry, gpd.GeoSeries(gpd.points_from_xy(pts.x, pts.y), crs=CRS)])
    x0, y0, x1, y1 = caja.buffer(700).total_bounds
    leer(capas, "edificios").plot(ax=ax, color=C["urbano"], linewidth=0)
    leer(capas, "zona_inundable").plot(ax=ax, color=C["zi"], edgecolor="none")
    leer(capas, "laguna_bojay").plot(ax=ax, color="#a6cee3", edgecolor="#2c7fb8", linewidth=0.6)
    leer(capas, "osm_caminos").plot(ax=ax, color="#9e9e9e", linewidth=0.35)
    leer(capas, "corrientes").plot(ax=ax, color=C["corriente"], linewidth=0.8)
    leer(capas, "canales").plot(ax=ax, color=C["agua"], linewidth=1.1)
    leer(capas, "osm_tren").query("railway == 'construction'").plot(ax=ax, color="#555", linewidth=1.4, linestyle=(0, (4, 2)))
    leer(capas, "pn_tula").boundary.plot(ax=ax, color=C["anp"], linewidth=1.0, linestyle=":")
    anp.boundary.plot(ax=ax, color=C["anp"], linewidth=1.6)
    leer(capas, "bordos_tc").plot(ax=ax, color=C["bordo"], linewidth=2.2)
    leer(red, "caminos_saca").plot(ax=ax, color=C["saca"], linewidth=1.6)
    leer(red, "conectores_candidatos").plot(ax=ax, color=C["conector"], linewidth=0.8, linestyle=(0, (1, 1)))

    rutas = leer(red, "rutas")
    rutas[rutas.modo == "vehicular"].plot(ax=ax, color=C["vehicular"], linewidth=2.6, alpha=0.85)
    rutas[rutas.modo == "activo"].plot(ax=ax, color=C["activo"], linewidth=3.2, alpha=0.85)
    rutas[rutas.modo == "vehicular_caminata"].plot(ax=ax, color="white", linewidth=1.2, linestyle=(0, (2, 2)))
    cr = leer(red, "cruces_agua")
    if len(cr):
        cr.plot(ax=ax, marker="o", markersize=26, facecolor="white", edgecolor=C["agua"], linewidth=1.2, zorder=6)
    est = leer(red, "estacionamientos_borde")
    est.plot(ax=ax, marker="s", markersize=110, color="#1f3b73", zorder=7)
    for p in est.geometry:
        ax.text(p.x, p.y, "P", color="white", fontsize=8, ha="center", va="center", weight="bold", zorder=8)
    for r in pts.itertuples():
        ax.plot(r.x, r.y, marker="*" if r.rol == "destino" else "o", color="black", markersize=11 if r.rol == "destino" else 7, zorder=9)
        ax.annotate(r.nombre, (r.x, r.y), xytext=(6, 6), textcoords="offset points", fontsize=7.5, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8), zorder=10)

    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.set_axis_off()
    ley = [Line2D([], [], color=C["activo"], lw=3, label="Ruta a pie / bici (activo)"),
           Line2D([], [], color=C["vehicular"], lw=3, label="Ruta vehicular hasta el borde"),
           Line2D([], [], color="black", lw=1, ls=(0, (2, 2)), label="Tramo a pie desde estacionamiento"),
           Line2D([], [], color=C["bordo"], lw=2.5, label="Bordos Tres Culturas (sendero)"),
           Line2D([], [], color=C["saca"], lw=2, label="Caminos de saca en el ANP (conservar)"),
           Line2D([], [], color=C["conector"], lw=1, ls=(0, (1, 1)), label="Conectores candidatos (< 250 m)"),
           Line2D([], [], color=C["agua"], lw=1.5, label="Canales (DR003 / INEGI)"),
           Line2D([], [], color=C["corriente"], lw=1.5, label="Corrientes (INEGI)"),
           Line2D([], [], marker="o", color="w", markeredgecolor=C["agua"], ms=7, label="Cruce con agua: estructura"),
           Line2D([], [], marker="s", color="#1f3b73", lw=0, ms=9, label="Estacionamiento de borde"),
           Line2D([], [], color="#555", lw=1.4, ls=(0, (4, 2)), label="Tren México-Querétaro"),
           Line2D([], [], color=C["anp"], lw=1.6, label="ANP propuesta / PN Tula (punteado)"),
           Patch(color=C["zi"], label="Zona inundable Tres Culturas"),
           Patch(color=C["urbano"], label="Edificaciones")]
    ax.legend(handles=ley, loc="lower left", fontsize=7.5, frameon=True, framealpha=0.95)
    ax.set_title("Propuesta de caminos ANP: Tres Culturas y Bojay", fontsize=13, weight="bold", loc="left")
    fig.tight_layout()
    fig.savefig(ruta, bbox_inches="tight")
    print(ruta)


def html(capas, red, pts, ruta):
    anp = leer(capas, "anp").to_crs(4326)
    c = anp.union_all().centroid
    m = folium.Map(location=[c.y, c.x], zoom_start=14, tiles=None)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery", name="Satélite").add_to(m)
    folium.TileLayer("OpenStreetMap", name="OSM").add_to(m)

    def capa(g, nombre, estilo, tooltip=None, mostrar=True):
        if len(g) == 0:
            return
        g = g.to_crs(4326)
        g = g[[c for c in g.columns if g[c].dtype != object or c == "geometry" or c in (tooltip or [])]] if tooltip is None else g
        folium.GeoJson(g, name=nombre, style_function=lambda _: estilo, show=mostrar,
                       tooltip=folium.GeoJsonTooltip(fields=tooltip) if tooltip else None).add_to(m)

    capa(anp, "ANP propuesta", {"color": C["anp"], "weight": 2, "fill": False})
    capa(leer(capas, "zona_inundable"), "Zona inundable", {"color": C["agua"], "weight": 0, "fillColor": C["zi"], "fillOpacity": 0.4})
    capa(leer(capas, "canales")[["fuente", "tipo", "nivel", "geometry"]].fillna(""), "Canales", {"color": C["agua"], "weight": 3}, ["fuente", "tipo", "nivel"])
    capa(leer(capas, "corrientes")[["geometry"]], "Corrientes", {"color": C["corriente"], "weight": 2})
    capa(leer(capas, "bordos_tc"), "Bordos Tres Culturas", {"color": C["bordo"], "weight": 4})
    capa(leer(red, "caminos_saca"), "Caminos de saca", {"color": C["saca"], "weight": 3}, ["largo_m"])
    capa(leer(red, "conectores_candidatos")[["largo", "cruces_agua", "geometry"]], "Conectores candidatos",
         {"color": C["conector"], "weight": 2, "dashArray": "3 3"}, ["largo", "cruces_agua"], mostrar=False)
    rutas = leer(red, "rutas")
    campos = ["modo", "origen", "destino", "km_total", "km_sobre_bordo", "km_zona_inundable",
              "km_riesgo_urbanizacion", "cruces_canal_o_corriente"]
    for modo, col, w in (("vehicular", C["vehicular"], 4), ("activo", C["activo"], 5), ("vehicular_caminata", "#ffffff", 2)):
        capa(rutas[rutas.modo == modo][campos + ["geometry"]], f"Rutas {modo}", {"color": col, "weight": w, "opacity": 0.85}, campos)
    for p in leer(red, "estacionamientos_borde").to_crs(4326).itertuples():
        folium.Marker([p.geometry.y, p.geometry.x], tooltip=f"Estacionamiento de borde · caminata {p.caminata_m} m",
                      icon=folium.Icon(color="darkblue", icon="car", prefix="fa")).add_to(m)
    for p in leer(red, "cruces_agua").to_crs(4326).itertuples():
        folium.CircleMarker([p.geometry.y, p.geometry.x], radius=5, color=C["agua"], fill=True, fill_color="white",
                            tooltip=f"Cruce con {p.clase} ({p.modo})").add_to(m)
    g = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts.x, pts.y), crs=CRS).to_crs(4326)
    for p in g.itertuples():
        folium.Marker([p.geometry.y, p.geometry.x], tooltip=p.nombre,
                      icon=folium.Icon(color="green" if p.rol == "destino" else "gray")).add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(ruta)
    print(ruta)


def main(capas, puntos_csv, salida):
    pts = pd.read_csv(puntos_csv).dropna(subset=["x", "y"])
    red = f"{salida}/red.gpkg"
    png(capas, red, pts, f"{salida}/mapa_propuesta.png")
    html(capas, red, pts, f"{salida}/mapa_interactivo.html")


if __name__ == "__main__":
    main(*sys.argv[1:4])
