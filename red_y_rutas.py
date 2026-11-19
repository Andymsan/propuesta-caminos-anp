"""Red de caminos candidata, rutas de menor costo e indicadores.

Uso: python red_y_rutas.py datos/capas.gpkg datos/puntos.csv resultados

Modos:
  activo     a pie o en bici. Prefiere bordos y brechas existentes; puede usar
             conectores nuevos cortos (sendero a construir).
  vehicular  visitantes en auto. Solo caminos existentes, castigo fuerte dentro
             del ANP fuera de zona urbana y prohibido en la zona inundable. Se
             estaciona en el borde (nodo urbano o fuera del ANP) y sigue a pie.
"""
import sys
import warnings

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString, Point

warnings.filterwarnings("ignore")
CRS = 32614

# Factor de costo por metro (modo activo). None = no permitido.
ACTIVO = {
    "bordo": 0.8, "bordo_bojay": 0.8, "path": 0.9, "footway": 0.9, "cycleway": 0.8,
    "pedestrian": 0.9, "track": 0.9, "steps": 1.5, "living_street": 1.0, "residential": 1.0,
    "service": 1.0, "unclassified": 1.0, "tertiary": 1.3, "tertiary_link": 1.3,
    "secondary": 1.8, "secondary_link": 1.8, "primary": 2.5, "primary_link": 2.5,
    "conector": 2.0,
}
# Factor de costo por metro (modo vehicular). Terracería más lenta.
VEHICULAR = {
    "motorway": 0.6, "motorway_link": 0.8, "trunk": 0.7, "primary": 0.8, "primary_link": 0.9,
    "secondary": 0.9, "secondary_link": 1.0, "tertiary": 1.0, "tertiary_link": 1.0,
    "unclassified": 1.2, "residential": 1.2, "living_street": 2.0, "service": 1.5, "track": 2.0,
}
CASTIGO_ANP_RURAL = 6.0     # vehicular dentro del ANP fuera de zona urbana
CASTIGO_CRUCE_NUEVO = 300   # m equivalentes por cada cruce de canal/corriente en conector nuevo
CONECTOR_MAX_M = 250        # largo máximo de un sendero nuevo para cerrar huecos
CAMINATA_MAX_M = 1500       # distancia máxima a pie desde el estacionamiento
PESO_CAMINATA = 2.0         # cuánto pesa caminar frente a manejar al elegir estacionamiento
URBANO_RADIO_M, URBANO_MIN_EDIF = 75, 6


def nodo(xy):
    return (round(xy[0], 1), round(xy[1], 1))


def agregar_lineas(G, gdf, tipo_col=None, tipo=None, fuente=""):
    for _, r in gdf.iterrows():
        t = tipo or r[tipo_col]
        for g in getattr(r.geometry, "geoms", [r.geometry]):
            c = list(g.coords)
            for a, b in zip(c[:-1], c[1:]):
                if a == b:
                    continue
                G.add_edge(nodo(a), nodo(b), tipo=t, fuente=fuente, nombre=r.get("name"),
                           largo=float(np.hypot(b[0] - a[0], b[1] - a[1])))


def conectar(G, origenes, destinos_xy, tree, max_m, tipo="conector"):
    """Une cada nodo de `origenes` con el nodo de `destinos_xy` más cercano (si está a < max_m)."""
    for n in origenes:
        i = tree.nearest(Point(n))
        d = destinos_xy[i]
        dist = float(np.hypot(d[0] - n[0], d[1] - n[1]))
        if 0 < dist <= max_m and not G.has_edge(n, d):
            G.add_edge(n, d, tipo=tipo, fuente="propuesto", nombre=None, largo=dist)


def construir_red(capas):
    G = nx.Graph()
    cam = gpd.read_file(capas, layer="osm_caminos")
    cam = cam[~cam.highway.isin(["construction", "corridor", "proposed", "platform"])]
    agregar_lineas(G, cam, tipo_col="highway", fuente="OSM")
    osm_nodos = list(G.nodes)

    bordos = gpd.read_file(capas, layer="bordos_tc")
    lag = gpd.read_file(capas, layer="laguna_bojay")
    anillo = gpd.GeoDataFrame(geometry=[lag.union_all().exterior if lag.union_all().geom_type == "Polygon"
                                        else max(lag.union_all().geoms, key=lambda p: p.area).exterior], crs=CRS)
    for gdf, t in ((bordos, "bordo"), (anillo, "bordo_bojay")):
        dens = gdf.geometry.segmentize(25)
        agregar_lineas(G, gpd.GeoDataFrame(geometry=dens, crs=CRS), tipo=t, fuente="bordo existente")

    # Bordos -> red OSM: conectores cortos donde el bordo toca o casi toca un camino
    tree_osm = shapely.STRtree([Point(n) for n in osm_nodos])
    bordo_nodos = [n for n, d in G.nodes(data=True) if any(G.edges[n, m]["tipo"].startswith("bordo") for m in G[n])]
    conectar(G, bordo_nodos, osm_nodos, tree_osm, 40)

    # Huecos: puntas muertas de brechas/veredas cerca del ANP -> bordos o red, como sendero nuevo
    puntas = [n for n in G.nodes if G.degree(n) == 1 and
              any(G.edges[n, m]["tipo"] in ("track", "path", "footway", "unclassified", "service") for m in G[n])]
    objetivo = [n for n in G.nodes if n not in set(puntas)]
    tree_obj = shapely.STRtree([Point(n) for n in objetivo])
    for p in puntas:
        cercanos = tree_obj.query(Point(p), predicate="dwithin", distance=CONECTOR_MAX_M)
        comp = nx.node_connected_component(G, p) if len(G[p]) else {p}
        mejor = None
        for i in cercanos:
            q = objetivo[i]
            if q in comp and nx.has_path(G, p, q) and nx.shortest_path_length(G, p, q, weight="largo") < 3 * CONECTOR_MAX_M:
                continue  # ya se llega fácil por la red
            d = float(np.hypot(q[0] - p[0], q[1] - p[1]))
            if mejor is None or d < mejor[1]:
                mejor = (q, d)
        if mejor:
            G.add_edge(p, mejor[0], tipo="conector", fuente="propuesto", nombre=None, largo=mejor[1])
    return G


def atributos(G, capas):
    """Agrega a cada arista: dentro del ANP, zona inundable, urbano, cruces con agua."""
    filas = [{"u": u, "v": v, **d, "geometry": LineString([u, v])} for u, v, d in G.edges(data=True)]
    E = gpd.GeoDataFrame(filas, crs=CRS)
    mid = E.geometry.interpolate(0.5, normalized=True)

    anp = gpd.read_file(capas, layer="anp").union_all()
    zi = gpd.read_file(capas, layer="zona_inundable").union_all()
    E["en_anp"] = mid.within(anp)
    E["en_zona_inundable"] = mid.within(zi)

    edif = gpd.read_file(capas, layer="edificios").centroid
    tree_e = shapely.STRtree(edif.values)
    idx = tree_e.query(mid.values, predicate="dwithin", distance=URBANO_RADIO_M)
    conteo = np.bincount(idx[0], minlength=len(E))
    E["urbano"] = conteo >= URBANO_MIN_EDIF

    agua = pd.concat([gpd.read_file(capas, layer="canales").assign(clase="canal")[["clase", "geometry"]],
                      gpd.read_file(capas, layer="corrientes").assign(clase="corriente")[["clase", "geometry"]]])
    tree_a = shapely.STRtree(agua.geometry.values)
    idx = tree_a.query(E.geometry.values, predicate="intersects")
    E["cruces_agua"] = np.bincount(idx[0], minlength=len(E))

    parc = pd.concat([gpd.read_file(capas, layer="parcelas_ran")[["geometry"]],
                      gpd.read_file(capas, layer="parcelas_zf")[["geometry"]]])
    tree_p = shapely.STRtree(parc.geometry.values)
    idx = tree_p.query(mid.values, predicate="dwithin", distance=15)
    E["junto_parcela"] = np.bincount(idx[0], minlength=len(E)) > 0

    for u, v, r in zip(E.u, E.v, E.itertuples()):
        G.edges[u, v].update(en_anp=r.en_anp, en_zona_inundable=r.en_zona_inundable, urbano=r.urbano,
                             cruces_agua=int(r.cruces_agua), junto_parcela=r.junto_parcela)
    return E, agua


def costo_activo(u, v, d):
    f = ACTIVO.get(d["tipo"])
    if f is None:
        return None
    c = d["largo"] * f
    if d["tipo"] == "conector":
        c += CASTIGO_CRUCE_NUEVO * d.get("cruces_agua", 0)
    return c


def costo_vehicular(u, v, d):
    f = VEHICULAR.get(d["tipo"])
    if f is None or d.get("en_zona_inundable"):
        return None
    if d.get("en_anp") and not d.get("urbano"):
        f *= CASTIGO_ANP_RURAL
    return d["largo"] * f


def cruces_distintos(geom, agua, radio=25):
    """Número de cruces distintos de una línea con canales/corrientes (puntos a < radio se agrupan)."""
    pts = []
    for g in agua.geometry.intersection(geom):
        pts += [p for p in getattr(g, "geoms", [g]) if not p.is_empty and p.geom_type == "Point"]
    if not pts:
        return 0
    return len(shapely.union_all([p.buffer(radio) for p in pts]).geoms) if len(pts) > 1 and \
        shapely.union_all([p.buffer(radio) for p in pts]).geom_type == "MultiPolygon" else 1


def nodo_cercano(G_nodos, tree, xy):
    i = tree.nearest(Point(xy))
    n = G_nodos[i]
    return n, float(np.hypot(n[0] - xy[0], n[1] - xy[1]))


def resumen_ruta(G, camino, modo, origen, destino, extra=None):
    aristas = [G.edges[a, b] for a, b in zip(camino[:-1], camino[1:])]
    L = sum(d["largo"] for d in aristas) or 1.0
    def km(cond):
        return round(sum(d["largo"] for d in aristas if cond(d)) / 1000, 2)
    r = {
        "modo": modo, "origen": origen, "destino": destino,
        "km_total": round(L / 1000, 2),
        "km_existente": km(lambda d: d["fuente"] != "propuesto"),
        "km_sobre_bordo": km(lambda d: d["tipo"].startswith("bordo")),
        "km_nuevo": km(lambda d: d["fuente"] == "propuesto"),
        "km_en_anp": km(lambda d: d.get("en_anp")),
        "km_zona_inundable": km(lambda d: d.get("en_zona_inundable")),
        "km_anp_no_urbano": km(lambda d: d.get("en_anp") and not d.get("urbano")),
        "cruces_canal_o_corriente": int(sum(d.get("cruces_agua", 0) for d in aristas)),
        "cruces_en_tramo_nuevo": int(sum(d.get("cruces_agua", 0) for d in aristas if d["fuente"] == "propuesto")),
        "km_junto_parcelas": km(lambda d: d.get("junto_parcela")),
    }
    # Riesgo de urbanización inducida: frente vehicular nuevo o mejorado en suelo no urbano del ANP
    r["km_riesgo_urbanizacion"] = r["km_anp_no_urbano"] if modo == "vehicular" else 0.0
    r.update(extra or {})
    geom = LineString(camino)
    return r, geom


def main(capas, puntos_csv, salida):
    G = construir_red(capas)
    E, agua = atributos(G, capas)
    print(f"red: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas, "
          f"{E[E.fuente == 'propuesto'].largo.sum() / 1000:.1f} km de conectores candidatos")

    pts = pd.read_csv(puntos_csv)
    pts = pts[pts.x.notna() & pts.y.notna()]
    P = {r.id: (r.x, r.y, r.nombre, r.rol) for r in pts.itertuples()}

    GA = nx.Graph(((u, v, {"w": c}) for u, v, d in G.edges(data=True) if (c := costo_activo(u, v, d)) is not None))
    GV = nx.Graph(((u, v, {"w": c}) for u, v, d in G.edges(data=True) if (c := costo_vehicular(u, v, d)) is not None))
    # Solo el componente principal de cada modo (evita ajustar a fragmentos aislados)
    GA = GA.subgraph(max(nx.connected_components(GA), key=len)).copy()
    GV = GV.subgraph(max(nx.connected_components(GV), key=len)).copy()
    nA, nV = list(GA.nodes), list(GV.nodes)
    tA, tV = shapely.STRtree([Point(n) for n in nA]), shapely.STRtree([Point(n) for n in nV])
    borde = [n for n in GV.nodes if all(not G.edges[n, m].get("en_anp") or G.edges[n, m].get("urbano") for m in G[n])]

    filas, geoms, estac = [], [], []
    origenes = [k for k, v in P.items() if v[3] == "origen"]
    destinos = [k for k, v in P.items() if v[3] == "destino"]
    for o in origenes:
        noA, soA = nodo_cercano(nA, tA, P[o][:2])
        noV, soV = nodo_cercano(nV, tV, P[o][:2])
        for d in destinos:
            nd, sd = nodo_cercano(nA, tA, P[d][:2])
            # Activo
            cam = nx.shortest_path(GA, noA, nd, weight="w")
            r, g = resumen_ruta(G, cam, "activo", P[o][2], P[d][2],
                                {"ajuste_origen_m": round(soA), "ajuste_destino_m": round(sd)})
            filas.append(r); geoms.append(g)
            # Vehicular + caminata desde estacionamiento de borde
            no, extra = noV, {"ajuste_origen_m": round(soV), "ajuste_destino_m": round(sd)}
            dist_v = nx.single_source_dijkstra_path_length(GV, no, weight="w")
            dist_a, path_a = nx.single_source_dijkstra(GA, nd, weight="w", cutoff=CAMINATA_MAX_M * 1.5)
            cand = [(dist_v[n] + PESO_CAMINATA * dist_a[n], n) for n in borde if n in dist_v and n in dist_a
                    and nx.has_path(GA, n, nd)]
            if not cand:
                continue
            _, p = min(cand)
            cam_v = nx.shortest_path(GV, no, p, weight="w")
            cam_a = list(reversed(path_a[p]))
            rv, gv = resumen_ruta(G, cam_v, "vehicular", P[o][2], P[d][2], extra) if len(cam_v) > 1 else (None, None)
            ra, ga = resumen_ruta(G, cam_a, "vehicular_caminata", P[o][2], P[d][2], extra) if len(cam_a) > 1 else (None, None)
            for r, g in ((rv, gv), (ra, ga)):
                if r:
                    filas.append(r); geoms.append(g)
            estac.append({"origen": P[o][2], "destino": P[d][2], "caminata_m": round(sum(
                G.edges[a, b]["largo"] for a, b in zip(cam_a[:-1], cam_a[1:]))), "geometry": Point(p)})

    rutas = gpd.GeoDataFrame(filas, geometry=geoms, crs=CRS)
    rutas["cruces_canal_o_corriente"] = [cruces_distintos(g, agua) for g in rutas.geometry]
    rutas.drop(columns="geometry").to_csv(f"{salida}/rutas_resumen.csv", index=False)

    # Estacionamientos de borde: agrupar los que caen a < 150 m
    est = gpd.GeoDataFrame(estac, crs=CRS)
    if len(est):
        est["grupo"] = est.buffer(150).apply(lambda b: est.index[est.intersects(b)].min())
        est = est.dissolve("grupo", aggfunc={"origen": lambda s: "; ".join(sorted(set(s))),
                                             "destino": lambda s: "; ".join(sorted(set(s))),
                                             "caminata_m": "max"}).reset_index(drop=True)
        est.geometry = est.centroid

    # Cruces con agua sobre las rutas (requieren estructura o verificación)
    ruta_union = rutas.dissolve("modo").reset_index()
    cruces = []
    for _, r in ruta_union.iterrows():
        x = agua.geometry.intersection(r.geometry)
        for g, clase in zip(x, agua.clase):
            for p in getattr(g, "geoms", [g]):
                if not p.is_empty and p.geom_type == "Point":
                    cruces.append({"modo": r.modo, "clase": clase, "geometry": p})
    cruces = gpd.GeoDataFrame(cruces, crs=CRS).drop_duplicates("geometry") if cruces else gpd.GeoDataFrame(
        columns=["modo", "clase", "geometry"], crs=CRS)

    # Caminos de saca: brechas existentes dentro del ANP que dan servicio a parcelas
    saca = E[(E.tipo.isin(["track", "unclassified", "service"])) & E.en_anp & E.junto_parcela & ~E.urbano]
    saca = saca.dissolve().explode(index_parts=False)
    saca = gpd.GeoDataFrame(geometry=shapely.line_merge(saca.geometry.values), crs=CRS).explode(index_parts=False)
    saca["largo_m"] = saca.length.round()
    saca = saca[saca.largo_m > 30]

    out = f"{salida}/red.gpkg"
    E.drop(columns=["u", "v"]).to_file(out, layer="red", driver="GPKG")
    rutas.to_file(out, layer="rutas", driver="GPKG")
    est.to_file(out, layer="estacionamientos_borde", driver="GPKG")
    cruces.to_file(out, layer="cruces_agua", driver="GPKG")
    saca.to_file(out, layer="caminos_saca", driver="GPKG")
    E[E.fuente == "propuesto"].drop(columns=["u", "v"]).to_file(out, layer="conectores_candidatos", driver="GPKG")

    pd.set_option("display.width", 250)
    print(rutas.drop(columns="geometry")[["modo", "origen", "destino", "km_total", "km_sobre_bordo", "km_nuevo",
                                          "km_zona_inundable", "km_riesgo_urbanizacion", "cruces_canal_o_corriente"]])
    print(f"estacionamientos de borde: {len(est)}; cruces con agua en rutas: {len(cruces)}; "
          f"caminos de saca en ANP: {saca.largo_m.sum() / 1000:.1f} km")


if __name__ == "__main__":
    main(*sys.argv[1:4])
