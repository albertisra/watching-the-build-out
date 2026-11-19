# Market data sources: Energy-Charts, SMARD, the 15-minute day-ahead switch, control variables, literature
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Caveat on method: WebFetch passes pages through a small summarising model. Quotes and numbers below are what that tool returned; where it said it estimated something (counts of array entries) this is flagged. PDFs (SMARD user manual, NEMO committee PDF, ACER decision, DWD terms PDF) came back as unreadable binary and were NOT read. EPEX SPOT and Elia press pages returned HTTP 403.

## Key facts
| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| 1 | https://api.energy-charts.info/v2 resolves | Yes: self-describing JSON, 19 GET endpoints (cbet, cbpf, frequency, installed_power, public_power, public_power_forecast, total_power, price, price_current, price_next_day, ren_share/solar_share/wind_* shares, signal) | [1] | VERIFIED |
| 2 | https://api.energy-charts.info/openapi.json resolves | Yes (content returned; describes v1 endpoints) | [2] | VERIFIED |
| 3 | https://api.energy-charts.info/llms-full.txt resolves | Yes (content returned) | [3] | VERIFIED |
| 4 | /price parameters | `bzn` (default DE-LU), `start`, `end`; start/end accept ISO 8601, a day (YYYY-MM-DD) or Unix seconds; empty end = start | [2] | VERIFIED |
| 5 | /price response fields | `license_info`, `unix_seconds`, `price`, `unit`, `deprecated`. Test call returned exactly these 5 top-level keys, unit "EUR / MWh", deprecated false | [4] (live call) | VERIFIED |
| 6 | Exact `license_info` returned for DE-LU (and DE-AT-LU) | "CC BY 4.0 (creativecommons.org/licenses/by/4.0) from Bundesnetzagentur \| SMARD.de" | [4][5][6][7] live calls | VERIFIED |
| 7 | DE-LU resolution before switch | 24 values/day on 2025-09-30 (hourly, 3600 s spacing) | [5] | VERIFIED |
| 8 | DE-LU resolution after switch | 96 values/day on 2025-10-01 (900 s spacing), first timestamp 1759269600 | [4] | VERIFIED |
| 9 | Time convention in Energy-Charts | `unix_seconds` = UTC epoch of the interval START. 1759269600 = 2025-09-30 22:00 UTC = 2025-10-01 00:00 CEST, i.e. a "day" query runs from local midnight. Docs: day inputs use the local timezone of the zone; timestamps mark start of period (v2 doc) | [1][2][4] | VERIFIED (DST-change days not tested) |
| 10 | Earliest DE-LU date | 2018-10-01 returns 24 values (first ts 1538344800 = 2018-10-01 00:00 CEST). Earlier DE-LU dates not tested | [6] | VERIFIED for 2018-10-01 as a valid start; earlier absence UNVERIFIED |
| 11 | DE-AT-LU earliest | 2015-01-05 returns 24 values (first ts 1420412400 = 2015-01-05 00:00 CET). 2014-12-31 returned HTTP 400. Exact first day (possibly 2015-01-01) not pinned | [7][8] | VERIFIED for 2015-01-05; earliest UNVERIFIED |
| 12 | Rate limit | Default 2 req/min, burst 4 per client IP per endpoint; /price 2 req/min, burst 2; 429 with Retry-After; higher limits for commercial use on request. Observed: two rapid /price calls produced HTTP 429 (Retry-After 10 s and 2 s) | [3][8] | VERIFIED |
| 13 | General licence | "Unless stated otherwise CC BY 4.0, attribution to Energy-Charts.info"; other zones' prices "for private and internal use only"; AT, BE, CH, CZ, DE-LU, DE-AT-LU, DK1, DK2, FR, HU, IT-North, NL, NO2, PL, SE4, SI are CC BY 4.0 from SMARD | [2][3] (tool paraphrase) | VERIFIED (paraphrased by fetch tool) |
| 14 | /public_power | `country` (default de), `start`, `end`, `subtype`; returns `unix_seconds`, `production_types` [{name, data}], `deprecated`; MW, public net production | [2] | VERIFIED |
| 15 | /total_power | Same structure; includes industrial self-supply; Germany only | [2] | VERIFIED |
| 16 | /installed_power | `country`, `time_step` (yearly default; monthly Germany only), `installation_decommission`; returns `time`, `production_types`, `last_update`, `deprecated`. Generally GW; battery storage in GWh (per docs). `time` labels period, values = state at period end | [2][9] | VERIFIED |
| 17 | Battery series in /installed_power (DE, monthly) | Series named "Battery storage (power)" and "Battery storage (capacity)". Last values (11.2026): power 22.444, capacity 35.249; time array ends 11.2026; last_update 1794490998. Units not shown in the payload; docs imply capacity in GWh and power in GW (so ~22.4 GW / 35.2 GWh) | [9] | VERIFIED for names/values; unit assignment from docs |
| 18 | Source of Energy-Charts battery data | The API/docs name no source and the payload has no source/licence field. Secondary reporting says Energy-Charts draws it from the MaStR | [10] | SECONDARY |
| 19 | SMARD licence for market data | "Creative Commons Namensnennung 4.0 International (CC BY 4.0)"; credit line "Bundesnetzagentur \| SMARD.de"; downloaded data may be used in parts, combined and changed ("dürfen in Teilen genutzt, zusammengefügt und verändert werden") | [11][12] | VERIFIED |
| 20 | SMARD caveat on wholesale prices | "We are currently conducting a thorough examination of legal licensing issues relating to wholesale prices" (HEDWIG proceedings); new data-use concept in preparation | [11][12] | VERIFIED |
| 21 | SMARD site-content licence (separate) | Impressum states site content is under CC BY-ND (text says 4.0, footer badge says 3.0); relevant to page content, not to market-data downloads, which have their own terms [11] | [13] | VERIFIED (inconsistency on the page) |
| 22 | SMARD chart_data endpoints | `https://www.smard.de/app/chart_data/{filter}/{region}/index_{resolution}.json` returns `{"timestamps":[ms,...]}` weekly steps (first 1538344800000 = 2018-09-30 22:00 UTC; last 1794178800000 = 2026-11-08 23:00 UTC; ~424 entries, count estimated by the tool). Series: `.../{filter}_{region}_{resolution}_{timestamp}.json` with keys `meta_data`, `series` = [[ms, EUR/MWh],...] | [14][15][16][17] (live fetches) | VERIFIED for filter 4169, region DE-LU, resolutions hour and quarterhour |
| 23 | Filter 4169 = DE-LU day-ahead price | The URL pattern with 4169/DE-LU resolved and returned prices matching Energy-Charts (e.g. 102.6 at 1759269600000). SMARD's own documentation of the ID was not found; the eta-nexus library docs also list 4169 | [14][16][18] | VERIFIED empirically; official ID table UNVERIFIED |
| 24 | SMARD hour vs quarterhour files after switch | Both exist for the week of 2025-09-29. Quarterhour: 1759269600000 -> 102.6, then 92.24, 86.03. Hour file: 1759269600000 -> 91.57. 15-min values for 2025-10-01 are in SMARD "from 1 October" (after initial technical problems) | [15][16][19] | VERIFIED (values); averaging rule not documented in sources I read |
| 25 | SMARD time convention | Unix ms UTC; weekly files start Monday 00:00 local (22:00/23:00 UTC). DST handling beyond that not documented in what I read | [14][15] | UNVERIFIED for DST rules |
| 26 | SMARD earliest data | chart_data index starts 2018-09-30 22:00 UTC (= 2018-10-01 00:00 CEST) for DE-LU. SMARD's DE-AT-LU series not queried | [14] | VERIFIED (DE-LU) |
| 27 | SDAC 15-min MTU first delivery | Trading day 30 September 2025, first delivery day 1 October 2025 (confirmed 12 Sep 2025 by the Market Coupling Steering Committee, via OTE) | [20][21] | VERIFIED |
| 28 | Earlier postponement | Go-live moved from 11 June 2025 to 30 September 2025, announced 14 May 2025, reason "non-technical readiness of some Parties" | [22] | VERIFIED |
| 29 | Results on 30 Sep 2025 | EPEX results for 96 quarter-hours published 13:08; 60-minute contracts still tradable; Ireland stays 30-min; Switzerland not included | [23] (search snippet, EPEX page itself 403) | SECONDARY |
| 30 | BNetzA treatment | BK8-22-001-A Mitteilung 3 (as of 18.08.2025): "stündlich" to be read as "viertelstündlich" after the switch | [24] | VERIFIED |
| 31 | DE-AT-LU split | Joint zone divided; DE-LU trading for delivery from 1 Oct 2018 (ACER Decision 06/2016, dated 17 or 18 Nov 2016 depending on source; EPEX/ECC/TenneT notices confirm go-live) | [25] | SECONDARY (search results; ACER/EPEX PDFs not opened) |
| 32 | SDAC max price | Raised from 3000 to 4000 EUR/MWh for trading day 10 May 2022 (delivery 11 May); a further rise to 5000 planned for 20 Sep 2022 was suspended; reference values now +4000 / -500 EUR/MWh | [26][27] | SECONDARY (exchange notices via search; ACER Decision 01/2023 and 02/2026 PDFs unreadable) |
| 33 | HMMCP methodology change | ACER Decision 02/2026 amends the SDAC HMMCP methodology (NEMO proposal received 4 Aug 2025); content not read | [27] | UNVERIFIED (content) |
| 34 | DWD licence | CC BY 4.0 for open data; source credit required; exact template on a separate DWD page (not opened) | [28] | VERIFIED (licence), UNVERIFIED (exact attribution text) |
| 35 | EEX EUA data | EEX market-data page: data "as is", systematic republication needs express permission; no free bulk download confirmed. ICAP says EEX auction data not downloadable | [29][30] | VERIFIED (terms), free historical source OPEN |

## Details

### Energy-Charts API
- `/v2` is a machine-readable catalogue. Its envelope adds explicit `timezone`, `resolution`, `interval_minutes` fields (named in the openapi text) that I did not see in a live v2 call. The v1 `/price` call returned the plain 5-key structure above.
- Day-ahead price query for 2025-10-01: 96 prices, 900 s apart. For 2025-09-30 and for 2018-10-01 and 2015-01-05: 24 hourly values. So the series is mixed resolution, switching on 2025-10-01 delivery. A pipeline must infer resolution from timestamp differences, not assume 24 values per day.
- Licence text returned verbatim in each live response: "CC BY 4.0 (creativecommons.org/licenses/by/4.0) from Bundesnetzagentur | SMARD.de". The spec assumption "CC BY 4.0 with attribution to energy-charts.info" is partly right: the general terms say so, but for price data the response states the source and SMARD attribution. Cite both. The underlying data thus is SMARD/BNetzA (which itself obtains it from ENTSO-E per SMARD, secondary [18]); EPEX SPOT is named in the docs only as the contact for non-listed zones.
- Rate limit: be conservative; two consecutive /price calls from one IP hit 429. One request per ~30 s with Retry-After handling, and cache locally.
- Production endpoints: `/public_power` (MW, net public production by type) and `/total_power` (includes self-supply, Germany only). Solar appears as a production type in the `production_types` list (exact name strings not captured in a live call; fetch one day to confirm). Load: the docs list `/public_power` and `/total_power` but I did not confirm a "Load" series name; check `production_types` for a load entry, and the SMARD "Realisierter Stromverbrauch" filter as an alternative (not verified).
- Installed capacity: `/installed_power` monthly for Germany has battery power and capacity series. These are the MaStR-derived totals (secondary) and include home storage (secondary reporting cites ~2.6 million systems in the register), so they are NOT utility-scale only.

### SMARD
- chart_data pattern verified live. Weekly files (Monday 00:00 local). Hour file for the week of 2025-09-29 has 168 entries; quarterhour file about 671-672 (estimated by the tool). No nulls in either.
- Observed: hourly value at 2025-10-01 00:00 local = 91.57; the quarter-hour values at that hour begin 102.6, 92.24, 86.03. The fourth value was not captured, so I cannot show that 91.57 is the arithmetic mean. This is a check to do before use. The hour-file values for 2025-09-29 to 30 (e.g. 90.95, 88.76) differ from Energy-Charts hourly 2025-09-30 (101.1, 98.43), a different day, so no comparison is possible; do a like-for-like check.
- Licence: see rows 19-21. The HEDWIG caveat means the SMARD terms for wholesale prices may change. Energy-Charts redistributes the same data under CC BY 4.0 now. Record retrieval date and the licence text at download time.
- CSV download centre: the page fetched named CC BY 4.0 but did not list filters or resolutions; the download-centre options (hour/quarter-hour, date limits) are UNVERIFIED. Use chart_data or Energy-Charts.

### The 15-minute day-ahead market (V8)
- Original plan 11 June 2025; postponed 14 May 2025 to 30 September 2025 (non-technical readiness of some parties) [22]. Confirmed on 12 Sep 2025 for trading day 30 Sep, delivery day 1 Oct 2025 [21]. SMARD: "Since 1 October 2025, the day-ahead market has traded on a 15-minute basis" [19]. Ireland stays at 30 minutes; Switzerland separate [23].
- Consequence for an "hourly price": after 2025-10-01 there is no hourly auction price. Any hourly price is a derived aggregate (EPEX says 60-minute contracts remain as block-like products for trading members [23], but these are not the coupled clearing price). Hourly SMARD/Energy-Charts values are aggregated by the provider; the rule is not documented in sources I could read.
- Within an hour, quarter-hour prices differ markedly (a "sawtooth" pattern; Montel-type commentary, secondary, +15% std. dev. in the first week [19 search]). Spread definitions (daily max minus min, top-n minus bottom-n) computed on 96 values are mechanically larger than on 24 values, so a break at 2025-10-01 arises from the definition alone. Use hourly means (4-quarter average) for all periods in the main series and report the 15-minute version separately.

### Other structural breaks
- 2018-10-01: DE-AT-LU split into DE-LU and AT. Spread series before that date are for the joint zone [25].
- Price cap: +3000 -> +4000 EUR/MWh from trading day 10 May 2022 [26]; floor -500; ACER decisions 01/2023 and 02/2026 govern automatic adjustment (contents not read) [27].
- Negative prices for renewables: EEG §51 and the Solarspitzengesetz (2025) were not researched in this session. UNVERIFIED; needs a source (Gesetze-im-Internet, BNetzA).

### Control variables
- Gas: no free, licence-clean daily TTF/THE series found. EEX terms restrict systematic republication [29]; Barchart/Argus are paid; UA Energy map CSV (EEX-sourced, terms unchecked) is not clean. BDEW publishes THE spot snapshots in PDFs (secondary). OPEN. Practical options: academic data via a licensed source, or ECB/World Bank monthly TTF (not checked), or treat gas as unavailable and use month fixed effects.
- Carbon: EEX auction prices have terms restricting republication [29]; ICAP says EEX data not downloadable [30]; ICAP secondary-market data (ICE) is weekly average, 6-month lag, graph/download-only [30]. OPEN for a daily series.
- Solar generation and load: Energy-Charts `/public_power` and `/total_power` (CC BY 4.0 unless response says otherwise) and SMARD chart_data. Filter IDs for solar/load not verified.
- Temperature: DWD CDC open data, CC BY 4.0, credit DWD [28]; hourly air temperature files under opendata.dwd.de/climate_environment/CDC/ (existence seen in search results).

### Literature pointers (as the sources state them)
- Lamp & Samano (2022), "Large-scale battery storage, short-term market outcomes, and arbitrage", Energy Economics 107, 105786, doi:10.1016/j.eneco.2021.105786. Abstract (via search/IDEAS): California batteries 2018-19; activity correlates with load and real-time prices; findings partially consistent with an arbitrage maximiser; battery deployment 2013-2017 reduced average intraday price spreads; market conditions limit profitability. Full text not read. [31]
- Karaduman (2021), "Economics of Grid-Scale Energy Storage in Wholesale Electricity Markets", MIT CEEPR WP 2021-005. South Australia (2017 data): "ignoring price impact of energy storage may lead large biases as arbitrage revenue diminish fast with the size"; accounting for incumbent best responses lowers storage profit by 10%; higher VRE capacity raises storage revenue via price variation. Summaries only. [32]
- Aalto University thesis (German day-ahead, 2023-24, four representative weeks): BESS arbitrage "reduces price extremes, compresses inter-temporal price spreads, and lowers short-term volatility", magnitude depends on charging-cost structure. Thesis, not peer-reviewed; page 403, abstract via search only. [33]
- Modo Energy (commercial, not peer-reviewed): German day-ahead spreads rose from about 30 EUR/MWh (2019) to about 130 EUR/MWh (2024) due to solar-driven midday lows; says battery charging is now cannibalising spreads. [34]
- GB: no peer-reviewed empirical paper on battery effect on wholesale spreads found. Poonyth (Reading PhD, 2016) finds storage revenues rise with wind-driven volatility (pre-battery fleet). Modo reports GB day-ahead spreads of GBP 40/MWh in Feb 2026. All secondary. [35]
- Gap: no peer-reviewed German ex-post estimate of battery capacity on spreads was found. A careful search of Energy Economics, Energy Policy, EWI Cologne and DIW is still needed.

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict | Source |
|---|---|---|---|---|
| V8 | "the day-ahead market moved to 15-minute products in October 2025" | First delivery day 1 Oct 2025 (trading day 30 Sep 2025). Postponed once, from 11 June 2025. Ireland excluded. "Hourly" price after that is a derived aggregate | CONFIRMED (add exact date and the definitional break) | [19][21][22] |
| spec | Energy-Charts licence "CC BY 4.0, attribution energy-charts.info" | Response text: "CC BY 4.0 (...) from Bundesnetzagentur \| SMARD.de"; general terms also CC BY 4.0 with Energy-Charts attribution. Cite both | CORRECTED (per-response wording, SMARD source) | [2][4] |

## What this means for our method
1. Build the price loader to detect resolution per day from timestamp spacing; never assume 24 values. Convert to UTC and handle DST days (23/25 hours) explicitly; define "day" in Europe/Berlin local time.
2. Define the spread on a fixed basis across the whole sample: hourly mean of quarter-hours, plus a separate 15-minute robustness series from 2025-10-01. Include a dummy for 2025-10-01 onward and for the pre/post 2018-10-01 zone change (start the main sample 2018-10-01 to stay inside DE-LU).
3. Attribution line for outputs: "Price data: Bundesnetzagentur | SMARD.de (CC BY 4.0), via Energy-Charts.info (Fraunhofer ISE)". Record retrieval date, given the HEDWIG licensing review.
4. Battery capacity from Energy-Charts includes home storage and is not utility-scale; for the utility-scale count use MaStR (other agents' scope).
5. Rate limit: 2 req/min on /price; request year-sized chunks, cache, honour Retry-After. Or use SMARD chart_data weekly files (no limit stated; unverified).
6. Gas and carbon: licence-clean free daily series unresolved; plan on seasonal/month effects plus solar, load, temperature, and flag gas/ETS as omitted variables.

## Open questions
- Does SMARD document how hourly values are derived from quarter-hours after 2025-10-01 (user manual PDF 04/2026 unreadable here)? Verify mean of 4 quarter-hours with a full hour.
- Exact earliest dates (DE-AT-LU, any DE-LU data before 2018-10-01) and DST-day behaviour.
- Exact `production_types` names for solar and load in Energy-Charts.
- EEG §51 / Solarspitzengesetz details and dates; ACER Decision 02/2026 content.
- Free gas (THE/TTF) and EUA daily price sources with clear licences.
- EPEX SPOT and Elia pages (403) and PDFs need a manual read.

## Sources
1. Energy-Charts API v2 catalogue, https://api.energy-charts.info/v2, retrieved 2026-11-12.
2. Energy-Charts openapi, https://api.energy-charts.info/openapi.json, retrieved 2026-11-12.
3. Energy-Charts llms-full.txt, https://api.energy-charts.info/llms-full.txt, retrieved 2026-11-12.
4. Live call /price?bzn=DE-LU&start=2025-10-01&end=2025-10-01, 2026-11-12.
5. Live call /price?bzn=DE-LU&start=2025-09-30&end=2025-09-30, 2026-11-12.
6. Live call /price?bzn=DE-LU&start=2018-10-01&end=2018-10-01, 2026-11-12.
7. Live call /price?bzn=DE-AT-LU&start=2015-01-05&end=2015-01-05, 2026-11-12.
8. Live call /price DE-AT-LU 2014-12-31 (HTTP 400) and rapid repeat (HTTP 429), 2026-11-12.
9. Live call /installed_power?country=de&time_step=monthly, 2026-11-12.
10. Search result summaries on Energy-Charts battery data (pv-magazine, ess-news, battery-charts.rwth-aachen.de), 2026-11-12. Secondary.
11. SMARD Datennutzung, https://www.smard.de/home/datennutzung, 2026-11-12.
12. SMARD data use (EN), https://www.smard.de/blueprint/servlet/page/bnetza-en/datennutzung/5808, 2026-11-12.
13. SMARD Impressum, https://www.smard.de/home/impressum, 2026-11-12.
14. SMARD index, https://www.smard.de/app/chart_data/4169/DE-LU/index_quarterhour.json (and index_hour.json), 2026-11-12.
15. SMARD series, https://www.smard.de/app/chart_data/4169/DE-LU/4169_DE-LU_quarterhour_1759096800000.json, 2026-11-12.
16. SMARD series, https://www.smard.de/app/chart_data/4169/DE-LU/4169_DE-LU_hour_1759096800000.json, 2026-11-12.
17. SMARD download centre, https://www.smard.de/en/downloadcenter/download-market-data/, 2026-11-12.
18. eta-nexus SMARD docs, https://eta-nexus.readthedocs.io/en/latest/_sources/connections/smard.rst.txt (third party), via search.
19. SMARD "15-minute wholesale prices available", https://www.smard.de/en/15-minute-wholesale-prices-available-218078, dated 2025-10-10.
20. NEMO Committee, https://nemo-committee.eu/assets/files/15-minute-mtu-in-sdac-was-implemented.pdf (PDF unreadable; cited via search snippets).
21. OTE/MCSC, https://www.ote-cr.cz/en/about-ote/ote-news/market-coupling-steering-committee-confirms-go-live-of-15-minute-mtu-in-sdac-on-trading-day-30-september-2025-for-delivery-day-1-october-2025, 2025-09-12.
22. OTE/MCSC, https://www.ote-cr.cz/en/about-ote/ote-news/market-coupling-steering-commitee-aligns-on-rescheduling-of-go-live-date-for-15-minute-mtu-in-sdac-from-11-june-to-30-september-2025, 2025-05-14.
23. EPEX SPOT, https://www.epexspot.com/en/news/15-minute-products-live-epex-spot-day-ahead-markets (403; via search summary).
24. Bundesnetzagentur BK8-22-001-A Mitteilung 3, https://bundesnetzagentur.de/DE/Beschlusskammern/1_GZ/BK8-GZ/2022/2022_4-Steller/BK8-22-0001/BK8-22-0001-A_MitteilungNr3.html?nn=686258, Stand 2025-08-18.
25. DE-AT split: TenneT, EPEX/ECC notices, ACER Q&A Decision 06/2016 (via search results, not opened); e.g. https://www.jao.eu/news/go-live-congestion-management-german-austrian.
26. EPEX/BSP/OTE notices on 4000 EUR/MWh from 10 May 2022, e.g. https://www.epexspot.com/en/news/harmonised-maximum-clearing-price-sdac-be-set-4000-eurmwh-10th-may-2022 (via search).
27. ACER Decision 02/2026, https://www.acer.europa.eu/sites/default/files/documents/Individual%20Decisions/ACER-Decision-02-2026-harmonised-clearing-prices-day-ahead.pdf (unreadable); ACER Decision 01/2023.
28. DWD legal notice, https://www.dwd.de/EN/service/legal_notice/legal_notice.html; CDC terms https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.pdf (unreadable; dated 2024-05-15 per metadata).
29. EEX market data, https://eex.com/en/market-data/environmentals/eu-ets-auctions, 2026-11-12.
30. ICAP Allowance Price Explorer terms, https://icapcarbonaction.com/en/terms-use-and-documentation-notes-allowance-price-explorer (via search).
31. Lamp & Samano 2022, https://ideas.repec.org/a/eee/eneeco/v107y2022ics0140988321006241.html (via search).
32. Karaduman 2021, https://ceepr.mit.edu/workingpaper/economics-of-grid-scale-energy-storage-in-wholesale-electricity-markets (via search).
33. Aalto thesis, https://aaltodoc.aalto.fi/items/69c01be5-9260-412b-9dfd-720ff64a3bf4 (403; via search).
34. Modo Energy, https://modoenergy.com/research/germany-explained-how-europes-most-liquid-power-market-really-works-for-bess (secondary).
35. Poonyth thesis, https://centaur.reading.ac.uk/73125/1/19025119_Poonyth_thesis.pdf; Modo GB reports (secondary).
