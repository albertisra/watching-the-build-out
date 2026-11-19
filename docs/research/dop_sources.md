# Open state orthophotos (DOP) in Germany: survey of all 16 federal states
Status: draft   Retrieved: 2026-11-18   Author: orthophoto-engineer

Scope: which state survey offices publish 20 cm (or finer) DOP as open data, under which licence, how the flight date of a location can be read, and how to access the imagery. Nothing from the fee-based BKG national mosaic or from commercial basemaps was used.

Evidence rules. VERIFIED means read on the office's own service (the WMS GetCapabilities document, saved in `data/raw/dop/caps/<state>.xml`, or a live GetFeatureInfo/GetMap call on 2026-11-18) or on the office's own web page. SECONDARY means a third-party or portal page that is not the office's own service. UNVERIFIED means not confirmed. "Capabilities" below always means the service's own GetCapabilities. Where a number came from a call, the call is described so it can be repeated. Page text was read through a script that strips HTML; exact wording is quoted in German.

Method note on the flight date. A WMS GetFeatureInfo call on the state's info layer at the centre of a 101 m window returns the metadata of the DOP block under that point. The date is therefore per block, not per pixel, and a 640 m chip can straddle two blocks. Our code records the date at the chip centre only.

## Key facts per state

### Bayern (BY)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für Digitalisierung, Breitband und Vermessung (LDBV), Bayerische Vermessungsverwaltung | WMS capabilities `by_dop20.xml` (ContactOrganization) | VERIFIED |
| Open | yes. Fees: "kostenfrei". AccessConstraints: "CC BY 4.0 vgl. https://creativecommons.org/licenses/by/4.0/deed.de" | capabilities; OpenData terms page https://www.geodaten.bayern.de/odd/m/3/html/nutzungsbedingungen.html | VERIFIED |
| Licence wording | "Die kostenfreien Geodatensätze und -dienste der Bayerischen Vermessungsverwaltung stehen unter nachfolgender Lizenz zur Verfügung: Creative Commons Namensnennung 4.0 International (CC BY 4.0)". Attribution: "angemessene Urheber- und Rechteangaben machen, einen Link zur Lizenz beifügen und angeben, ob Änderungen vorgenommen wurden". The page prescribes no fixed attribution string; ours is "© Bayerische Vermessungsverwaltung (LDBV), CC BY 4.0, modified" | terms page | VERIFIED (string is our choice) |
| Products | DOP20 (RGB, grey, CIR) and DOP40 (RGB, grey) as separate WMS; DOP20, DOP40-RGB and DOP20-CIR free via OpenData | capabilities `by_dop20.xml`, `by_dop40.xml`; https://www.ldbv.bayern.de/produkte/luftbilder/orthophotos.html | VERIFIED |
| Resolution | 20 cm (DOP20), 40 cm (DOP40) | capabilities abstracts | VERIFIED |
| Flight cycle | "ab 2017 jährlich die Hälfte der bayerischen Landesfläche beflogen" (two-year cycle); until 2016 three-year cycle | capabilities `by_dop20.xml`, `by_hist.xml` | VERIFIED |
| Flight date per location | GetFeatureInfo on layer `by_dop20_info` ("Angabe des Aufnahmetages des zugrunde liegenden Luftbildes (Befliegungsdatum)"). Call for a site near Munich returned `ua = '24.08.2024'`, `nummer = '124028'`, feature box 664000,5322000 to 704000,5348000 (EPSG:25832), i.e. blocks of about 40 x 26 km. Formats text/plain, GML, HTML | capabilities; live call 2026-11-18 | VERIFIED |
| Historical DOP | yes, open: WMS "WMS BY DOP historisch": "farbige historische Digitale Orthophotos (DOP), die im Rahmen der Bayernbefliegung seit 2003 erstellt wurden. Für die Jahre 2003 bis 2005 ... 40 cm, ab 2006 ... 20 cm". One layer per year `by_dop_<yyyy>_h` for 2003 to 2025 (all 23 layer names found) with an info layer `by_dop_<yyyy>_h_info`. Same CC BY 4.0 | capabilities `by_hist.xml` | VERIFIED (info-layer content per year not tested) |
| Access | WMS 1.3.0 (also 1.1.1), CRS EPSG:25832, 25833, 31468, 4258, 4326, 3857, 5678. Endpoints: `https://geoservices.bayern.de/od/wms/dop/v1/dop20`, `.../dop/v1/dop40`, `https://geoservices.bayern.de/od/wms/histdop/v1/histdop`. Formats image/jpeg, png, tiff. Bulk download of DOP tiles through the OpenData portal (https://geodaten.bayern.de/opengeodata/); the page text read did not show the tile size | capabilities; OpenData FAQ | VERIFIED (WMS), SECONDARY (download details) |
| Request limits | "Der WMS ist auf eine maximale Ausdehnung von 6.000 x 6.000 Pixel begrenzt" (MaxWidth 6500 in the XML). No rate limit documented in capabilities or terms | capabilities | VERIFIED (no rate limit found) |

### Baden-Württemberg (BW)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für Geoinformation und Landentwicklung Baden-Württemberg (LGL-BW) | capabilities `bw.xml` | VERIFIED |
| Open | yes. Fees: "Unentgeltliche Nutzung nach Open Data Lizenz". LGL product page: "DOP20 sind in der Regel Open Data" | capabilities; https://www.lgl-bw.de/Produkte/Luftbildprodukte/DOP20/ | VERIFIED |
| Licence wording | "Es gelten die Lizenzbedingungen „Datenlizenz Deutschland - Namensnennung - Version 2.0“ bzw. „dl-de/by-2-0” ( https://www.govdata.de/dl-de/by-2-0 ) mit den dort geforderten Angaben zum Quellenvermerk. Als Rechteinhaber und Bereitsteller ist die Datenhaltende Stelle, sowie das Jahr des Datenbezugs in Klammern anzugeben. Beispiel für Quellenvermerk: LGL-BW (2024) Datenlizenz Deutschland - Namensnennung - Version 2.0, www.lgl-bw.de" | capabilities | VERIFIED |
| Resolution | 20 cm (DOP20); DOP10 also exists; DOP40/80 by order | capabilities; LGL page | VERIFIED |
| Flight cycle | "Ab 2021/2022 im 2-Jahres-Turnus. ... Sommerbefliegung mit Belaubung bis 2025. Ab 2026 eine Befliegung für DOP20 und DOP10. DOP seit 2020 als TrueDOP." Capabilities abstract: "Jährliche Aktualisierung von ca. 50 % der Landesfläche" (a second layer abstract says 30 %) | LGL page; capabilities | VERIFIED (the 30 / 50 % wording is inconsistent in the service) |
| Flight date per location | NOT OBTAINABLE by machine. Both WMS layers have `queryable="0"`. The LGL page links only a "Befliegungsübersichten" map in the Geoportal BW viewer (https://www.geoportal-bw.de, permalink on the DOP20 page), no tile index file or service found (checked 2026-11-18) | capabilities; LGL page | NOT OBTAINABLE |
| Historical DOP | LGL: "Historische Luftbilder als Geodatendienste sind in der Regel Open Data"; analog aerial photos from 1968 flächendeckend (five-year cycle 1968 to 2008), orthophotos partly on request. Whether georeferenced historical DOP exist as a service and from which year was not confirmed | https://www.lgl-bw.de/Produkte/Luftbildprodukte/Historische-Luftbilder/ | UNVERIFIED (service) |
| Access | WMS 1.3.0 `https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ATKIS_DOP_20_C`, layer `IMAGES_DOP_20_RGB`, CRS incl. EPSG:25832. Download via Open GeoData portal https://opengeodata.lgl-bw.de (product dop20, from the LGL page link) | capabilities; LGL page | VERIFIED (WMS) |
| Request limits | MaxWidth/MaxHeight 15000; no rate limit documented | capabilities | VERIFIED |

### Berlin (BE)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin (Geoportal Berlin / FIS-Broker) | capabilities `be4.xml` | VERIFIED |
| Open, licence | "Für die Nutzung der Daten ist die Datenlizenz Deutschland - Zero - Version 2.0 anzuwenden." No access restriction ("Es gelten keine Zugriffsbeschränkungen"). No attribution required | capabilities | VERIFIED |
| Resolution, cycle | 0.20 m TrueDOP, tiles 2 km x 2 km, position accuracy +/- 0.4 m; the service `truedop_2024` is the 2024 edition. Older editions and the cycle were not read | capabilities | VERIFIED (2024); cycle UNVERIFIED |
| Flight date | Not in the service: layer `truedop_2024` is not queryable; the queryable tile layer `blattschnitt` returns tile id and a download URL only. Year 2024 is in the service name | live call 2026-11-18 | VERIFIED (no day) |
| Historical | not checked | | UNVERIFIED |
| Access | WMS `https://gdi.berlin.de/services/wms/truedop_2024`, CRS EPSG:25833 and 25832; tile download (ATOM) `https://fbinter.stadt-berlin.de/fb/atom/DOP/dop20true_rgbi_2024/bilder/dop20rgbi_33_<x>_<y>_2_be_2024.jp2` (URL pattern returned by the service) | live call | VERIFIED |
| Limits | none stated | capabilities | VERIFIED (none found) |
| Note | Berlin is also covered by the Brandenburg service (BB-BE) | `bb2.xml` | VERIFIED |

### Brandenburg (BB)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesvermessung und Geobasisinformation Brandenburg (LGB) | capabilities `bb2.xml` | VERIFIED |
| Open, licence | "Die Daten können gemäß der „Datenlizenz Deutschland - Namensnennung - Version 2.0“ (https://www.govdata.de/dl-de/by-2-0) genutzt werden. Namensnennung: "GeoBasis-DE/LGB", Beispiel: „© GeoBasis-DE/LGB, dl-de/by-2-0, (Daten geändert)“". If Berlin data are used: add "© Geoportal Berlin, dl-de/by-2-0" | capabilities | VERIFIED |
| Resolution | 20 cm, colour, Brandenburg with Berlin | capabilities | VERIFIED |
| Flight cycle | "alle 3 Jahre (bis 2025), alle zwei Jahre seit 2026"; TrueDOP 20 cm since November 2020, DOP10 TrueDOP since 2022 | https://geobasis-bb.de/lgb/de/geodaten/luftbilder/luftbilder-aktuell/ | VERIFIED |
| Flight date | Service contains an info layer `bb_dop_info` ("DOP - Aktualitätsübersicht"), but GetFeatureInfo returned HTTP 500 on 2026-11-18 (text/plain and text/html). Retried 2026-11-18, still HTTP 500. The office points to its Aktualitätenviewer (https://viewer.brandenburg.de/aktualitaeten/, web app) for dates; no machine-readable index found | live call; LGB page | NOT OBTAINABLE |
| Historical | LGB offers "Luftbilder historisch" incl. DOP of several years; delivered through the customer service with costs, open-data status not stated | https://geobasis-bb.de/lgb/de/geodaten/luftbilder/luftbilder-historisch/ | NOT OPEN (as far as stated) |
| Access | WMS (cached, MapProxy) `https://isk.geobasis-bb.de/mapproxy/dop20c/service/wms`, layers `bebb_dop20c`, `bb_dop_info`; EPSG:25832 and 25833. A cached tile service can limit arbitrary bboxes; a 640 m GetMap worked | capabilities; live GetMap | VERIFIED |
| Limits | MaxWidth/MaxHeight 8000 | capabilities | VERIFIED |

### Bremen (HB)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt GeoInformation Bremen | capabilities `hb.xml` | VERIFIED |
| Licence | "Creative Commons Namensnennung (CC-BY), Quellenvermerk: Landesamt GeoInformation Bremen" (CC version not stated) | capabilities | VERIFIED |
| Resolution, year | DOP20 flight 2023 (service title "DOP20 2023 Land Bremen"); day not exposed | capabilities | VERIFIED |
| Access | WMS `https://geodienste.bremen.de/wms_dop20_2023`, layers `DOP20_2023_HB`, `DOP20_2023_BHV`, EPSG:25832 and 25833, MaxWidth 14276. Older years not checked | capabilities | VERIFIED |

### Hamburg (HH)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesbetrieb Geoinformation und Vermessung (LGV) Hamburg | WMS capabilities `hh.xml` (ContactOrganization "LGV Hamburg") | VERIFIED |
| Open, licence | Transparenzportal CKAN API (`https://suche.transparenz.hamburg.de/api/3/action/package_search`) lists the DOP datasets with `license_id = dl-de-by-2.0`. The WMS Fees field reads: "Datenlizenz Deutschland Namensnennung 2.0, Quellenvermerk: Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung (LGV), Andere geschlossene Lizenz, Quellenvermerk: Maxar Products. Dynamic Product © 2023 Maxar Technologies." So some years in the service are closed-licence satellite imagery | capabilities; CKAN API | VERIFIED |
| Resolution | 0.20 to 0.30 m (unbelaubt), 0.20 to 0.50 m (belaubt) per dataset descriptions; "2022 image from satellite" | CKAN API | VERIFIED |
| Flight date | WMS time dimension in years, `2001/2026/P1Y`, default 2026; one layer `dop_zeitreihe_unbelaubt`. No day. Which years are aerial and which Maxar is not stated in the capabilities | capabilities | VERIFIED (year only; aerial/satellite split NOT OBTAINABLE here) |
| Access | WMS `https://geodienste.hamburg.de/wms_dop_zeitreihe_unbelaubt` (EPSG:25832, 25833, MaxWidth 4096), `.../wms_dop_zeitreihe_belaubt` (name from the catalogue snapshot). The catalogue's other endpoints `HH_WMS_DOP` and `HH_WMS_Cache_DOP20` return HTTP 404 (2026-11-18) | live calls | VERIFIED |
| Use | NOT coded: the service mixes licence-clean aerial years with closed Maxar years and exposes no way to tell them apart; no pilot site; two negatives get no chip | | NOT OBTAINABLE (aerial vs satellite split) |

### Hessen (HE)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Hessische Verwaltung für Bodenmanagement und Geoinformation (HVBG), service operator Hessisches Landesamt für Bodenmanagement und Geoinformation | WMS capabilities `he2.xml`; https://hvbg.hessen.de/geoinformation/open-data and https://hvbg.hessen.de/node/2167 (service list) | VERIFIED |
| Open, licence | WMS Fees: "Der automatisierte Abruf und die Nutzung der Geobasisdaten und der zugehörigen Metadaten sind kostenfrei. (§ 24 HVGG)". AccessConstraints: "Jede Nutzung der Geobasisdaten und zugehörigen Metadaten ist ohne Einschränkung oder Bedingung erlaubt ... kommerzielle und nicht kommerzielle Nutzung ..." Attribution optional; if given it must state changes ("§ 18 HVGG"). No named licence (statutory open data). Our credit: "Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation (modified)" | capabilities | VERIFIED |
| Resolution, product | DOP20 (TrueDOP, RGB and CIR); also scale series | capabilities; service list page | VERIFIED |
| Flight date | GetFeatureInfo on layer `he_dop_rgb_info` returns `flugjahr`, `bildflug = 'dd-mm-yyyy'` (example 14-06-2025), tile `name`, `aenderung` | live call 2026-11-18 | VERIFIED |
| Cycle | not stated | | NOT OBTAINABLE (not on the pages read) |
| Historical | WMS `https://www.gds-srv.hessen.de/cgi-bin/hdop/he-hdop.ows` "Historische Digitale Orthofotos" 1952-67 (layers `hdop040`, `hdop320`, info layer `he_hdop_info`); a WMTS exists at `https://www.gds-srv.hessen.de/wmts-dop/wmts/1.0.0/WMTSCapabilities.xml`; years between 1967 and today not read | capabilities | VERIFIED (1952-67), UNVERIFIED (later) |
| Access | WMS 1.3.0 `https://www.gds-srv.hessen.de/cgi-bin/lika-services/ogc-free-images.ows`, layers `he_dop20_rgb`, `he_dop20_cir`, EPSG:25832, 25833; WCS listed by HVBG (URL not found) | capabilities | VERIFIED (WMS) |
| Limits | MaxWidth/MaxHeight 3000, so a 640 m chip is requested at 0.25 m (2560 px) | capabilities | VERIFIED |

### Mecklenburg-Vorpommern (MV)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für innere Verwaltung M-V, Amt für Geoinformation, Vermessung und Katasterwesen | capabilities `mv.xml` | VERIFIED |
| Open, licence | NOT open data (corrected 2026-11-18). The WMS Fees field says "Es gelten keine Bedingungen", but the CSW record of the service (`https://www.geodaten-mv.de/soapServices/api?...GetRecordById&id=bcfae1e9-1e22-47dd-92ea-1901308b9b74`) states: "Öffentlicher Zugriff beschränkt entsprechend Artikel 13(1)(e) der INSPIRE-Richtlinie ... Für die Nutzung können Kosten anfallen. Der Dienst darf genehmigungs- und geldleistungsfrei mit eigenen Diensten und Daten ... in interne Geschäftsprozesse, Produkte und Anwendungen eingebunden werden. Jede darüberhinausgehende externe Nutzung des Dienstes ... ist genehmigungs- und ggf. geldleistungspflichtig. Es gelten die AGNB des AfGVK". Internal analysis is allowed; publishing chips or derived outlines is external use and needs permission (geodatenservice@laiv-mv.de). Attribution wording when used:  "Der Lizenznehmer ist verpflichtet, bei jeder öffentlichen Wiedergabe, Verbreitung oder Präsentation der Geodaten sowie bei jeder Veröffentlichung oder externen Nutzung einer Bearbeitung oder Umgestaltung einen deutlich sichtbaren Quellenvermerk anzubringen, der wie folgt auszugestalten ist: © GeoBasis-DE/M-V <Jahr der letzten Datenlieferung>". No named open licence | capabilities; CSW record | VERIFIED (restricted) |
| Resolution | DOP10, DOP20, DOP40 exist; this service shows 0.2 m | capabilities | VERIFIED |
| Flight cycle | "Die Aktualität für die Landesfläche liegt bei ca. drei Jahren"; CIR since flight year 2004; leaf-on and leaf-off flights since 2013 | capabilities | VERIFIED |
| Flight date | GetFeatureInfo on `mv_dop_info` returns the fields `Befliegungsjahr`, `Befliegungszeitraum` and `Nummer` (flight year, flight day, flight batch) for a location, plus a CSW record link (values not reproduced: use restriction) | live call 2026-11-18 | VERIFIED |
| Historical | The abstract says DOP exist from the early digital years (CIR from 2004); no historical service found | capabilities | UNVERIFIED |
| Access | WMS `https://www.geodaten-mv.de/dienste/adv_dop`, layers `mv_dop`, `mv_dop_info`, EPSG:25833 and 25832 | capabilities | VERIFIED |
| Limits | MaxWidth/MaxHeight 4192; none else | capabilities | VERIFIED |

### Niedersachsen (NI)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für Geoinformation und Landentwicklung Niedersachsen (LGLN) | capabilities `ni.xml` | VERIFIED |
| Licence wording | "Es gelten die Lizenzbedingungen "Creative Commons Namensnennung – 4.0 International (CC BY 4.0)" ... Als Rechteinhaber und Bereitsteller ist "LGLN", sowie das Jahr des Datenbezugs in Klammern anzugeben. Beispiel für Quellenvermerk: LGLN (2024) Creative Commons Namensnennung – 4.0 International ..." | capabilities | VERIFIED |
| Resolution, cycle | 20 cm TrueDOP20 RGBI; cycle not read | capabilities; live call | VERIFIED (cycle UNVERIFIED) |
| Flight date | GetFeatureInfo (GML, with `format=image/png` also passed) on `ni_dop20_info` returns `PRODUKT TrueDOP20 RGBI`, `EDITION 2025`, `BF_NAME Meppen`, `BF_DATUM 20250308`, `BF_NUMMER 3802`, `B_AUFL_CM 20`, `STAND 20250807`, tile box 2 km. Without the `format` parameter the service answers "Parameter "format" fehlerhaft" | live call 2026-11-18 | VERIFIED |
| Historical | not checked | | UNVERIFIED |
| Access | WMS `https://opendata.lgln.niedersachsen.de/doorman/noauth/dop_wms`, layers `ni_dop20`, `ni_dop20_info`, EPSG:25832, 25833 | capabilities | VERIFIED |
| Limits | MaxWidth/MaxHeight 15000 | capabilities | VERIFIED |

### Nordrhein-Westfalen (NW)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Geobasis NRW (Bezirksregierung Köln) | capabilities `nw.xml` | VERIFIED |
| Licence wording | "Die Geobasisdaten des amtlichen Vermessungswesens werden ... gebührenfrei nach Open Data-Prinzipien über online-Verfahren bereitgestellt. ... Es gelten die ... einheitlichen Lizenzbedingungen „Datenlizenz Deutschland – Zero“ (https://www.govdata.de/dl-de/zero-2-0). Jede Nutzung ist ohne Einschränkungen oder Bedingungen zulässig." No attribution required | capabilities | VERIFIED |
| Resolution | 10 cm ("Bodenauflösung von 10cm/Pixel"), 4 channels RGBI; true orthophoto since flight 2018 | capabilities | VERIFIED |
| Flight cycle | "werden in einem 2-jährigen Zyklus erneuert" | capabilities | VERIFIED |
| Flight date | GetFeatureInfo on `nw_dop_utm_info` returns `Kachelname`, `Bildflugdatum = '27.02.2026'`, `Bodenauflösung = '0.10'`, `Photometrie = 'RGBI'` for a pilot site (tile 32408_5756). A February date means leaf-off imagery | live call 2026-11-18 | VERIFIED |
| Historical | not checked (the WMS shows the current DOP only) | | UNVERIFIED |
| Access | WMS `https://www.wms.nrw.de/geobasis/wms_nw_dop`, layers `nw_dop_rgb`, `nw_dop_cir`, `nw_dop_nir`, `nw_dop_utm_info`; EPSG:25832. WCS/ATOM not checked | capabilities | VERIFIED (WMS) |
| Limits | MaxWidth/MaxHeight 5000 (640 m at 10 cm needs 6400 px, so we request 20 cm) | capabilities | VERIFIED |

### Rheinland-Pfalz (RP)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Vermessungs- und Katasterverwaltung RLP (LVermGeoRP) | capabilities `rp.xml` | VERIFIED |
| Licence wording | "geldleistungsfrei, Datenlizenz Deutschland – Namensnennung – Version 2.0 ... Die Namensnennung der Vermessungs- und Katasterverwaltung Rheinland-Pfalz als Rechteinhaberin hat in folgender Weise zu erfolgen: ©GeoBasis-DE / LVermGeoRP (Jahr des Datenbezugs), dl-de/by-2-0, http://www.lvermgeo.rlp.de [Daten bearbeitet]" | capabilities | VERIFIED |
| Resolution | 20 cm | capabilities | VERIFIED |
| Flight cycle | not stated | RP CSW record (`metadatenkatalog-vermkv.service24.rlp.de/extern/vertriebsprodukte`) read 2026-11-18 | NOT OBTAINABLE |
| Flight date | The info layer returns `erstellung = '20.06.2025'` ("Erstellung" is the production date of the tile record, not the flight date), `publikation`, tile name `dop20rgbi_32350_5536`, and a CSW link. The CSW record (retrieved with the link properly URL-encoded) confirms the licence "Open-data-Produkt: Datenlizenz Deutschland -Namensnennung- Version 2.0" and lists only publication dates and a bare year "2025", no flight day. Flight date NOT OBTAINABLE | live calls 2026-11-18 | VERIFIED (production date only) |
| Historical | not checked | | UNVERIFIED |
| Access | WMS `https://geo4.service24.rlp.de/wms/rp_dop20.fcgi`, layers `rp_dop20`, `rp_dop20_info`, EPSG:25832 (25831, 25833) | capabilities | VERIFIED |
| Limits | MaxWidth/MaxHeight 10000 | capabilities | VERIFIED |

### Saarland (SL)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für Vermessung, Geoinformation und Landentwicklung (LVGL) | capabilities `sl.xml` | VERIFIED (office) |
| Open | NOT OBTAINABLE. The LVGL pages return HTTP 403 to our client (https://www.saarland.de/lvgl/DE/portale/geoinformation/Luftbilder, tried 2026-11-18). The only LVGL Geoportal WMS read (a Sentinel-2 layer) says: "Das Betrachten ... ist kostenfrei. Jegliche andere Nutzung, so auch das Einbinden in andere Anwendungen (Download) ist kostenpflichtig und bedarf einer vertraglichen Grundlage." If this applies to DOP, our use is not allowed | capabilities | NOT OBTAINABLE |
Not used. Four negatives get no chip.

### Sachsen (SN)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für Geobasisinformation Sachsen (GeoSN) | capabilities `sn.xml` | VERIFIED |
| Licence wording | "Die Erlaubnis entspricht dem Lizenzmuster der Datenlizenz Deutschland – Namensnennung – Version 2.0 unter Angabe des Quellenvermerks "Landesamt für Geobasisinformation Sachsen (GeoSN)" oder kurz "GeoSN". Der Download und die Nutzung der online bereitgestellten Daten sind ... kostenfrei." Example: "Quelle: GeoSN, dl-de/by-2-0" | https://www.landesvermessung.sachsen.de/allgemeine-nutzungsbedingungen-8954.html (linked from the WMS AccessConstraints page) | VERIFIED |
| Resolution | 0.20 m RGB; digital-camera orthophotos produced "Seit 2005" | capabilities | VERIFIED |
| Flight cycle | annual flights of parts of the state (the portal shows "Bildflug 2025" DOP available and "Bildflug 2026" Quick-DOP) | https://www.geodaten.sachsen.de/ | SECONDARY |
| Flight date | GetFeatureInfo on `sn_dop_020_info` returns "Gebiet: Bautzen", "Datum: 20.03. + 26.03.2024", "ROHDOP: DOP". The date text can hold several days; our code takes the first day and keeps the raw text | live call 2026-11-18 | VERIFIED |
| Historical | not checked | | UNVERIFIED |
| Access | WMS `https://geodienste.sachsen.de/wms_geosn_dop-rgb/guest`, layers `sn_dop_020`, `sn_dop_020_info`, EPSG:25833, 25832; batch download of DOP and Quick-DOP at https://www.geodaten.sachsen.de | capabilities; portal | VERIFIED (WMS) |
| Limits | MaxWidth/MaxHeight 4096 | capabilities | VERIFIED |

### Sachsen-Anhalt (ST)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für Vermessung und Geoinformation Sachsen-Anhalt (LVermGeo) | capabilities `st.xml` | VERIFIED |
| Licence wording | "Für alle ... kostenfrei bereitgestellten Daten (außer Satellitenbilddaten, basemap.de, ...) gelten die Nutzungsbedingungen des LVermGeo, wonach diese unter der Open-Data-Lizenz "Datenlizenz Deutschland – Namensnennung – Version 2.0" genutzt werden dürfen." Fixed attribution string not found; page footers use "© LVermGeo ST", which we adopt with the licence name. DOP10 are excluded ("Aus Datenschutzgründen unterliegen die DOP10 Nutzungsbeschränkungen") | https://www.lvermgeo.sachsen-anhalt.de/de/gdp-open-data.html; /de/gdp-digitale-orthophotos.html | VERIFIED (string is our choice) |
| Resolution | DOP20 (20 cm) and DOP100 open | open-data page; capabilities | VERIFIED |
| Flight cycle | "die Landesfläche alle zwei Jahre beflogen"; true orthophoto since flight 2019 | DOP page | VERIFIED |
| Flight date | not in the WMS. The office publishes a tile index "Aktualität DOP" `https://www.lvermgeo.sachsen-anhalt.de/datei/anzeigen/id/250488,501/dop_aktualitaet.zip` (157,628 bytes; shapefile, EPSG:25832, 5,466 tiles of 2 km, fields NAME, LOSNR, BFLOS, BFDATUM). We cached it once in `data/raw/dop/st_aktualitaet/` and read the date by point in polygon. Field name BFDATUM is read as flight date (name "Bildflug" prefix BF); the file's own metadata sheet (`.shp.xml`) was not read | download 2026-11-18 | VERIFIED (file), SECONDARY (meaning of BFDATUM) |
| Historical | Page links "Luftbildzeitreihen" and "gdp-dop20-auswahl-historie" exist; years not read | open-data page | UNVERIFIED |
| Access | WMS `https://www.geodatenportal.sachsen-anhalt.de/wss/service/ST_LVermGeo_DOP_WMS_OpenData/guest`, layers `lsa_lvermgeo_dop20_2` and `lsa_lvermgeo_dop100_unbesch`, EPSG:25832, 25833; DOP20 tile download page `/de/gdp-dop20-auswahl.html` | capabilities; open-data page | VERIFIED |
| Limits | MaxWidth/MaxHeight 4096 | capabilities | VERIFIED |

### Schleswig-Holstein (SH)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Landesamt für Vermessung und Geoinformation Schleswig-Holstein (LVermGeo SH) | capabilities `sh.xml` | VERIFIED |
| Licence wording | "Für die Nutzung der Daten ist die Creative Commons (CC BY 4.0) – Namensnennung 4.0 International anzuwenden. ... Der Quellenvermerk lautet "© GeoBasis-DE/LVermGeo SH/CC BY 4.0"" | capabilities | VERIFIED |
| Resolution | 20 cm RGB | capabilities | VERIFIED |
| Flight cycle, date, history | The service has one layer `sh_dop20_rgb` and no info layer; the LVermGeo SH site was unreachable from our client on 2026-11-18 (connection refused). NOT OBTAINABLE | capabilities | NOT OBTAINABLE |
| Access | WMS `https://dienste.gdi-sh.de/WMS_SH_DOP20col_OpenGBD`, EPSG:25832, 25833, MaxWidth/MaxHeight 5000 | capabilities | VERIFIED |

### Thüringen (TH)
| Item | Value | Source | Status |
|---|---|---|---|
| Office | Thüringer Ministerium für Digitales und Infrastruktur (service operator, Geoproxy); data holder TLBG | capabilities `th.xml` | VERIFIED (service) |
| Licence wording | "Lizenz: Creative Commons BY 4.0 (https://creativecommons.org/licenses/by/4.0/deed.de) Namensnennung: "© GDI-Th"" | capabilities | VERIFIED |
| Resolution | 20 cm; RGB, panchromatic, CIR; "flächendeckend" | capabilities | VERIFIED |
| Flight date | info layer `th_dop_info` returns `Erstellung = 01.05.2024`, `Publikation = 2024-10`, `Bezug = bDOM`: production dates, not flight dates. The metadata layer `dop20rgbi_utm_metadaten` answers GetFeatureInfo with "Missing WMS:GetFeatureInfo right" (tested 2026-11-18), so flight dates are NOT OBTAINABLE | live call | VERIFIED (production date only) |
| Historical, cycle | not stated in the service | capabilities | NOT OBTAINABLE |
| Access | WMS `https://www.geoproxy.geoportal-th.de/geoproxy/services/DOP20`, layers `th_dop`, `th_dop20pan`, `th_dop20cir`, EPSG:25832, 25833; MaxWidth/MaxHeight 5000 | capabilities | VERIFIED |

## Cross-state notes
- No state documents a request rate limit in its capabilities or terms (only maximum image size). Our own limit is one request per second plus caching, so a pilot run of 50 chips is about 100 requests including date lookups.
- All services were queried with the generic client name `bo-research-client/0.1`.
- All WMS here are 1.3.0 and use easting, northing axis order for EPSG:25832 and 25833.
- Servers return the nominal grid; blocks of different flight years can meet inside a chip. The date is per chip centre.

## Summary table

| State | Office | Open | Licence | Res. | Cycle | Date per location | Historical | Endpoint verified | Used |
|---|---|---|---|---|---|---|---|---|---|
| Bayern | LDBV | yes | CC BY 4.0 | 20 / 40 cm | 2 y (half the state a year) | GetFeatureInfo `ua` (day) | 2003 to 2025, WMS, open | yes | yes |
| Baden-Württemberg | LGL-BW | yes | dl-de/by-2-0 | 20 cm | 2 y from 2021/22 | NOT OBTAINABLE (viewer only) | analog 1968 to 2008; service UNVERIFIED | yes | yes, no date |
| Berlin | SenStadt | yes | dl-de/zero-2-0 | 20 cm | not read | year only (2024) | UNVERIFIED | yes | yes (no pilot site) |
| Brandenburg | LGB | yes | dl-de/by-2-0 | 20 cm | 3 y to 2025, 2 y from 2026 | NOT OBTAINABLE (info layer HTTP 500; viewer only) | not open as stated | yes | yes, no date |
| Bremen | LGB Bremen | yes | CC BY | 20 cm | not read | year only (2023) | UNVERIFIED | yes | yes (no pilot site) |
| Hamburg | LGV | yes (dl-de/by-2.0; some years Maxar, closed) | dl-de/by-2.0 + closed Maxar years | 20 to 50 cm | not read | year only (WMS time) | time series 2001 to 2026 | yes | no (aerial/satellite split unknown) |
| Hessen | HLBG/HVBG | yes | statutory, no conditions (HVGG) | 20 cm | NOT OBTAINABLE | GetFeatureInfo `bildflug` (day) | 1952-67 WMS; later UNVERIFIED | yes | yes |
| Mecklenburg-Vorpommern | LAiV M-V | NO: restricted (INSPIRE 13(1)(e)); internal use only | AGNB AfGVK | 10 / 20 / 40 cm | about 3 y | GetFeatureInfo (day) | UNVERIFIED | yes | chips kept internal; do not publish |
| Niedersachsen | LGLN | yes | CC BY 4.0 | 20 cm | not read | GetFeatureInfo `BF_DATUM` (day) | UNVERIFIED | yes | yes |
| Nordrhein-Westfalen | Geobasis NRW | yes | dl-de/zero-2-0 | 10 cm | 2 y | GetFeatureInfo `Bildflugdatum` (day) | UNVERIFIED | yes | yes |
| Rheinland-Pfalz | LVermGeoRP | yes | dl-de/by-2-0 | 20 cm | NOT OBTAINABLE | NOT OBTAINABLE (production date only) | UNVERIFIED | yes | yes, no flight date |
| Saarland | LVGL | NOT OBTAINABLE (pages 403; Geoportal default charges) | n/a | n/a | n/a | n/a | n/a | no | no |
| Sachsen | GeoSN | yes | dl-de/by-2-0 | 20 cm | annual parts | GetFeatureInfo `Datum` (day) | UNVERIFIED | yes | yes |
| Sachsen-Anhalt | LVermGeo ST | yes (DOP20, DOP100) | dl-de/by-2-0 | 20 cm | 2 y | tile index file `BFDATUM` (day) | UNVERIFIED | yes | yes |
| Schleswig-Holstein | LVermGeo SH | yes | CC BY 4.0 | 20 cm | NOT OBTAINABLE | NOT OBTAINABLE | UNVERIFIED | yes | yes, no date |
| Thüringen | TMDI / TLBG | yes | CC BY 4.0 | 20 cm | NOT OBTAINABLE | NOT OBTAINABLE (production date only) | NOT OBTAINABLE | yes | yes, no flight date |

## Verdict on V6
V6 reads: "Open 20 or 40 cm DOP in Bavaria (incl. historical since 2003), Baden-Württemberg, Rhineland-Palatinate, Berlin, Saxony, NRW, Hamburg".

- Bavaria: CONFIRMED. DOP20 and DOP40 under CC BY 4.0, plus an open historical WMS with one layer per year 2003 to 2025 (40 cm 2003 to 2005, 20 cm from 2006). Flight day readable per location.
- Baden-Württemberg: CONFIRMED for current DOP20 (dl-de/by-2-0). Historical georeferenced DOP not confirmed. No flight date in the service.
- Rhineland-Palatinate: CONFIRMED (dl-de/by-2-0, 20 cm). Only a production date is exposed.
- Berlin: CONFIRMED (dl-de/zero-2.0, 20 cm, 2024 edition). Older editions not checked.
- Saxony: CONFIRMED (dl-de/by-2-0, 20 cm).
- NRW: CONFIRMED, better than stated: 10 cm, dl-de/zero-2.0.
- Hamburg: PARTLY. Open licence dl-de/by-2.0 and a working WMS 2001 to 2026 (year dimension) confirmed from the office's own service and portal, but the service mixes aerial years with closed-licence Maxar satellite years and does not say which, so it is not coded.

Extra open states found: Brandenburg, Bremen, Hessen (endpoint found 2026-11-18, flight day readable), Niedersachsen, Sachsen-Anhalt, Schleswig-Holstein, Thüringen. Mecklenburg-Vorpommern is NOT open: its service metadata restricts external use (see MV block). Saarland not obtainable.
Status of V6: PARTLY CONFIRMED (6 of 7 named states confirmed; Hamburg open with a catch; Bavaria historical since 2003 confirmed).

## Remaining gaps (2026-11-18)
Marked NOT OBTAINABLE means I tried the office's own service and pages named in the row and found nothing machine-readable.
| Gap | State | Tried | Result |
|---|---|---|---|
| Flight date per location | BW | capabilities (not queryable), LGL DOP20 page | viewer only |
| Flight date per location | BB | GetFeatureInfo `bb_dop_info` (HTTP 500, twice), LGB page | viewer only |
| Flight day | RP | info layer, CSW record | production date only |
| Flight date | SH | capabilities; site unreachable | none |
| Flight day | TH | `th_dop_info`, `dop20rgbi_utm_metadaten` | production date only / no right |
| Flight day | BE, HB | capabilities | edition year only (2024, 2023) |
| Cycle | RP, SH, TH, NI, BE, HB, HE | capabilities, CSW (RP) | not stated |
| Historical DOP (beyond BY) | all except BY, HE (1952-67) | not systematically searched | UNVERIFIED |
| Hamburg aerial vs satellite years | HH | capabilities | not stated |
| Saarland openness | SL | LVGL pages (403), Geoportal WMS terms | not obtainable |
| MV permission for external use | MV | CSW record | author decision: ask geodatenservice@laiv-mv.de or drop MV |
