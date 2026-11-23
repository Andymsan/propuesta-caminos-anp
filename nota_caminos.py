"""Genera la nota conceptual de caminos (Word) con mapa y fotos numeradas.

Uso: python nota_caminos.py resultados/mapa_caminos_ejido.png datos/fotos_puntos.csv <carpeta_fotos> documentos/nota_caminos.docx
"""
import io
import sys

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

FUENTE = "Arial"


def sombrear(celda, color):
    tc = celda._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), color)
    tc.append(s)


def parrafo(doc, texto="", negrita=None, tam=10.5, alin=None, despues=6):
    p = doc.add_paragraph()
    for i, trozo in enumerate(texto.split("**")):
        r = p.add_run(trozo)
        r.bold = (i % 2 == 1) if negrita is None else negrita
        r.font.size = Pt(tam)
    p.paragraph_format.space_after = Pt(despues)
    if alin:
        p.alignment = alin
    return p


def vinetas(celda, items):
    celda.text = ""
    for i, t in enumerate(items):
        p = celda.paragraphs[0] if i == 0 else celda.add_paragraph()
        p.add_run("- " + t).font.size = Pt(9)
        p.paragraph_format.space_after = Pt(1)


def foto_reducida(ruta, ancho=1100):
    im = Image.open(ruta).convert("RGB")
    im.thumbnail((ancho, ancho))
    b = io.BytesIO(); im.save(b, "JPEG", quality=82); b.seek(0)
    return b


def main(mapa, fotos_csv, carpeta_fotos, salida):
    doc = Document()
    st = doc.styles["Normal"]; st.font.name = FUENTE; st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FUENTE)
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.2); s.top_margin = s.bottom_margin = Cm(1.6)

    t = doc.add_paragraph()
    r = t.add_run("Caminos de acceso a Tres Culturas y San Francisco Bojay\n"); r.bold = True; r.font.size = Pt(15)
    r = t.add_run("Nota conceptual"); r.bold = True; r.font.size = Pt(15)

    parrafo(doc, "El ejido de San Francisco Bojay identificó los caminos que requiere para mejorar el acceso a sus "
                 "parcelas, a la laguna de Bojay y a la zona de Tres Culturas. Las solicitudes son congruentes con el "
                 "proyecto de Saneamiento y Restauración del Río Tula y con la propuesta de Área Natural Protegida, ya que "
                 "**aprovechan caminos y bordos existentes**, **apoyan las actividades agrícolas** del ejido y "
                 "**no abren nuevas vialidades urbanas**.")
    parrafo(doc, "Las solicitudes del ejido se agrupan en cinco acciones:")

    tabla = doc.add_table(rows=1, cols=3)
    tabla.style = "Table Grid"; tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in zip(tabla.rows[0].cells, ("Solicitud", "Descripción", "Acciones necesarias")):
        c.text = ""; rr = c.paragraphs[0].add_run(h); rr.bold = True; rr.font.size = Pt(10)
        sombrear(c, "D9E7D6")
    filas = [
        ("Andador peatonal\n4.7 km",
         "Recorrido peatonal y ciclista sobre el bordo de Tres Culturas y la margen de la laguna de Bojay. Conecta la "
         "ciudad de Tula con Bojay pasando bajo el Arco Norte.",
         ["Conformado y compactado de la corona del bordo con material permeable",
          "Reforestación con especies nativas a lo largo del andador",
          "Señalética y bolardos en los accesos para evitar el paso de vehículos"]),
        ("Rehabilitación de caminos\n3.0 km",
         "Camino existente entre la última sección pavimentada del lado de Tula y el fin del pavimento en la colonia "
         "de San Francisco Bojay (fotos 1 a 8). Pasa bajo el viaducto del tren México–Querétaro y el Arco Norte, y da "
         "servicio a las parcelas del ejido.",
         ["Nivelación y revestimiento de terracería",
          "Cunetas y obras de drenaje para evitar encharcamientos",
          "Reencauzar el dren que se desvía hacia el camino y atender el drenaje de la colonia (fotos 6 y 7)",
          "Sin pavimento asfáltico en el tramo dentro del polígono del ANP (0.5 km)"]),
        ("Camino a parcelas\n1.4 km",
         "Camino paralelo al Arco Norte, del camino rehabilitado a la entrada de las parcelas (fotos 4 y 5). Dos "
         "terceras partes ya existen como brecha.",
         ["Conformado de terracería de máximo 4 m de ancho",
          "Alcantarilla o puente en el cruce con el canal del Distrito de Riego 003",
          "Sin introducción de servicios (luz, agua, drenaje)"]),
        ("Acceso vehicular al bordo\n0.5 km",
         "Camino junto al Arco Norte, del paso bajo el puente (foto 3) al bordo del río, para que los ejidatarios "
         "lleguen con maquinaria, cosecha y ganado a sus parcelas.",
         ["Camino de terracería de máximo 4 m de ancho",
          "Acceso controlado por el ejido (pluma o candado)",
          "Sin introducción de servicios (luz, agua, drenaje)"]),
        ("Bache\nColonia San Francisco Bojay",
         "Hundimiento en la calle de acceso a la laguna, en la zona urbana de la colonia.",
         ["Reparación puntual de la carpeta (foto 9)"]),
    ]
    for sol, desc, acc in filas:
        c = tabla.add_row().cells
        c[0].text = ""; rr = c[0].paragraphs[0].add_run(sol); rr.bold = True; rr.font.size = Pt(9)
        c[1].text = ""; c[1].paragraphs[0].add_run(desc).font.size = Pt(9)
        vinetas(c[2], acc)
    for row in tabla.rows:
        for w, c in zip((Cm(3.6), Cm(6.4), Cm(6.6)), row.cells):
            c.width = w
    parrafo(doc, "", despues=4)

    parrafo(doc, "**Consideraciones**", despues=3)
    for txt in (
        "**No incentivar la urbanización.** Los caminos dentro de la zona de conservación se mantienen de terracería, "
        "con acceso controlado y sin servicios, para que mejoren el acceso a las parcelas sin generar presión para "
        "lotificar.",
        "**Respeto a canales y drenes agrícolas.** El camino a parcelas cruza un canal del Distrito de Riego 003; el "
        "andador, el acceso vehicular y el camino rehabilitado corren a menos de 30 m de canales secundarios. Las obras "
        "no deben ocupar su zona federal ni reducir su sección, y se coordinarán con el módulo de riego.",
        "**Zona inundable.** Cerca de 1.9 km del andador están en la zona inundable de Tres Culturas, por lo que podrá "
        "cerrarse temporalmente en avenidas extraordinarias.",
        "**Permisos.** Las obras sobre bordos y zona federal requieren permiso de Conagua.",
    ):
        p = parrafo(doc, txt, tam=10, despues=3)
        p.paragraph_format.left_indent = Cm(0.5)

    doc.add_page_break()
    parrafo(doc, "**Ubicación de las solicitudes**", tam=12, despues=4)
    m = Image.open(mapa)
    doc.add_picture(foto_reducida(mapa, 2200), width=Cm(16.5) if m.width / m.height > 0.75 else None,
                    height=None if m.width / m.height > 0.75 else Cm(21.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    parrafo(doc, "**Fotografías de los puntos clave**", tam=12, despues=4).paragraph_format.page_break_before = True
    fotos = pd.read_csv(fotos_csv)
    grid = doc.add_table(rows=(len(fotos) + 2) // 3, cols=3)
    grid.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, r in enumerate(fotos.itertuples()):
        c = grid.rows[i // 3].cells[i % 3]
        c.text = ""
        c.paragraphs[0].add_run().add_picture(foto_reducida(f"{carpeta_fotos}/{r.foto}"), width=Cm(5.3))
        cap = c.add_paragraph()
        rr = cap.add_run(f"{r.num}. "); rr.bold = True; rr.font.size = Pt(9)
        rr = cap.add_run(r.descripcion); rr.font.size = Pt(9)
        cap.paragraph_format.space_after = Pt(4)
    doc.save(salida)
    print(salida)


if __name__ == "__main__":
    main(*sys.argv[1:5])
