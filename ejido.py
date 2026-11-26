import sys

import geopandas as gpd
import pandas as pd
import shapely
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Pt

import mapa_ejido as m

WAYBACK = ("https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/"
           "default028mm/MapServer/tile/45441/{z}/{y}/{x}")  # captura 2022-08-31
ANCHO_IN = 7.5
SUR_SANTA_ANA = (465499, 2218835)   # extremo sur de la carretera a Santa Ana (EPSG:32614)
EL_LLANO = (467385, 2217738)        # centro de El Llano, donde se ubicaría la estación (EPSG:32614)
NARANJA, AZUL, BLANCO, NEGRO, AMARILLO = (RGBColor(0xFF, 0x8C, 0x00), RGBColor(0x2B, 0x8C, 0xFF),
                                          RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0, 0, 0), RGBColor(0xFF, 0xD4, 0x00))


def main(capas, ejido, fotos_csv, salida):
    L = lambda c, src=capas: gpd.read_file(src, layer=c).to_crs(3857)
    con = m.conexiones(capas)
    rehab = []
    for c in m.CAPAS_REHAB:
        g = L(c, ejido)
        if c == "camino_a_parcelas":
            g = m.recortar_en_santa_ana(g, con)
        rehab.append(g)
    rehab = pd.concat(rehab)
    fotos = pd.read_csv(fotos_csv)
    fotos = fotos[fotos.num.isin(m.FOTOS_NOTA)].assign(num=lambda d: d.num.map(m.FOTOS_NOTA))
    fotos.loc[fotos.num == 4, ["x", "y"]] = m.FOTO_4_EN_TRAMO
    fg = gpd.GeoDataFrame(fotos, geometry=gpd.points_from_xy(fotos.x, fotos.y), crs=32614).to_crs(3857)

    caja = pd.concat([rehab.geometry, fg.geometry]).total_bounds
    x0, y0, x1, y1 = caja[0] - 450, caja[1] - 650, caja[2] + 450, caja[3] + 250
    ancho = (y1 - y0) * m.ASPECTO
    cx = (x0 + x1) / 2
    x0, x1 = cx - ancho / 2, cx + ancho / 2
    vista = shapely.box(x0, y0, x1, y1)

    m.TILE = WAYBACK
    img, ext = m.satelite(x0, y0, x1, y1, 17, "datos/teselas_2022")
    # recorta el mosaico exactamente a la vista
    ex0, ex1, ey0, ey1 = ext
    W, H = img.size
    px = lambda x: (x - ex0) / (ex1 - ex0) * W
    py = lambda y: (ey1 - y) / (ey1 - ey0) * H
    img.crop((int(px(x0)), int(py(y1)), int(px(x1)), int(py(y0)))).save("documentos/fondo_2022.jpg", quality=88)

    prs = Presentation()
    prs.slide_width = Emu(int(ANCHO_IN * 914400))
    prs.slide_height = Emu(int(ANCHO_IN / m.ASPECTO * 914400))
    sw, sh = prs.slide_width, prs.slide_height
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_picture("documentos/fondo_2022.jpg", 0, 0, sw, sh)
    X = lambda x: Emu(int((x - x0) / (x1 - x0) * sw))
    Y = lambda y: Emu(int((y1 - y) / (y1 - y0) * sh))

    def lineas(geom, color, ancho_pt, nombre, tolerancia):
        g = geom.intersection(vista).simplify(tolerancia)
        grupo = s.shapes.add_group_shape()
        grupo.name = nombre
        for parte in getattr(g, "geoms", [g]):
            if parte.is_empty or parte.geom_type != "LineString":
                continue
            c = list(parte.coords)
            for a, b in zip(c[:-1], c[1:]):
                ln = grupo.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, X(a[0]), Y(a[1]), X(b[0]), Y(b[1]))
                ln.line.color.rgb = color
                ln.line.width = Pt(ancho_pt)
        return grupo

    def texto(x, y, txt, tam=9, relleno=BLANCO, ancho_in=2.0, alto_in=0.28, centro=False):
        w, h = Emu(int(ancho_in * 914400)), Emu(int(alto_in * 914400))
        left = x - w // 2 if centro else x
        tb = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, y - h // 2, w, h)
        tb.fill.solid(); tb.fill.fore_color.rgb = relleno
        tb.line.color.rgb = NEGRO; tb.line.width = Pt(0.75)
        tf = tb.text_frame; tf.margin_left = tf.margin_right = Pt(3); tf.margin_top = tf.margin_bottom = Pt(1)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = txt; r.font.size = Pt(tam); r.font.bold = True; r.font.color.rgb = NEGRO
        return tb

    agua = L("osm_agua")
    lineas(agua[agua.waterway == "river"].union_all(), AZUL, 2.5, "Río Tula", 12)
    for r in con.itertuples():
        lineas(r.geometry, BLANCO, 2.25, r.nombre, 8)
    lineas(rehab.union_all(), NARANJA, 4.5, "Vialidades a rehabilitar", 5)

    # Etiquetas de las calles de conexión
    for r in con.itertuples():
        g = r.geometry.intersection(vista)
        g = max(getattr(g, "geoms", [g]), key=lambda t: t.length)
        p = g.interpolate(0.45 if "Santa Ana" in r.nombre else 0.6, normalized=True)
        ancho_lbl = 1.75 if "Santa Ana" in r.nombre else 2.15
        tb = texto(X(p.x) - Emu(int((ancho_lbl + 0.08) * 914400)), Y(p.y), r.nombre, ancho_in=ancho_lbl)
        tb.name = f"Etiqueta {r.nombre}"

    # Flecha hacia la estación del tren (El Llano): donde la carretera a Santa Ana sale del mapa por el sur,
    # apuntando hacia afuera en la dirección de la carretera
    sa = con[con.nombre == "Carretera a Santa Ana"].union_all()
    sa = shapely.line_merge(sa) if sa.geom_type == "MultiLineString" else sa
    sa = max(getattr(sa, "geoms", [sa]), key=lambda t: t.length)
    margen = vista.buffer(-60)  # el punto de salida, 60 m dentro del borde
    dentro = sa.intersection(margen)
    dentro = max(getattr(dentro, "geoms", [dentro]), key=lambda t: t.length)
    c = list(dentro.coords)
    fin = min((c[0], c[-1]), key=lambda p: p[1])           # extremo más al sur dentro del mapa
    d_fin = sa.project(shapely.Point(fin))
    ini_p = sa.interpolate(max(d_fin - 300, 0)) if sa.project(shapely.Point(sa.coords[0])) < d_fin else sa.interpolate(d_fin + 300)
    # el punto de inicio debe quedar al norte del final
    if ini_p.y < fin[1]:
        ini_p = sa.interpolate(d_fin + 300)
    ini = (ini_p.x, ini_p.y)
    fl = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, X(ini[0]), Y(ini[1]), X(fin[0]), Y(fin[1]))
    fl.name = "Flecha a la estación del tren"
    fl.line.color.rgb = BLANCO
    fl.line.width = Pt(3)
    from pptx.oxml.ns import qn
    ln_xml = fl.line._get_or_add_ln()
    tail = ln_xml.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln_xml.append(tail)
    tb = texto(X(fin[0]) - Emu(int(2.0 * 914400)), Y(fin[1]) - Emu(int(0.25 * 914400)),
               "Hacia la estación Tula del Tren México–Querétaro (El Llano, ~2.5 km)", tam=8, ancho_in=1.9, alto_in=0.42)
    tb.name = "Etiqueta estación del tren"

    # Fotos numeradas
    d = Emu(int(0.24 * 914400))
    for r in fg.itertuples():
        o = s.shapes.add_shape(MSO_SHAPE.OVAL, X(r.geometry.x) - d // 2, Y(r.geometry.y) - d // 2, d, d)
        o.name = f"Foto {r.num}"
        o.fill.solid(); o.fill.fore_color.rgb = AMARILLO
        o.line.color.rgb = NEGRO; o.line.width = Pt(1)
        tf = o.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        t = p.add_run(); t.text = str(r.num); t.font.size = Pt(9); t.font.bold = True; t.font.color.rgb = NEGRO

    # Leyenda
    lx, ly = sw - Emu(int(2.25 * 914400)), Emu(int(0.12 * 914400))
    caja_ley = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, lx, ly, Emu(int(2.1 * 914400)), Emu(int(0.62 * 914400)))
    caja_ley.name = "Leyenda"
    caja_ley.fill.solid(); caja_ley.fill.fore_color.rgb = BLANCO; caja_ley.line.color.rgb = RGBColor(0x99, 0x99, 0x99)
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, lx + Emu(91440), ly + Emu(int(0.2 * 914400)),
                                lx + Emu(int(0.45 * 914400)), ly + Emu(int(0.2 * 914400)))
    ln.line.color.rgb = NARANJA; ln.line.width = Pt(4.5)
    o = s.shapes.add_shape(MSO_SHAPE.OVAL, lx + Emu(int(0.19 * 914400)), ly + Emu(int(0.36 * 914400)), Emu(int(0.17 * 914400)), Emu(int(0.17 * 914400)))
    o.fill.solid(); o.fill.fore_color.rgb = AMARILLO; o.line.color.rgb = NEGRO
    for i, txt in enumerate(["Vialidades a rehabilitar", "Foto"]):
        tb = s.shapes.add_textbox(lx + Emu(int(0.55 * 914400)), ly + Emu(int((0.07 + i * 0.25) * 914400)), Emu(int(1.5 * 914400)), Emu(int(0.25 * 914400)))
        r = tb.text_frame.paragraphs[0].add_run(); r.text = txt; r.font.size = Pt(9); r.font.color.rgb = NEGRO

    at = s.shapes.add_textbox(sw - Emu(int(3.2 * 914400)), sh - Emu(int(0.28 * 914400)), Emu(int(3.1 * 914400)), Emu(int(0.25 * 914400)))
    p = at.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
    r = p.add_run(); r.text = "Imagen: Esri World Imagery Wayback (31 ago 2022) · Calles: © OpenStreetMap"
    r.font.size = Pt(6); r.font.color.rgb = BLANCO

    prs.save(salida)
    print(salida, len(s.shapes))


if __name__ == "__main__":
    main(*sys.argv[1:5])
