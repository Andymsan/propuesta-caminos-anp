# Metodología

## 1. Cómo se hacen estos procesos

### 1.1 Marco legal en México

| Instrumento | Qué pide para caminos | Implicación aquí |
|---|---|---|
| **LGEEPA art. 28** y **Reglamento en materia de EIA art. 5** | Las obras en ANP y las vías de comunicación requieren autorización de impacto ambiental (MIA) de SEMARNAT | Un camino nuevo o la ampliación de uno dentro del ANP necesitará MIA. Rehabilitar senderos sobre bordos existentes puede requerir solo un informe preventivo o una consulta de exención. Confirmar con DGIRA |
| **Decreto y Programa de Manejo del APFF** (LGEEPA arts. 47 bis y 66; Reglamento de ANP) | La zonificación (núcleo / amortiguamiento) y sus subzonas (uso público, aprovechamiento sustentable, recuperación) definen dónde se permiten caminos y de qué tipo | Esta propuesta debe entrar al **estudio previo justificativo (ETJ)** y después al programa de manejo como subzona de uso público con reglas de circulación |
| **POET de Tula** (en consulta desde el 11 nov 2026; cierra el 14 dic) | Los lineamientos por UGA determinan usos condicionados | Pedir que las UGAs colindantes (668, 681, 752) incluyan "caminos de acceso de bajo impacto" como uso condicionado y prohíban la apertura de vialidades para fraccionamiento |
| **Ley de Aguas Nacionales art. 3** (ribera o zona federal) | Faja de 10 m desde el NAMO en cauces y vasos (5 m si el cauce mide menos de 5 m de ancho). Las obras en zona federal requieren permiso de Conagua | Los senderos sobre bordos y los cruces de canales del DR003 necesitan permiso de Conagua y del módulo de riego |
| **Decreto del Distrito de Riego 003 Tula** | Canales y drenes, con su zona federal y bordos de operación, son infraestructura federal concesionada al módulo | Los bordos de canales no se usan como caminos vehiculares sin acuerdo con el módulo. Cada cruce necesita una estructura de cruce |
| **INAH** | Cualquier obra cerca de la zona arqueológica o de vestigios requiere su visto bueno | Aplica al sendero de la barranca PN Tula–Tres Culturas |
| **Ley Agraria** / Procuraduría Agraria | Los caminos en tierra ejidal requieren acuerdo de asamblea | Los caminos de saca (tipo B) se acuerdan con cada ejido: Bojay, Huerto Nantza, Xiteje, etc. |

### 1.2 Pasos típicos de un plan de accesos en ANP

1. **Inventario de la red existente**: caminos, brechas, bordos y veredas, con superficie, ancho y uso. Fuentes: INEGI, OSM, ortofoto y recorrido.
2. **Inventario de restricciones**: zonas núcleo, zona inundable, hábitat sensible, sitios arqueológicos, canales y drenes con su zona federal, tenencia de la tierra.
3. **Demanda**: quién necesita llegar a dónde. Visitantes (tren, centro de Tula, zona arqueológica), ejidatarios (parcelas, ganado), servicios (mantenimiento de bordos, colectores, emergencias).
4. **Jerarquía de caminos por tipo de usuario**: peatonal / ciclista, de servicio restringido, vehicular de borde. Esta jerarquía es la principal herramienta contra la urbanización inducida.
5. **Trazo de rutas** que reutilicen lo existente y minimicen impactos (análisis de menor costo o multicriterio).
6. **Gestión de acceso**: puntos de control, horarios, plumas, bolardos, estacionamientos fuera del área.
7. **Diseño de bajo impacto**: drenaje transversal, alcantarillas dimensionadas, vados, superficie permeable.
8. **Consulta y acuerdos**: ejidos, módulo de riego, Conagua, INAH, Conanp.
9. **Monitoreo**: conteo de visitantes, nuevas construcciones a menos de 200 m de los caminos (imagen satelital anual).

### 1.3 Lo que dice la evidencia sobre caminos y urbanización

- El **acceso que abre un camino** es el principal mecanismo por el que aumentan la superficie construida, la urbanización y la expansión agrícola. Así lo concluye una revisión de 137 estudios en África subsahariana (IIASA, 2021).
- Los asentamientos al borde de un camino y los caminos secundarios que salen de él crecen hasta formar **zonas urbanizadas**. Los caminos de obra abren hábitat intacto (PIARC, 2011).
- Los caminos en ANP aumentan el número de visitantes. Su planeación debe ponderar manejo, técnica, economía, ecología y paisaje (Croatian Journal of Forest Engineering, 2022).
- Para caminos rurales de bajo volumen, la guía *Low-Volume Roads Engineering BMP Field Guide* (Keller y Sherar, USAID / USFS, 2003) establece el drenaje transversal, el diseño de alcantarillas (cap. 8), los vados (cap. 9) y los puentes (cap. 10) como las prácticas que más reducen el impacto hídrico.

Conclusión operativa: **lo que induce urbanización es el acceso vehicular mejorado a suelo no urbano**, no el sendero peatonal. Por eso el modelo mide el riesgo solo en tramos vehiculares dentro del ANP fuera de zona urbana.

## 2. Cómo se modeló aquí

### 2.1 Red

- **Caminos**: OpenStreetMap, todas las clases `highway`. La conectividad sale de los vértices compartidos, así que los puentes y pasos a desnivel no crean cruces falsos.
- **Bordos**: ejes de los bordos de Tres Culturas (`bordos-tres-culturas/datos/bordos.gpkg`) y el perímetro de la laguna de Bojay (bordo perimetral en rehabilitación). Se unen a la red donde quedan a menos de 40 m de un camino.
- **Conectores candidatos**: senderos nuevos de hasta 250 m desde puntas muertas de brechas y veredas, solo donde la red no ofrece ya un recorrido corto.

### 2.2 Atributos por tramo

| Atributo | Cálculo |
|---|---|
| `en_anp` | Punto medio dentro del polígono del ANP |
| `en_zona_inundable` | Punto medio dentro de la zona inundable de Tres Culturas |
| `urbano` | ≥ 6 edificaciones (Open Buildings) a menos de 75 m |
| `cruces_agua` | Intersecciones con canales (DR003, INEGI 1:50k) y corrientes (INEGI) |
| `junto_parcela` | A menos de 15 m de una parcela RAN o de zona federal |

### 2.3 Costos

**Modo activo** (a pie y en bici), costo por metro: bordo 0.8, vereda o brecha 0.9, calle local 1.0, terciaria 1.3, secundaria 1.8, primaria 2.5, conector nuevo 2.0, más 300 m equivalentes por cada canal o corriente que cruce un conector nuevo. Las autopistas no están permitidas.

**Modo vehicular**: solo caminos existentes. Terracería ×2, **×6 dentro del ANP fuera de zona urbana**, prohibido en la zona inundable. Se elige el **estacionamiento de borde** P que minimiza `costo_auto(O→P) + 2 × costo_caminata(P→D)`, con P en un nodo urbano o fuera del ANP y a no más de 1.5 km a pie.

### 2.4 Indicadores por ruta

`km_total`, `km_existente`, `km_sobre_bordo`, `km_nuevo`, `km_en_anp`, `km_zona_inundable`, `km_anp_no_urbano`, `km_riesgo_urbanizacion` (solo vehicular), `cruces_canal_o_corriente` (cruces distintos, agrupados a 25 m), `km_junto_parcelas`.

### 2.5 Supuestos para revisar

- Los pesos son de criterio experto. Conviene calibrarlos en un taller con Conanp y los ejidos.
- La capa "urbano" usa edificaciones, no el uso de suelo del POET.
- El inventario de canales no incluye drenes. Los cruces reales serán más que los calculados.

## Fuentes

- [LGEEPA, Cámara de Diputados](https://www.diputados.gob.mx/LeyesBiblio/pdf/LGEEPA.pdf)
- [Reglamento de la LGEEPA en materia de EIA, art. 5](https://mley.mx/Reg_LGEEPA_MEIA/articulo/5o/)
- [Reglamento de la LGEEPA en materia de ANP](https://mley.mx/Reg_LGEEPA_ANP/index.html.md)
- [Curso MIA: regulación ambiental (SEMARNAT)](https://www.gob.mx/cms/uploads/attachment/file/863056/2-_Curso_MIA-Regulaci_n_ambiental.pdf)
- [Ley de Aguas Nacionales, art. 3](https://mley.mx/LAN/articulo/3/) · [Reglamento LAN, art. 4](https://mley.mx/Reg_LAN/articulo/4o/)
- [Distritos de riego: infraestructura y funcionamiento (agua.org.mx)](https://agua.org.mx/wp-content/uploads/2011/06/distritosderiegoinfraestructurayfuncionamiento.pdf)
- [Anexos técnicos de conservación de distritos de riego, Conagua 2014](https://agua.org.mx/wp-content/uploads/2015/06/Anexos_tecnico_generales_conservacion_distritos_de_riego_dic2014.pdf)
- [IIASA (2021): impactos de caminos en ecosistemas de África subsahariana](https://iiasa.ac.at/web/home/about/211019-road-impacts-in-sub-saharan-africa.html)
- [PIARC (2011), congreso de México: caminos y áreas protegidas](https://proceedings-mexico2011.piarc.org/ressources/files/4/0724-en.pdf)
- [Essential issues related to construction phases of road networks in protected areas (CROJFE, 2022)](https://crojfe.com/archive/volume-43-no.1/essential-issues-related-to-construction-phases-of-road-networks-in-protected-areas-a-review/)
- [Keller y Sherar (2003), Low-Volume Roads Engineering BMP Field Guide](https://vtechworks.lib.vt.edu/handle/10919/68420) · [USFS Low Volume Roads](https://www.fs.usda.gov/t-d/programs/forest_mgmt/projects/lowvolroads)

Documentos internos usados: *Reporte de recorrido Tres Culturas–Bojay* (18 nov 2025), *Hoja de ruta ANP Tula*, *Notas de reuniones Tres Culturas*, *Propuesta de Parque Inundable Tres Culturas* (3 nov 2026), *Tres Culturas – Proyecto conceptual*.
