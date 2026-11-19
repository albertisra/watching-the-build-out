# Site footprints: BESS and ground-mounted solar (area, containers, row geometry)
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Scope note: utility-scale commercial sites only. No security details (fences, access points, protective equipment) were collected. Areas below are "site/plot area as stated by the developer", which may differ from the fenced or built-up area. Numbers marked "derived" are my arithmetic, not source statements.

## Key facts

### A. Container dimensions and energy per container

| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 1 | ISO 668 nominal outer size, 20 ft container | 6.058 m x 2.438 m x 2.591 m (L x W x H, standard height); high-cube is 2.896 m high | [S11] (freight table attributing to ISO 668 via Hapag-Lloyd booklet; found via search, not the ISO text); [S12] (BIC gives 20 ft x 8 ft x 8 ft 6 in / 9 ft 6 in HC and cites ISO 668:2013; mm values there are my conversion) | SECONDARY (ISO text not opened) |
| 2 | ISO 668 40 ft container | 12.192 m x 2.438 m x 2.591 m (HC 2.896 m) | [S11], [S12] | SECONDARY |
| 3 | Sungrow PowerTitan 3.0 ST6900UX-8H uses 20 ft HC envelope | 6,058 x 2,896 x 2,438 mm (W x H x D), 55,000 kg, 6,904 kWh nominal, 2 x 450 kVA | [S3] Sungrow datasheet, marked "Preliminary", Version 3, (c) 2026 | VERIFIED |
| 4 | Tesla Megapack 2 (Rev. 1.0, 6 Aug 2021) | 2-h: 1,297.6 kW / 2,595.2 kWh; 4-h: 771.4 kW / 3,085.6 kWh; enclosure 7,250 x 1,600 x 2,507 mm; 30,500 kg | [S1] Tesla datasheet (preliminary) | VERIFIED |
| 5 | Tesla Megapack 2 XL (Rev. 1.5.1, 10 Feb 2023) | 2-h: 1,927 kW / 3,854 kWh; 4-h: 979 kW / 3,916 kWh; enclosure 8,800 x 1,650 x 2,785 mm (+/-13 mm); 38,100 kg | [S2] Tesla datasheet | VERIFIED |
| 6 | Tesla Megapack 3 (unveiled Sep 2025) | "approximately 5 MWh of storage capacity per unit", up from 3.9 MWh in Megapack 2XL; dimensions not in the page I read (another source says 8.1 x 1.6 x 2.8 m, not verified) | [S4] pv magazine 9 Sep 2025 | SECONDARY |
| 7 | CATL TENER (launched 12 Apr 2024) | 6.25 MWh per 20 ft (TEU) container; press release claim: +30% energy density per area and -20% station footprint versus previous 5 MWh containerized system | [S5] pv magazine 12 Apr 2024 (press-release based, not a CATL datasheet) | SECONDARY |
| 8 | CATL EnerC 3.72 MWh (20 ft) | Only reseller listings found; no CATL datasheet opened | search results only | UNVERIFIED |
| 9 | BYD MC Cube-T (launched Apr 2024) | Search snippets: MC12C-B6437 6,431 kWh usable, 2,438 x 7,550 x 2,896 mm, 53 t; MC10C-B5365 5,360 kWh, 6,058 mm long; "footprint up to 24.7% smaller than predecessor". The enfsolar page returned 403 and the BYD PDF had no readable specs | search snippets of [S13] | UNVERIFIED |
| 10 | Fluence Gridstack Pro 5000 Series | "up to 5.6 MWh" in a 20 ft enclosure (spec table 4,888 to 5,644 kWh for 5000 Series, reading uncertain). Fluence datasheet PDF not readable by my tools | search snippets (pv magazine Australia, Fluence brochure) | UNVERIFIED |
| 11 | Fluence Smartstack | claimed up to 7.5 MWh with split battery pod/skid design (not a single 20 ft box); dimensions not found | search snippets | UNVERIFIED |
| 12 | Sungrow PowerTitan 3.0 family (Jun 2025) | Flex 3.45 MWh, Class 6.9 MWh, Plus 12.5 MWh | [S6] pv magazine 10 Jun 2025 | SECONDARY |
| 13 | Fire separation / row spacing distances in a standard or datasheet | Not found. The Tesla and Sungrow datasheets opened give no spacing. I did not open NFPA 855, VdS, or any German guideline | none | OPEN (not found) |

Derived container densities (energy divided by outer footprint L x W; excludes aisles):

| Product (datasheet year) | Energy MWh | Footprint m2 | MWh per m2 of box | Status of inputs |
|---|---|---|---|---|
| Megapack 2, 4-h (2021) | 3.086 | 7.25 x 1.60 = 11.60 | 0.27 | VERIFIED inputs |
| Megapack 2 XL, 4-h (2023) | 3.916 | 8.80 x 1.65 = 14.52 | 0.27 | VERIFIED inputs |
| Sungrow ST6900UX-8H (2026) | 6.904 | 6.058 x 2.438 = 14.77 | 0.47 | VERIFIED inputs |
| CATL TENER (2024), 20 ft ISO | 6.25 | 14.77 | 0.42 | energy SECONDARY, footprint assumed ISO |

### B. Real German BESS sites with both capacity and area stated

All m2 per MW and per MWh are derived. "Plan" means the figure is from a construction-start or permit announcement.

| # | Site (developer) | MW / MWh | Area stated | m2/MW | m2/MWh | Source | Status |
|---|---|---|---|---|---|---|---|
| 1 | Hamm, Kraftwerk Westfalen (RWE), ~1.1 h | 140 / 151 | ~14,000 m2 | 100 | 93 | [S14] RWE press release 31 May 2023; commissioned Dec 2024 [S15] | VERIFIED |
| 2 | Neurath (RWE), ~1.05 h | 80 / 84 | ~7,500 m2 | 94 | 89 | [S14] | VERIFIED |
| 3 | Bollingstedt, Schleswig-Holstein (Eco Stor), 2.3 h | 103.5 / 238 | ~1.2 ha | 116 | 50 | [S16] pv magazine 22 Apr 2024; [S17] 5 Jun 2025 (both state 1.2 ha) | SECONDARY (trade press, repeated in two articles) |
| 4 | Hambach, NRW (RWE), 2 h, 128 containers | 236 / 470 | ~3 ha | 127 | 64 | [S18] contextcrew 29 Jul 2026 (3 ha); [S19] boerse-express 29 Jul 2026 (3 ha, 128 containers) | SECONDARY |
| 5 | Kraenzlin, Brandenburg (re.venture), 4 h, permit stage | 60 / 240 | 1.5 ha | 250 | 62.5 | [S20] agrarheute 18 Sep 2025 | SECONDARY (plan) |
| 6 | Foerderstedt, Saxony-Anhalt (Eco Stor), ~2.3 h | 300 / >700 | ~8 ha | 267 | <=114 | [S21] solarserver 5 Nov 2025 | SECONDARY (plan) |
| 7 | Boxberg (LEAG), 4 h | 400 / 1,600 | 6 ha | 150 | 37.5 | media reports in search results; the ms-aktuell page returned 403 and ingenieur.de did not state area | SECONDARY (not opened in full) |
| 8 | Klostermansfeld (BW ESS), ~5.7 h | 1,000 / up to 5,700 | ~15 ha, >1,100 containers | 150 | 26 | [S22] cleanthinking 1 Jul 2026 | SECONDARY (plan) |

Excluded: Gundremmingen (RWE). The search snippet said 55 ha for a 400 MW / 700 MWh battery, but the pv-magazine.de article states 55 ha is the adjoining solar park, not the battery [S23]. Not used.

Per-container energy implied by the table (derived): Hambach 470 MWh / 128 = 3.7 MWh per container (2026 build, early-generation boxes or mixed); Klostermansfeld 5,700 / ">1,100" = about 5.2 MWh or less per container.

Empirical range (derived from rows 1 to 8):
- Per MW: 94 to 267 m2/MW; the six sites that are not "plan with extra expansion land" cluster at 94 to 150 m2/MW.
- Per MWh: 26 to 114 m2/MWh. By duration: ~1 h about 90 m2/MWh (rows 1, 2); ~2 to 2.3 h about 50 to 64 (rows 3, 4; row 6 up to 114); 4 h about 37 to 62 (rows 5, 7); ~5.7 h about 26 (row 8).
- Caution: duration and build year are confounded (newer, longer-duration sites are also denser per MWh).

Unverified literature figures (found only in search-result summaries, not opened): a NABU 2026 FAQ is said to assume a 40 ft container holds 1 to 3 MWh and seals about 30 m2; a Swiss trade-press report of a German study is said to use about 5 ha per GWh (= 500 m2/MWh), which is 5 to 10 times higher than the project data above and probably refers to total plot area including reserve land. Both UNVERIFIED; the NABU PDF returned 404 when I fetched it.

### C. Ground-mounted solar land use in Germany

| # | Fact | Value | Source | Status |
|---|------|-------|--------|--------|
| 14 | Specific land take of newly commissioned PV-FFA (ZSW, 2 Jun 2025, for the BMWE EEG Erfahrungsbericht under section 99 EEG) | 3.31 ha/MW (2004), 4.24 (2006), 3.50 (2008), 2.78 (2010), 1.94 (2012), 1.62 (2014), 1.51 (2016), 1.31 (2018), 1.17 (2020), 0.95 (2022), 0.88 (2024). Text: "bis 2008 ... 3,5 Hektar und mehr", "bis 2021 auf 1 ha/MW", "0,88 ha/MW im Jahr 2024" | [S7] ZSW, Kelm and Stauch, Fig. 3 and text | VERIFIED |
| 15 | Cause of the decline (ZSW) | "gestiegenen Modulwirkungsgraden, geringeren Modulreihenabstaenden und dem Einfluss groesserer Anlagen" | [S7] | VERIFIED |
| 16 | Non-subsidised PV-FFA commissioned 2024 | 0.83 ha/MW vs 0.88 for all | [S7] | VERIFIED |
| 17 | Stock end 2024 | 31,288 MW on 45,223 ha (average 1.45 ha/MW, derived; older parks dominate area) | [S7] Table 1 | VERIFIED |
| 18 | FA Wind und Solar (May 2025) quoting ZSW update 2023 | 4.1 ha/MW (2006) to 0.9 ha/MW (2023) | [S8] | VERIFIED as a quotation (secondary to ZSW) |
| 19 | UBA: "less than 1 ha per MW" for new plants in 2025, about 4 ha in 2006 | as quoted on a commercial page; UBA page itself returned 404 | [S24] logicenergy quoting UBA | SECONDARY |
| 20 | Individual German parks (derived ha per MW): Alttrebbin 125 ha built / 151 MWp = 0.83 (plot 149 ha = 0.99); Witznitz 500 ha / 605 MW = 0.83; Weesow-Willmersdorf 164 ha module area / 187 MW = 0.88; Langenenslingen-Wilflingen ~60 ha PV / ~80 MWp = 0.75 (total 78 ha = 0.98) | [S25] EnBW Alttrebbin; [S26] l-iz.de; [S27] de.wikipedia; [S28] EnBW | SECONDARY (Weesow, Witznitz); VERIFIED as operator statements (EnBW pages) |
| 21 | East-west vs south, ha per MWp | A commercial page is said (in search snippet) to give 1.0 ha/MWp south fixed tilt and 0.7 to 0.8 east-west bifacial; when I fetched the page it did not contain orientation-specific values | none usable | UNVERIFIED |
| 22 | Row pitch, tilt, GCR | No German primary source opened. A vendor glossary gives a formula: pitch P = L cos(tilt) + d, d = L sin(tilt) / tan(alpha_min), alpha_min = 90 - latitude - 23.45 deg. Worked example Munich, 1.7 m module, 20 deg: P = 3.34 m; Berlin P about 3.93 m; Hamburg about 4.11 m. The vendor's own tables contain internal inconsistencies, so I recalculated | [S29] surgepv.com glossary | SECONDARY (geometry is textbook; German-specific values are my recalculation) |

Derived GCR (module projection width divided by pitch) for the Munich example: 1.60 m / 3.34 m = 0.48; Hamburg: 1.60 / 4.11 = 0.39. Derived, not sourced. Thuenen, KNE and Fraunhofer ISE "Aktuelle Fakten" (version dated 11 Nov 2026) were reachable, but the ISE PDF is 7.4 MB and my tools could not extract text from it; I did not find a land-use figure in its HTML page.

## Details

Why "per MWh" fell over time: row 1 vs row 8 shows 93 vs 26 m2/MWh, but also a move from 1 h to about 5.7 h duration. For footprint-based sizing, area scales more with the number of power conversion blocks, transformers and aisles (per MW) and with the number of battery boxes (per MWh). Our conversion from area to MW and MWh should therefore carry both a per-MW and a per-MWh estimate and use the build year as a covariate.

The Tesla datasheets give no site layout. Tesla's own Megablock "248 MWh per acre" claim appeared in a search snippet only and is not confirmed; I could not open the page.

## (verify) items from KICKOFF.md

| ID | Claim in KICKOFF.md | Finding | Verdict | Source |
|---|---|---|---|---|
| V3 | Typical BESS site footprint per MW and per MWh; container dimensions | 20 ft ISO 6.058 x 2.438 x 2.591 m; 40 ft 12.192 m long. Real German sites: 94 to 267 m2/MW (core 94 to 150), 26 to 114 m2/MWh. Tesla and Sungrow boxes are not ISO 20 ft/40 ft (Megapack 2 XL is 8.8 m long). | CONFIRMED with ranges; only 8 projects, mostly trade-press areas | S1 to S3, S11 to S22 |
| V4 | Typical solar park footprint per MWp | ZSW: 0.88 ha/MW for 2024 commissioning, 0.95 (2022), 1.17 (2020), 1.31 (2018); older parks 1.5 to 4 ha/MW. Use 0.7 to 1.2 ha/MWp for new parks. Note ZSW divides by MW as registered in MaStR (may be AC or DC, not stated in the paper I read). | CONFIRMED | S7, S8 |
| (KICKOFF) | "battery energy density per container has risen quickly and newer sites store more MWh per m2" | Per container: 3.1 MWh (Megapack 2, 2021) to 3.9 (2023) to about 5 (Megapack 3, 2025) to 6.9 (Sungrow 20 ft, 2026 datasheet); about 2.2x in five years. Per m2 of box: Megapack 2 to 2 XL is flat (0.27 MWh/m2); the jump comes with 20 ft 6+ MWh boxes (about 0.42 to 0.47). Site level: 93 (2023 plan, 1 h) to 50 (2024) to 26 m2/MWh (2026 plan, 5.7 h), but duration is confounded. | CONFIRMED for MWh per container and for newer 20 ft products; CORRECTED to "not uniform": 2021 to 2023 gains did not improve MWh per m2 of box | S1 to S5, S14, S16, S22 |
| V3b | Typical construction durations | See construction_durations.md | see that note | n/a |

## What this means for our method

1. Footprint to MW/MWh: use per-MW and per-MWh bands, not a single constant. Suggested priors (derived): BESS 100 to 150 m2/MW (core), 25 to 115 m2/MWh with build year (newer = lower). Keep MWh as the more uncertain output; duration is not observable from imagery.
2. Container counting (orthophoto): converting counted containers to MWh needs the product year; use roughly 2.6 to 3.1 MWh for 2021-era, 3.9 MWh for 2023, 5 to 7 MWh for 2025 to 2026 boxes. Hambach implies 3.7 MWh average per box in a 2026 project, so use ranges.
3. Pixel-level consequences are in the table below. A 1 MW BESS is at most a couple of Sentinel pixels and cannot be delineated at 10 m; detection of small BESS relies on orthophotos or on change signals only.
4. Solar: row pitch 3 to 4 m means roughly 2.5 to 3 module rows per 10 m pixel, so a 10 m pixel is a mix of module, gap and ground. Mixed-pixel signal is nearly constant within a park, which suits texture or temporal-change features rather than pure-pixel classification.
5. Plot area from registry or planning documents overstates the built footprint (Alttrebbin: 149 ha plot vs 125 ha built).

### Derived footprint estimates (1 Sentinel pixel = 10 m x 10 m = 100 m2, nominal)

Inputs: BESS 50 to 115 m2/MWh (rows 3, 4, 6) cross-checked against 94 to 267 m2/MW; solar 0.88 ha/MWp central (ZSW 2024), 0.7 to 1.2 range (ZSW and park examples).

| Site | Arithmetic | Area m2 (central; range) | Pixels (central; range) | Label |
|---|---|---|---|---|
| 1 MW / 2 MWh BESS | 2 MWh x 50 to 115 = 100 to 230; one 20 ft box alone is 14.8 m2 | ~150 (100 to 400; small sites carry fixed overhead not evidenced in my sources) | ~1.5 (1 to 4) | derived, weak (no small-site data) |
| 10 MW / 20 MWh BESS | 20 x 50 to 115 = 1,000 to 2,300; per-MW check 10 x 94 to 267 = 940 to 2,670 | ~1,500 (1,000 to 2,700) | ~15 (10 to 27) | derived |
| 100 MW / 200 MWh BESS (2 h) | 200 x 50 to 115 = 10,000 to 23,000; check Bollingstedt 1.2 ha for 103.5 MW | ~12,000 to 15,000 (10,000 to 27,000) | ~120 to 150 (100 to 270) | derived |
| 100 MW / 400 MWh BESS (4 h), for comparison | 400 x 26 to 62 = 10,400 to 24,800; Boxberg-like 150 m2/MW gives 15,000 | ~15,000 (10,000 to 25,000) | ~150 (100 to 250) | derived |
| 1 MWp solar | 1 x 0.88 ha = 8,800 m2 (0.7 to 1.2 ha) | 8,800 (7,000 to 12,000) | 88 (70 to 120) | derived |
| 10 MWp solar | 10 x 0.88 = 8.8 ha | 88,000 (70,000 to 120,000) | 880 (700 to 1,200) | derived |
| 50 MWp solar | 50 x 0.88 = 44 ha | 440,000 (350,000 to 600,000) | 4,400 (3,500 to 6,000) | derived |

Pixel counts assume footprint is axis-aligned; boundary pixels reduce pure-pixel counts. Sentinel-2 10 m bands only (B2, B3, B4, B8); 20 m bands would reduce the counts by 4x.

## Open questions

- ISO 668 text itself was not opened (paywalled); values are from freight and BIC pages.
- No standard or datasheet found stating inter-container spacing or fire separation distances. Needs NFPA 855 / VdS 3999 / local Brandschutzkonzept checks (not done).
- BYD, Fluence and CATL manufacturer datasheets could not be read by my tools (PDF text extraction failed or 403). The "MWh per container" time series therefore rests on Tesla and Sungrow datasheets only.
- ZSW basis (MW AC or MWp DC) not clarified; confirm in the EEG Erfahrungsbericht.
- Row pitch, tilt and east-west density need a German primary source (KNE, Fraunhofer ISE, C.A.R.M.E.N.).
- Fraunhofer ISE "Aktuelle Fakten zur Photovoltaik in Deutschland" (version of 11 Nov 2026) was not text-readable here; check it for a land-use figure.

## Sources

1. Tesla, Megapack 2 Datasheet Rev. 1.0, 6 Aug 2021. https://marketingdocuments.energytoolbase.com/marketing/TeslaMegapack2Datasheet.pdf (retrieved 2026-11-12, read via saved PDF)
2. Tesla, Megapack 2 XL Datasheet Rev. 1.5.1, 10 Feb 2023 (hosted copy). https://portal.ct.gov/-/media/csc/3_petitions-medialibrary/petitions_medialibrary/mediapetitionnos1601-1700/pe1607/petitionersubmissions/supplement-attachment-a---megapack_2_xl_datasheet.pdf (retrieved 2026-11-12)
3. Sungrow, PowerTitan 3.0 ST6900UX-8H datasheet, Version 3, 2026, "Preliminary". https://info-support.sungrowpower.com/datasheet-materials/1ee485cf-69a9-40c9-83d0-b84d43470387.pdf (retrieved 2026-11-12)
4. pv magazine, Tesla unveils new generation of utility-scale batteries, 9 Sep 2025. http://www.pv-magazine.com/2025/09/09/tesla-unveils-new-generation-of-utility-scale-batteries/ (retrieved 2026-11-12)
5. pv magazine, CATL unveils first mass-producible battery storage with zero degradation, 12 Apr 2024. http://www.pv-magazine.com/2024/04/12/catl-unveils-first-mass-producible-battery-storage-with-zero-degradation/ (retrieved 2026-11-12)
6. pv magazine, Sungrow unveils PowerTitan 3.0, 10 Jun 2025. https://www.pv-magazine.com/2025/06/10/sungrow-unveils-powertitan-3-0-bess-with-684-ah-cell-liquid-cooling/ (retrieved 2026-11-12)
7. ZSW (Kelm, Stauch), Flaecheninanspruchnahme von PV-Freiflaechenanlagen, Update 2024, 2 Jun 2025. https://www.zsw-bw.de/fileadmin/user_upload/Flaecheninanspruchnahme_PV-FFA__Update_2024.pdf (retrieved 2026-11-12)
8. Fachagentur Wind und Solar, Kompaktwissen: Bedeutung der Photovoltaik in Deutschland, May 2025. https://www.fachagentur-wind-solar.de/fileadmin/Veroeffentlichungen/Solar/Allgemein/FA_Wind_Solar_Kompaktwissen_Bedeutung_Solarenergie.pdf (retrieved 2026-11-12)
9. Fraunhofer ISE, Aktuelle Fakten zur Photovoltaik in Deutschland, version of 11 Nov 2026 (page reached; PDF text not extractable). https://www.ise.fraunhofer.de/content/dam/ise/de/documents/publications/studies/aktuelle-fakten-zur-photovoltaik-in-deutschland.pdf (retrieved 2026-11-12)
10. (not used)
11. Freight-industry container size table citing ISO 668 (found via search; GoFreight). https://gofreight.com/blog/education/shipping-container-dimensions-everything-you-need-to-know.html (search result only, retrieved 2026-11-12)
12. BIC, Shipping container sizes (cites ISO 668:2013). https://bic-boxtech.org/shipping-container-sizes/ (retrieved 2026-11-12)
13. enfsolar, BYD MC Cube-T listing. https://www.enfsolar.com/pv/storage-system-datasheet/16358 (403 when fetched; snippets only)
14. RWE press release, 31 May 2023, construction start Neurath and Hamm. https://www.rwe.com/presse/rwe-generation/2023-05-31-rwe-startet-bau-von-batteriespeicher-grossprojekt/ (retrieved 2026-11-12)
15. RWE press release, 14 Feb 2025, commissioning Hamm and Neurath. https://www.rwe.com/presse/rwe-generation/2025-02-14-rwe-nimmt-220-mw-batteriespeicher-in-hamm-und-neurath-in-betrieb/ (retrieved 2026-11-12)
16. pv magazine Deutschland, Eco Stor beginnt Bau ..., 22 Apr 2024. https://www.pv-magazine.de/2024/04/22/eco-stor-beginnt-bau-von-238-megawattstunden-speicher-in-schleswig-holstein/ (retrieved 2026-11-12)
17. pv magazine Deutschland, Batteriespeicher von Eco Stor ... eingeweiht, 5 Jun 2025. https://www.pv-magazine.de/2025/06/05/batteriespeicher-von-eco-stor-mit-1035-megawatt-offiziell-eingeweiht/ (retrieved 2026-11-12)
18. contextcrew, RWE baut 236-MW-Batteriespeicher im Tagebau Hambach, 29 Jul 2026. https://www.contextcrew.de/rwe-baut-236-mw-batteriespeicher-im-tagebau-hambach/ (retrieved 2026-11-12)
19. boerse-express, Stromspeicher-Boom: 236 MW Hambach, 300 MW Foerderstedt, 29 Jul 2026. https://www.boerse-express.com/news/articles/stromspeicher-boom-236-mw-hambach-300-mw-foerderstedt-online-933334 (retrieved 2026-11-12)
20. agrarheute, Mega-Batteriespeicher in Brandenburg ... 240 MWh, 18 Sep 2025. https://www.agrarheute.com/energie/strom/mega-batteriespeicher-brandenburg-stehen-bald-240-mwh-gegen-blackouts-636617 (retrieved 2026-11-12)
21. solarserver, Deutschlands groesster Batteriespeicher wird in Foerderstedt gebaut, 5 Nov 2025. https://www.solarserver.de/2025/11/05/deutschlands-groesster-batteriespeicher-wird-in-foerderstedt-gebaut/ (retrieved 2026-11-12)
22. cleanthinking, Grossspeicher BESS Klostermansfeld, 1 Jul 2026. https://www.cleanthinking.de/klostermansfeld-europas-groesster-speicher (retrieved 2026-11-12)
23. pv magazine Deutschland, RWE baut Batteriespeicher ... Gundremmingen, 29 Oct 2025. https://www.pv-magazine.de/2025/10/29/rwe-baut-batteriespeicher-mit-700-megawattstunden-am-ehemaligen-akw-gundremmingen-standort/ (retrieved 2026-11-12)
24. Logic Energy, Freiflaechen-Photovoltaik 2026 (quotes UBA). https://www.logicenergy.de/pv-freiflaechenanlagen (retrieved 2026-11-12)
25. EnBW, Solarpark Alttrebbin. https://www.enbw.com/unternehmen/themen/solarenergie/solarpark-alttrebbin/ (retrieved 2026-11-12)
26. L-IZ.de, Energiepark Witznitz offiziell am Netz, 4 Jul 2024. https://www.l-iz.de/wirtschaft/firmenwelt/2024/07/energiepark-witznitz-solarpark-leipziger-sudraum-offiziell-am-netz-596041 (retrieved 2026-11-12)
27. Wikipedia (de), Solarpark Weesow-Willmersdorf. https://de.wikipedia.org/wiki/Solarpark_Weesow-Willmersdorf (retrieved 2026-11-12)
28. EnBW, Solarpark Langenenslingen-Wilflingen. https://www.enbw.com/unternehmen/themen/solarenergie/solarpark-langenenslingen-wilflingen/ (retrieved 2026-11-12)
29. Surge PV, Glossar Reihenabstand PV (vendor). https://www.surgepv.com/de/glossar/reihenabstand-pv (retrieved 2026-11-12)
