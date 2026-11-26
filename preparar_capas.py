"""Recorta y unifica las capas base en datos/capas.gpkg (EPSG:32614).

Uso: python preparar_capas.py <carpeta_semarnat> <osm.json> <bordos.gpkg> datos/capas.gpkg
"""
import glob
import json
import sys
import warnings

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon, box

warnings.filterwarnings("ignore")
CRS = 32614
MARGEN_M = 2500  # recorte alrededor del ANP


def leer(ruta, recorte):
    g = gpd.read_file(ruta)
    g = g.set_crs(4326) if g.crs is None else g
    g = g.to_crs(CRS)
    g = g[g.is_valid | g.geometry.notna()]
    return gpd.clip(g, recorte)


def osm_a_capas(ruta_json, recorte):
    """Separa el JSON de Overpass en caminos, agua, tren y sitios."""
    elementos = json.load(open(ruta_json, encoding="utf8"))["elements"]
    filas = []
    for e in elementos:
        t = e.get("tags", {})
        if e["type"] == "way" and "geometry" in e:
            xy = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if len(xy) < 2:
                continue
            cerrado = xy[0] == xy[-1] and len(xy) > 3
            area = cerrado and any(k in t for k in ("landuse", "leisure")) or (cerrado and "historic" in t)
            geom = Polygon(xy) if area else LineString(xy)
            filas.append({"osm_id": e["id"], "geometry": geom, **{k: t.get(k) for k in
                          ("highway", "waterway", "railway", "landuse", "leisure", "historic",
                           "name", "surface", "tracktype", "access", "bridge")}})
        elif e["type"] == "node":
            from shapely.geometry import Point
            filas.append({"osm_id": e["id"], "geometry": Point(e["lon"], e["lat"]),
                          "railway": t.get("railway"), "name": t.get("name")})
    g = gpd.GeoDataFrame(filas, crs=4326).to_crs(CRS)
    g = gpd.clip(g, recorte)
    lin = g[g.geom_type.isin(["LineString", "MultiLineString"])]
    return {
        "osm_caminos": lin[lin.highway.notna()],
        "osm_agua": lin[lin.waterway.notna()],
        "osm_tren": lin[lin.railway.notna()],
        "osm_sitios": g[g.historic.notna() | (g.leisure == "nature_reserve")],
    }


def main(base, osm_json, bordos_gpkg, salida):
    B = base.rstrip("/\\") + "/"
    RT = B + "01_Rio Tula/"
    anp = gpd.read_file(B + "rios-vivos/data/tula/nueva_anp.geojson").to_crs(CRS)[["geometry"]]
    anp["nombre"] = "APFF Corredor biocultural Tres Culturas (propuesta)"
    recorte = box(*anp.buffer(MARGEN_M).total_bounds)

    capas = {"anp": anp}
    capas["pn_tula"] = leer(RT + "00_Mapa base/04_Areas protegidas/232_ANP_ITRF08_15042025/"
                            "232_ANP_ITRF08_15042025.shp", recorte)[["NOMBRE", "CAT_MANEJO", "geometry"]]
    capas["zona_inundable"] = leer(B + "rios-vivos/data/tula/zona_inundable.geojson", recorte)[["geometry"]]
    capas["zona_federal"] = leer(B + "rios-vivos/data/tula/zona_federal.geojson", recorte)[["geometry"]]
    capas["laguna_bojay"] = leer(B + "rios-vivos/data/tula/bojay.geojson", recorte)[["geometry"]]
    capas["bordos_tc"] = gpd.read_file(bordos_gpkg, layer="bordo").to_crs(CRS)

    # Canales de riego (DR003) + canales INEGI 1:50k
    dr = leer(RT + "00_Mapa base/06_Distritos de riego/Canales 3DR_Tutla/"
                   "Canales 3DR_Tutla/DR003/dr003_rc.shp", recorte)
    dr = dr.assign(fuente="Conagua DR003", tipo=dr.TIPO_RED.str.title(), nivel=dr.NIVEL_RED,
                   revest=dr.TIPO_REV, nombre=dr.NOMBRE)[["fuente", "tipo", "nivel", "revest", "nombre", "geometry"]]
    inegi = []
    for f in glob.glob(RT + "00_Mapa base/02_Topografia/Cartas INEGI y DEM/*/conjunto_de_datos/canal50_l.shp"):
        g = leer(f, recorte)
        if len(g):
            inegi.append(g.assign(fuente="INEGI 1:50k", tipo="Canal", nivel=None, revest=None,
                                  nombre=g.get("nombre"))[["fuente", "tipo", "nivel", "revest", "nombre", "geometry"]])
    capas["canales"] = gpd.GeoDataFrame(pd.concat([dr] + inegi, ignore_index=True), crs=CRS)

    corr = [leer(f, recorte) for f in glob.glob(RT + "00_Mapa base/02_Topografia/Cartas INEGI y DEM/*/conjunto_de_datos/corriente_ag50_l.shp")]
    corr = [c for c in corr if len(c)]
    capas["corrientes"] = gpd.GeoDataFrame(pd.concat(corr, ignore_index=True), crs=CRS)[["nombre", "condicion", "geometry"]]

    loc = [leer(f, recorte) for f in glob.glob(RT + "00_Mapa base/02_Topografia/Cartas INEGI y DEM/*/conjunto_de_datos/localidad50_p.shp")]
    capas["localidades"] = gpd.GeoDataFrame(pd.concat([l for l in loc if len(l)], ignore_index=True), crs=CRS)[["nombre", "nume_hab", "geometry"]]

    capas["edificios"] = leer(RT + "11_Diseno/03_Capas de diseno/shp/buildings 32614.shp", recorte)[["confidence", "geometry"]]
    capas["parcelas_ran"] = leer(RT + "07_Social y territorio/02_Tenencia de la tierra/"
                                 "ran_parcelas_hidalgo_tula de allende.kml", recorte)[["Name", "geometry"]]
    capas["parcelas_zf"] = leer(RT + "04_Inundaciones/02_Delimitacion federal/parcelas_zona_inundable.geojson", recorte)[["geometry"]]
    capas["colectores"] = leer(RT + "02_Calidad del agua y saneamiento/05_Colectores/colectores.geojson", recorte)[["Name", "geometry"]]

    capas.update(osm_a_capas(osm_json, recorte))

    for nombre, g in capas.items():
        g = g[~g.geometry.is_empty]
        g.to_file(salida, layer=nombre, driver="GPKG")
        print(f"{nombre:16s} {len(g):6d}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
