"""Mapa satelital con los caminos solicitados por los ejidatarios y los puntos de las fotos.

Uso: python mapa_ejido.py datos/capas.gpkg datos/ejidatarios.gpkg datos/fotos_puntos.csv <carpeta_dr> salida.png
"""
import io
import math
import os
import sys
import warnings

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.lines import Line2D
from PIL import Image

warnings.filterwarnings("ignore")
TILE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
R = 6378137.0
HALO = [pe.withStroke(linewidth=3, foreground="black")]


def satelite(x0, y0, x1, y1, z, cache):
    """Mosaico Esri World Imagery para una caja en EPSG:3857."""
    def t(x, y):
        n = 2 ** z
        return int((x + math.pi * R) / (2 * math.pi * R) * n), int((math.pi * R - y) / (2 * math.pi * R) * n)
    tx0, ty0 = t(x0, y1)
    tx1, ty1 = t(x1, y0)
    img = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    os.makedirs(cache, exist_ok=True)
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            f = f"{cache}/{z}_{tx}_{ty}.jpg"
            if not os.path.exists(f):
                r = requests.get(TILE.format(z=z, x=tx, y=ty), timeout=30, headers={"User-Agent": "mapa-research"})
                r.raise_for_status()
                open(f, "wb").write(r.content)
            img.paste(Image.open(f), ((tx - tx0) * 256, (ty - ty0) * 256))
    size = 2 * math.pi * R / 2 ** z
    ext = (-math.pi * R + tx0 * size, -math.pi * R + (tx1 + 1) * size,
           math.pi * R - (ty1 + 1) * size, math.pi * R - ty0 * size)
    return img, ext


def main(capas, ejido, fotos_csv, dr, salida):
    L = lambda capa, src=capas: gpd.read_file(src, layer=capa).to_crs(3857)
    and_ = L("andador_peatonal", ejido)
    reh = L("rehabilitacion_de_caminos", ejido)
    acc = L("Acceso_vehicular_al_bordo", ejido)
    bac = L("Bache", ejido)
    par = L("camino_a_parcelas", ejido)
    caja = pd.concat([and_.geometry, reh.geometry, acc.geometry, par.geometry, bac.geometry]).total_bounds
    x0, y0, x1, y1 = caja[0] - 450, caja[1] - 250, caja[2] + 350, caja[3] + 250

    img, ext = satelite(x0, y0, x1, y1, 17, "datos/teselas")
    fig, ax = plt.subplots(figsize=(8.5, 11), dpi=220)
    ax.imshow(img, extent=ext, zorder=0)
    ax.imshow([[0]], extent=ext, cmap="gray", alpha=0.18, zorder=1)  # aclara un poco el fondo

    cam = L("osm_caminos")
    agua = L("osm_agua")
    tren = L("osm_tren").query("railway == 'construction'")
    sec = gpd.read_file(f"{dr}/dr003_canales secundarios.kml").to_crs(3857)
    gen = gpd.read_file(f"{dr}/dr003_canales generales.kml").to_crs(3857)

    # Referencias
    pd.concat([sec, gen]).plot(ax=ax, color="#5ec8f2", linewidth=1.3, zorder=3)
    agua[agua.waterway == "river"].plot(ax=ax, color="#2b8cff", linewidth=2.4, zorder=3)
    cam[cam.highway.str.startswith("motorway")].plot(ax=ax, color="#ffffff", linewidth=1.2, alpha=0.8, zorder=3)
    tren.plot(ax=ax, color="#ffffff", linewidth=1.4, linestyle=(0, (5, 3)), zorder=3)

    # Propuesta
    reh.plot(ax=ax, color="#ff8c00", linewidth=4, zorder=5, path_effects=[pe.withStroke(linewidth=6, foreground="black")])
    and_.plot(ax=ax, color="#3ddc5f", linewidth=3.2, zorder=6, path_effects=[pe.withStroke(linewidth=5, foreground="black")])
    par.plot(ax=ax, color="#00e5ff", linewidth=3.6, zorder=6, path_effects=[pe.withStroke(linewidth=5.5, foreground="black")])
    acc.plot(ax=ax, color="#ff3df5", linewidth=3.6, zorder=6, path_effects=[pe.withStroke(linewidth=5.5, foreground="black")])
    bac.plot(ax=ax, marker="X", color="#ff2020", markersize=170, edgecolor="white", linewidth=1.2, zorder=8)

    # Etiquetas de referencia (fuera de la laguna para dejar Bojay limpio)
    def etiqueta(xy, txt, size=8.5, rot=0, color="white", style="normal"):
        ax.text(*xy, txt, color=color, fontsize=size, rotation=rot, weight="bold", style=style,
                ha="center", va="center", path_effects=HALO, zorder=9)
    lag = L("laguna_bojay").union_all()
    c = lag.centroid
    etiqueta((c.x - 120, c.y + 150), "Laguna\nde Bojay", 9.5, color="#bfe6ff", style="italic")
    etiqueta((caja[2] - 450, caja[3] - 100), "San Francisco\nBojay", 10)
    zi = L("zona_inundable").union_all().centroid
    etiqueta((zi.x - 420, zi.y - 60), "Tres\nCulturas", 10)
    etiqueta((caja[2] - 300, caja[1] + 150), "hacia el centro\nde Tula ↓", 8)
    for capa_g, txt in ((cam[cam.name == "Autopista Arco Norte"], "Arco Norte"), (tren, "Tren México–Querétaro"),
                        (agua[agua.waterway == "river"], "Río Tula")):
        vis = capa_g.union_all().intersection(gpd.GeoSeries.from_xy([x0, x1], [y0, y1]).union_all().envelope)
        if vis.is_empty:
            continue
        vis = max(getattr(vis, "geoms", [vis]), key=lambda s: s.length)
        p = vis.interpolate({"Río Tula": 0.55, "Tren México–Querétaro": 0.25}.get(txt, 0.18), normalized=True)
        etiqueta((p.x, p.y + 60), txt, 8, color="#f0f0f0")

    # Calles con nombre más largas dentro del mapa
    vista = gpd.GeoSeries.from_xy([x0, x1], [y0, y1]).union_all().envelope
    calles = cam[cam.name.notna() & (cam.name.str.len() < 28) & ~cam.highway.str.startswith("motorway") & cam.intersects(vista)].copy()
    calles["largo"] = calles.intersection(vista).length
    calles = calles.dissolve("name", aggfunc={"largo": "sum"}).sort_values("largo", ascending=False).head(6)
    for nombre, r in calles.iterrows():
        g = r.geometry.intersection(vista)
        g = max(getattr(g, "geoms", [g]), key=lambda s: s.length)
        p = g.interpolate(0.5, normalized=True)
        if p.distance(lag) < 200:
            continue
        ax.text(p.x, p.y, nombre, fontsize=6.5, color="#fff7c2", ha="center", va="center", path_effects=HALO, zorder=9)

    # Fotos numeradas
    fotos = pd.read_csv(fotos_csv)
    fg = gpd.GeoDataFrame(fotos, geometry=gpd.points_from_xy(fotos.x, fotos.y), crs=32614).to_crs(3857)
    for r in fg.itertuples():
        ax.plot(r.geometry.x, r.geometry.y, "o", ms=15, mfc="#ffd400", mec="black", mew=1.4, zorder=10)
        ax.text(r.geometry.x, r.geometry.y, str(r.num), fontsize=8.5, weight="bold", ha="center", va="center", zorder=11)

    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_axis_off()
    ley = [Line2D([], [], color="#3ddc5f", lw=4, label="Andador peatonal"),
           Line2D([], [], color="#ff8c00", lw=4, label="Rehabilitación de caminos"),
           Line2D([], [], color="#ff3df5", lw=4, label="Acceso vehicular al bordo"),
           Line2D([], [], color="#00e5ff", lw=4, label="Camino a parcelas"),
           Line2D([], [], marker="X", color="#ff2020", lw=0, ms=10, label="Bache"),
           Line2D([], [], marker="o", color="#ffd400", mec="black", lw=0, ms=10, label="Foto"),
           Line2D([], [], color="#2b8cff", lw=2.5, label="Río Tula"),
           Line2D([], [], color="#5ec8f2", lw=1.5, label="Canales DR003"),
           Line2D([], [], color="#777", lw=1.4, ls=(0, (5, 3)), label="Tren México–Querétaro")]
    ax.legend(handles=ley, loc="lower left", fontsize=7.5, framealpha=0.92)
    ax.text(x1 - 40, y1 - 40, "Imagen: Esri World Imagery · Calles: © OpenStreetMap", fontsize=5.5, color="white",
            ha="right", va="top", path_effects=HALO)
    fig.savefig(salida, bbox_inches="tight", pad_inches=0.02)
    print(salida)


if __name__ == "__main__":
    main(*sys.argv[1:6])
