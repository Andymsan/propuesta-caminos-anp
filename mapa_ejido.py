"""Mapa satelital con los caminos solicitados por los ejidatarios y los puntos de las fotos.

Uso: python mapa_ejido.py datos/capas.gpkg datos/ejidatarios.gpkg datos/fotos_puntos.csv <carpeta_dr> salida.png
"""
import io
import math
import os
import sys
import warnings

import geopandas as gpd
import shapely.ops
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


FOTOS_NOTA = {1: 1, 2: 2, 3: 3, 4: 4, 6: 5, 8: 6}   # foto original -> número en la nota conceptual
COLOSIO = "Calle Luis Donaldo Colosio"
SANTA_ANA_OSM = [252732472, 252736656, 252736657]  # tramos OSM sin nombre de la carretera a Santa Ana
ASPECTO = 451.27559 / 578   # ancho / alto del mapa en la nota
CAPAS_REHAB = ["rehabilitacion_de_caminos", "camino_a_parcelas", "Acceso_vehicular_al_bordo"]


def conexiones(capas):
    """Calles con las que se conectan los caminos: Luis Donaldo Colosio y carretera a Santa Ana."""
    cam = gpd.read_file(capas, layer="osm_caminos")
    colosio = cam[cam.name == COLOSIO].dissolve().assign(nombre="Calle Luis Donaldo Colosio")
    sa = cam[cam.osm_id.isin(SANTA_ANA_OSM)].dissolve().assign(nombre="Carretera a Santa Ana")
    return pd.concat([colosio[["nombre", "geometry"]], sa[["nombre", "geometry"]]]).set_crs(32614).to_crs(3857)


def recortar_en_santa_ana(g, con):
    """Deja solo la parte del camino al poniente de su cruce con la carretera a Santa Ana."""
    import shapely
    linea = g.union_all()
    sa = con[con.nombre == "Carretera a Santa Ana"].union_all()
    cruce = linea.intersection(sa)
    cruce = cruce if cruce.geom_type == "Point" else list(cruce.geoms)[0]
    d = linea.project(cruce)
    tramos = [shapely.ops.substring(linea, 0, d), shapely.ops.substring(linea, d, linea.length)]
    oeste = min(tramos, key=lambda t: t.centroid.x)
    return gpd.GeoDataFrame(geometry=[oeste], crs=g.crs)


FOTO_4_EN_TRAMO = (464800, 2220076)  # la foto 4 se tomó al este de la carretera; se muestra sobre el tramo que queda


def main(capas, ejido, fotos_csv, dr, salida):
    """Mapa para la nota: solo vialidades a rehabilitar, fotos, río sin leyenda y calles de conexión."""
    L = lambda capa, src=capas: gpd.read_file(src, layer=capa).to_crs(3857)
    con = conexiones(capas)
    capas_rehab = []
    for c in CAPAS_REHAB:
        g = L(c, ejido)
        if c == "camino_a_parcelas":  # llega solo hasta la carretera a Santa Ana
            g = recortar_en_santa_ana(g, con)
        capas_rehab.append(g)
    rehab = pd.concat(capas_rehab)
    fotos = pd.read_csv(fotos_csv)
    fotos = fotos[fotos.num.isin(FOTOS_NOTA)].assign(num=lambda d: d.num.map(FOTOS_NOTA))
    fotos.loc[fotos.num == 4, ["x", "y"]] = FOTO_4_EN_TRAMO
    fg = gpd.GeoDataFrame(fotos, geometry=gpd.points_from_xy(fotos.x, fotos.y), crs=32614).to_crs(3857)
    caja = pd.concat([rehab.geometry, fg.geometry]).total_bounds
    x0, y0, x1, y1 = caja[0] - 450, caja[1] - 650, caja[2] + 450, caja[3] + 250
    # Misma proporción que la imagen de la nota (451 x 578 pt) para reemplazarla sin recortes
    ancho = (y1 - y0) * ASPECTO
    cx = (x0 + x1) / 2
    x0, x1 = cx - ancho / 2, cx + ancho / 2
    vista = gpd.GeoSeries.from_xy([x0, x1], [y0, y1]).union_all().envelope

    img, ext = satelite(x0, y0, x1, y1, 17, "datos/teselas")
    fig, ax = plt.subplots(figsize=(8.5, 11), dpi=220)
    ax.imshow(img, extent=ext, zorder=0)
    ax.imshow([[0]], extent=ext, cmap="gray", alpha=0.18, zorder=1)  # aclara un poco el fondo

    agua = L("osm_agua")
    agua[agua.waterway == "river"].plot(ax=ax, color="#2b8cff", linewidth=2.4, zorder=3)  # río, sin leyenda
    con.plot(ax=ax, color="white", linewidth=2.2, zorder=4, path_effects=[pe.withStroke(linewidth=4, foreground="black")])
    rehab.plot(ax=ax, color="#ff8c00", linewidth=4.2, zorder=5, path_effects=[pe.withStroke(linewidth=6.5, foreground="black")])

    for r in con.itertuples():
        g = r.geometry.intersection(vista)
        g = max(getattr(g, "geoms", [g]), key=lambda s: s.length)
        p = g.interpolate(0.45 if "Santa Ana" in r.nombre else 0.6, normalized=True)
        ax.text(p.x - 60, p.y, r.nombre, fontsize=9, weight="bold", color="black", ha="right", va="center", zorder=12,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", lw=0.8))

    for r in fg.itertuples():
        ax.plot(r.geometry.x, r.geometry.y, "o", ms=15, mfc="#ffd400", mec="black", mew=1.4, zorder=10)
        ax.text(r.geometry.x, r.geometry.y, str(r.num), fontsize=8.5, weight="bold", ha="center", va="center", zorder=11)

    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_axis_off()
    ley = [Line2D([], [], color="#ff8c00", lw=4.5, label="Vialidades a rehabilitar"),
           Line2D([], [], marker="o", color="#ffd400", mec="black", lw=0, ms=10, label="Foto")]
    ax.legend(handles=ley, loc="upper right", fontsize=8, framealpha=0.92)
    ax.text(x1 - 40, y0 + 40, "Imagen: Esri World Imagery · Calles: © OpenStreetMap", fontsize=5.5, color="white",
            ha="right", va="bottom", path_effects=HALO)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.set_size_inches(8.5, 8.5 / ASPECTO)
    fig.savefig(salida, pad_inches=0)
    print(salida)


if __name__ == "__main__":
    main(*sys.argv[1:6])
