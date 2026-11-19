# Data access platforms (CDSE, Planetary Computer, Google Earth Engine, AWS, openEO)
Status: draft   Retrieved: 2026-11-12   Author: literature-scout

Scope note: all pages below were opened on 2026-11-12. Most provider docs pages show no "last updated" date; where a date is shown it is given. WebFetch summarised pages with a small model, so numbers quoted from tables should be re-checked once in the browser before they are hard-coded (flagged where it matters).

## Key facts
| # | Fact | Value | Source | Status |
|---|---|---|---|---|
| 1 | CDSE quota page lists only user type "Copernicus General Users"; no last-updated date on page | n/a | [1] | VERIFIED |
| 2 | S3/OData/STAC: requests per minute | 2000 | [1] | VERIFIED |
| 3 | S3/OData/STAC: bandwidth per connection | 20 MB/s (IAD) | [1] | VERIFIED |
| 4 | S3/OData/STAC: concurrent connections | 4 (IAD) | [1] | VERIFIED |
| 5 | S3/OData/STAC: monthly transfer limit | 12 TB, rolling 30-day window; beyond it 1 MB/s and 1 connection | [1] | VERIFIED |
| 6 | S3/OData/STAC: active sessions | 100; access token valid 10 min, refreshable within 60 min | [1] | VERIFIED |
| 7 | Sentinel Hub APIs: requests/month, requests/min | 10,000 ; 300 | [1] | VERIFIED |
| 8 | Sentinel Hub: processing units (PU)/month, PU/min | 10,000 ; 300 | [1] | VERIFIED |
| 9 | Direct HTTP access to COGs: requests per month | 50,000 (extensions via CREODIAS; "technical limitation may apply") | [1] | VERIFIED |
| 10 | openEO: credits per month | 10,000 (footnote: temporary boost, news item 3 Sep 2024; still stated on credit page today) | [1][4] | VERIFIED |
| 11 | openEO: requests/min; concurrency | 12 (sync+batch execution requests, 1 per 5 s); 2 concurrent sync, 2 concurrent batch jobs | [1][5] | VERIFIED |
| 12 | openEO credit cost | sync request fixed 7 credits; batch job 2 credits startup/storage plus memory and CPU (page example: ~1.07 credits/GB-h, ~1.64 credits/CPU-h, derived from the example; factors "set by the backend and may change") | [4] | VERIFIED (rates DERIVED) |
| 13 | openEO tested scale | "up to about 100x100 km at 10 m" per job; start with small temporal extent | [5] | VERIFIED |
| 14 | CDSE STAC endpoint | `https://stac.dataspace.copernicus.eu/v1/` (search: `/v1/search`, GET or POST); legacy `https://catalogue.dataspace.copernicus.eu/stac` deprecated 17 Nov 2025 | [2] | VERIFIED |
| 15 | CDSE STAC collection IDs | `sentinel-2-l2a`, `sentinel-1-grd` | [2] | VERIFIED |
| 16 | CDSE S3 endpoint and keys | `https://eodata.dataspace.copernicus.eu/` (alt. `https://eodata.ams.dataspace.copernicus.eu/`); keys created at `https://eodata-s3keysmanager.dataspace.copernicus.eu/` (secret shown once, expiry date chosen by user) | [6] | VERIFIED |
| 17 | Sentinel Hub auth | OAuth client (ID+secret) created in Dashboard > User Settings; `client_credentials` grant at `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`; token rate-limited (HTTP 429) | [7] | VERIFIED |
| 18 | openEO endpoints | `https://openeofed.dataspace.copernicus.eu/` (federated), `https://openeo.dataspace.copernicus.eu/` (CDSE only) | [5] | VERIFIED |
| 19 | openEO collections IDs | `SENTINEL2_L2A` (extent from 2015-06-27, open end), `SENTINEL1_GRD`, `SENTINEL1_GLOBAL_MOSAICS`, `SENTINEL2_L1C`, others; list read only partly (first 100k of 331k characters) | [8] | VERIFIED (partial list) |
| 20 | PU definition | 1 PU = 512x512 px, 3 bands, 1 sample/px, <=16 bit output, no extra processing. Min cost 0.005 PU (Process/OGC) | [3] | VERIFIED |
| 21 | PU formula | area factor = BBOX px/(512x512) (min 0.01) x bands/3 (dataMask not counted) x output factor (32-bit float TIFF 2; 8/16-bit 1) x samples/px x (data fusion factor). S1: orthorectification x2, RTC x2.5, speckle x2 | [3] | VERIFIED |
| 22 | PU cost, 64x64 px, 12 bands, 16-bit, 1 sample | 0.0156 x 4 x 1 x 1 = 0.0625 PU (0.125 PU if 32-bit float) | derived from [3] | DERIVED |
| 23 | Sentinel data legal notice | free, full, open access; reproduction, distribution, public communication, adaptation allowed; notice "Copernicus Sentinel data [Year]" / "Contains modified Copernicus Sentinel data [Year]" required when distributing or communicating; no warranty | [9] | VERIFIED |
| 24 | PC STAC API live and anonymous today | `https://planetarycomputer.microsoft.com/api/stac/v1/collections/...` returned JSON without credentials on 2026-11-12; SAS token endpoint `/api/sas/v1/token/<collection>` returned a token without credentials for `sentinel-2-l2a` and `sentinel-1-rtc` | [10][11][12][13] | VERIFIED |
| 25 | PC Hub retired 2024-06-06; maintainers: "the Planetary Computer Data and APIs will remain available and unchanged"; later note: data and API available without account or key, SAS tokens still needed for Blob access | see source | [14] | VERIFIED (maintainer comment, GitHub) |
| 26 | Planetary Computer Pro | separate Azure service for organisations' own private datasets (GeoCatalog resource, usage-based billing); not the free public catalog. Learn landing page `updated_at` 2026-06-11 | [15] | VERIFIED |
| 27 | PC `sentinel-2-l2a` | extent 2015-06-27 to open end; region `westeurope`; assets B01-B12, B8A, SCL, AOT, WVP, visual as COG (`image/tiff; application=geotiff; profile=cloud-optimized`); license `proprietary` + link to Copernicus Sentinel data terms; description text says archive "2016 to present" though extent starts 2015 | [10] | VERIFIED |
| 28 | PC `sentinel-1-grd` | extent 2014-10-10 to open end; `westeurope`; license `proprietary`; assets hh, hv, vh, vv (original GRD, not COG per metadata read) | [12] | VERIFIED |
| 29 | PC `sentinel-1-rtc` | extent 2014-10-10 to open end; license CC-BY-4.0; processed by Catalyst with PlanetDEM; `msft:requires_account: true`; assets hh,hv,vh,vv; `westeurope` | [11] | VERIFIED |
| 30 | PC SAS token | `planetary_computer.sign` / `sign_inplace` modifier for pystac-client; two JSON keys `msft:expiry`, `token`; observed expiry about 40-45 min after request (DERIVED from two observations, 2026-11-12 ~21:12 UTC request -> expiry 21:57:25Z; ~21:20 -> 22:00:00Z) | [13][16] | DERIVED |
| 31 | PC subscription key | optional; maintainer (8 Dec 2025): gives higher rate limits for SAS token requests and longer-lived SAS tokens. Key registration/developer portal appears inactive (issue comment 28 Aug 2026, unanswered) | [17] | VERIFIED (maintainer statement); key obtainability OPEN |
| 32 | PC documented numeric rate limits | none found on any official page opened | [16][17] | UNVERIFIED |
| 33 | PC processing baseline handling | official example notebook harmonizes scenes on/after 2022-01-25 by `offset = 1000` (clip at offset, subtract) for B01-B12/B8A; collection metadata read showed no offset info; a sample 2022-06-30 item had `s2:processing_baseline` 05.10 (reprocessed 2024-07-03) | [18][19] | VERIFIED (notebook); item-level offset absent per summariser, re-check |
| 34 | PC terms | "Supplemental Terms of Use for Microsoft Planetary Computer Previews", last updated January 2023; tokens may not be transferred or monetized; production use at user's risk | [20] | SECONDARY (search excerpt; page fetch returned only title) |
| 35 | GEE non-commercial eligibility | free for nonprofits, academic/educational users, individuals for "noncommercial personal use"; excluded: fee-for-service, paid deliverables, compensation for apps/data built with EE, R&D for commercial product | [21] | VERIFIED |
| 36 | GEE terms | last modified 2022-09-29; non-commercial use permitted for individuals; may use data/figures in own research publications (§2.1(d)); may not "sell, resell, sublicense, transfer, or distribute any or all of the Services" (§2.2(c)(iii)); no general attribution requirement stated | [22] | VERIFIED |
| 37 | GEE non-commercial quota tiers (effective 2026-04-27) | Community 150 EECU-h/month (verified noncommercial project); Contributor 1,000 EECU-h/month (needs active billing account, not charged for noncommercial EE use); Partner 100,000 EECU-h/month (application, climate/nature work only, several weeks review). Reset midnight Pacific on the 1st; no rollover; yearly re-verification; exceeding quota puts project in "restricted mode" (slower, not stopped); "quota farming" via many projects violates ToS | [23] | VERIFIED |
| 38 | GEE per-project defaults | 40 concurrent requests, 100 requests/s, 2 average concurrent batch tasks, 3,000 queued tasks, 250 GB / 10,000 assets storage; concurrent batch under noncommercial "determined by your tier" (no number) | [24] | VERIFIED |
| 39 | GEE collection IDs | `COPERNICUS/S2_SR_HARMONIZED` (2017-03-28 to 2026-11-11; 2017-2018 L2 "not yet global"); `COPERNICUS/S1_GRD` (2014-10-03 to 2026-11-12); `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` (2015-06-27 to 2026-11-11, bands `cs`, `cs_cdf`, CC-BY-4.0, backfill ongoing) | [25][26][27] | VERIFIED |
| 40 | GEE S2 harmonization | baseline >=04.00 shifted by 1000 after 2022-01-25; HARMONIZED collection adjusts new scenes to old range | [25] | VERIFIED |
| 41 | Earth Search STAC (Element84) | `https://earth-search.aws.element84.com/v1`; collections: `sentinel-2-l2a` (from 2015-06-27, open end), `sentinel-2-c1-l2a`, `sentinel-2-pre-c1-l2a`, `sentinel-2-l1c`, `sentinel-1-grd`, `landsat-c2-l2`, `cop-dem-glo-30/90`, `naip` | [28] | VERIFIED |
| 42 | Earth Search S1 GRD marked requester-pays | `sentinel-1-grd` flagged requester-pays true; sentinel-2-l2a has no such flag in metadata | [28] | VERIFIED |
| 43 | AWS Open Data `sentinel-cogs` | us-west-2; L2A COGs from April 2017 over wider Europe, globally Dec 2018; page does not say requester-pays; examples use `--no-sign-request` | [29] | VERIFIED (requester-pays status unstated) |
| 44 | S2 constellation | S2C launched 2024-09-05, replaced S2A operationally 2025-01-21; S2B operating; S2D not launched; 5-day revisit; swath 290 km; 10 m: B2,B3,B4,B8; 20 m: B5,B6,B7,B8a,B11,B12 | [30] | VERIFIED |
| 45 | Observed item count, Earth Search, Germany bbox 5.85,47.27,15.05,55.06, 2025-07-01..05 | numberMatched = 349 | [28b] | VERIFIED (single query) |
| 46 | Python packages (PyPI JSON, 2026-11-12) | pystac-client 0.9.1 Apache-2.0 (2026-10-20); planetary-computer 1.0.0 MIT (2023-07-05); odc-stac 0.5.3 licence field null, LICENSE file present (2026-07-30); stackstac 0.5.1 MIT (2024-08-10, README: "Don't use this in production"); openeo 0.54.0 Apache-2.0 (2026-10-28); sentinelhub 3.12.1 MIT (2026-11-06) | [31]-[36] | VERIFIED |

## Details

### 1. CDSE (Copernicus General user)
Quota table, as shown on [1] (no date on page): S3/OData/STAC 2000 req/min, 20 MB/s per connection, 4 concurrent connections, 12 TB per rolling 30 days, 100 active sessions. Sentinel Hub 10,000 requests and 10,000 PU per month, 300 requests and 300 PU per minute. openEO 10,000 credits/month, 12 execution requests/min, 2 concurrent. Direct HTTP COG access 50,000 requests/month. Footnote: after the monthly transfer limit bandwidth drops to 1 MB/s and 1 connection. Note: each S3 file is a separate request (a recursive download of a 100-file product = 100 requests) [6].

Authentication summary: STAC search pages show plain HTTPS without token (whether login is needed for search is not stated in what I read; the second part of the STAC page said nothing on auth). Downloads/OData/S3: a CDSE account is required; token via username/password (password grant, client `cdse-public`) or S3 key pair [6]. Sentinel Hub: OAuth client ID/secret [7]. openEO: OAuth (client credentials page exists, content not read); account required.

Processing unit: see facts 20-22. Arithmetic for one 64x64 px, 12-band chip (640 m at 10 m): area = 64x64 / (512x512) = 4096/262144 = 0.015625 (above the 0.01 floor); bands 12/3 = 4; output 16-bit = 1; samples 1; so PU = 0.015625 x 4 = 0.0625. Quota consequence: PU would allow 10,000/0.0625 = 160,000 chip requests per month, but the 10,000 requests/month cap binds first, so about 10,000 chip-requests per month (one request per site-month for ~3,000 sites would use 3,000 of them per month). Mosaicking that returns several samples per pixel multiplies PU by samples. 12 req/s is not an issue (300/min).

National scan on Sentinel Hub (derived): 357,000 km2 at 10 m = 3.57e9 px; /262,144 = 13,618 tiles of 512x512; x (12/3 = 4) = 54,500 PU per single-date 12-band pass, or x(4/3) = 18,200 PU for 4 bands. Both exceed the 10,000 PU monthly quota, so Sentinel Hub on the free tier cannot do a monthly national scan. [Statistical API has a 0.01 PU minimum and is the right primitive for aggregated features but the same area factor applies.]

Terms: [9] allows reproduction, distribution, adaptation, public communication of Sentinel data, requires the attribution notice quoted in fact 23, no warranty. CDSE terms [37] (no version date on page): Sentinel data "on a free, full and open basis"; Section 9 requires good faith and forbids circumventing limits with multiple accounts; other portal content "intended for non-commercial use". Forum rules prohibit automated crawling of the forum only. Fine for a public GitHub repo with aggregated results as long as the attribution notice is carried.

### 2. Microsoft Planetary Computer
Status today: the STAC API answers anonymously and the SAS token endpoint issues tokens without a key. Hub retired 2024-06-06 [14]; Planetary Computer Pro is a different, paid, bring-your-own-data Azure service [15]; the public Data Catalog and API were stated to remain available [14]. No official statement that the public API will be shut down was found, but no recent maintainer statement was found either. Registration of personal subscription keys appears to be gone (issue #464 comment dated 2026-08-28 unanswered) [17]. Anonymous access is therefore the working mode.

Open conflicts: `sentinel-1-rtc` carries `msft:requires_account: true`, yet the token endpoint returned a token anonymously on 2026-11-12; I did not test an actual RTC blob read (OPEN). RTC coverage over Germany not checked (OPEN). A GitHub-issue summary mentions HTTP 429 on collection calls (issue #415, seen only via search snippet); my own fetch of the notebook on nbviewer returned 429 from nbviewer, not PC.

Processing baseline: PC `sentinel-2-l2a` is Sen2Cor L2A as converted by Esri/Microsoft; collection metadata gives no offset note. Microsoft's own example notebook handles PB 04.00 manually: for scenes on/after 2022-01-25 subtract 1000 from B01-B12/B8A (with clipping) to match earlier scenes [18]. Treat PC data as NOT harmonized; do it per scene (or per `s2:processing_baseline`). Contrast GEE `S2_SR_HARMONIZED`, which is already harmonized [25]. CDSE STAC items declare offset -0.1 / scale 0.0001 for baseline >=04.00 per a CDSE forum post (SECONDARY, found via search).

Licence of data: Sentinel data: collection license "proprietary" with link to the Copernicus Sentinel data terms (i.e. [9]); RTC is CC-BY-4.0 (processor Catalyst). Platform terms [20] (via search excerpt only): tokens non-transferable and not to be monetized.

### 3. Google Earth Engine
Allowed for you, per [21][22]: individuals using EE for "noncommercial personal use" and for research publications; you may use data, charts, figures in research or educational publications (§2.1(d)). Not allowed: fee-for-service or paid deliverables, compensation for apps/data built with EE, R&D for a commercial product, selling/sublicensing the Services (§2.2(c)(iii)). Posting your own aggregated results and your code on GitHub is not "distributing the Services", but re-hosting raw EE-served imagery at scale is not covered by anything I read and should be avoided (judgement, UNVERIFIED). Registration: a Cloud project registered/verified as noncommercial, yearly re-verification [23]. Contributor tier needs a billing account on file (not charged for noncommercial) [23]. The Partner tier is restricted to climate mitigation/adaptation/nature protection; a BESS/solar build-out study might arguably fit but is OPEN.

Quota fit: Community 150 EECU-h/month; Contributor 1,000. A national monthly scan in EE is unlikely to fit in Community; on Contributor feasibility depends on the reducer cost and cannot be estimated without a test (OPEN). Exceeding quota puts the project in restricted mode (slower, not blocked) [23].

### 4. Other routes
Earth Search v1 (Element84) STAC: `sentinel-2-l2a` COGs in AWS us-west-2 `sentinel-cogs` [28][29]; Collection 1 IDs `sentinel-2-c1-l2a` also present. Requester-pays: not stated for S2 L2A in the pages read; S1 GRD is flagged requester-pays (needs an AWS account). Reads from a laptop in Germany go cross-region (us-west-2), so latency/throughput per request is poor compared with PC West Europe or CDSE (judgement).
CDSE openEO: collections `SENTINEL2_L2A`, `SENTINEL1_GRD`, `SENTINEL1_GLOBAL_MOSAICS` [8]; compositing processes (`reduce_dimension`, `aggregate_temporal_period`, `load_collection`, `save_result`) exist in the openEO standard but I did not open a page listing the CDSE-supported process set (OPEN). Practical limit: 2 concurrent jobs, tested to ~100x100 km per job, credits 10,000/month [1][5].

### 5. Feasibility of a national streaming scan (all DERIVED unless noted)
Tile count: Germany spans roughly UTM 31/32/33. Area bound: 357,000 km2 / (109.8 km)^2 = 357,000 / 12,056 = 29.6 tiles as a strict minimum; real count including border overlap and irregular outline is higher, probably 40-50 (UNVERIFIED; I could not obtain the tile list). Observed: Earth Search returned 349 items for the rectangular Germany bbox in 5 days (July 2025) [28b]. bbox is about 520,000 km2 incl. neighbouring countries, so Germany-only is smaller. Scaling 349 per 5 days x 73 = about 25,500 scenes/year for the bbox as an upper bound (single summer window; may include tiles with partial data). Germany-only, assume 55-70 percent: roughly 14,000-18,000 scenes/year (rough guess).
Per-scene volume (full tile 109.8 km = 10,980 px at 10 m): 10 m bands: 10,980^2 = 1.206e8 px x 4 bands x 2 bytes = 0.965 GB uncompressed. 20 m bands: 5,490^2 = 3.01e7 px x 6 bands x 2 bytes = 0.361 GB. Total about 1.33 GB uncompressed per scene (excl. SCL, AOT, WVP); deflate COG probably 40-60 percent of that (UNVERIFIED), so ~0.5-0.8 GB.
Annual streaming volume: 14,000-25,500 scenes x 0.5-1.33 GB = about 7-34 TB per year of reads if every band of every scene is read. Cloud filtering (e.g. <60 percent cloud) and reading only needed bands (e.g. B02,B03,B04,B08,B11,B12, SCL) reduce this by a factor of about 2-3. Monthly: ~0.6-2.8 TB. For the full 2017-2026 history (~9.5 years): ~70-320 TB.
Fit: CDSE S3: 12 TB per rolling 30 days and 20 MB/s x 4 connections = 80 MB/s max = ~207 TB/month theoretical at line rate, so the 12 TB cap binds: roughly one year of Germany per month of quota if band-subset and cloud-filtered; the full history would take many months. PC: no documented cap, throughput from a laptop is the limit (e.g. at 50 MB/s sustained: 12 TB/day... no: 50 MB/s x 86,400 s = 4.3 TB/day; so a year of reads in ~2-8 days of continuous running). Network speed of the laptop is the real constraint (OPEN).

### 6. Python tooling
See fact 46. `stackstac` is effectively unmaintained (last release 2024-08; README warns against production use); prefer `odc-stac` for loading STAC items into xarray, `pystac-client` for search, `planetary-computer` 1.0.0 (2023) for SAS signing, `openeo` for CDSE openEO, `sentinelhub` for Process/Statistical API.

## Comparison table
| Platform | S2 L2A | S1 GRD/RTC | Time range | Auth | Free quota | Server-side compute | (a) chips, few thousand sites | (b) national streaming scan |
|---|---|---|---|---|---|---|---|---|
| CDSE S3/STAC (COG/JP2 SAFE) | yes, `sentinel-2-l2a` | GRD `sentinel-1-grd`; no RTC | 2015-06-27 onward | account + S3 keys / token | 12 TB/30 d, 4 conn, 20 MB/s | none | good (but JP2 SAFE; partial reads harder) | feasible within 12 TB/month only if band/cloud-filtered |
| CDSE Sentinel Hub | yes | yes (GRD, ortho/RTC options) | 2015 onward | OAuth client | 10,000 PU, 10,000 req/month | yes (evalscript) | good: 0.0625 PU/chip, 10,000 req cap | no: ~54,500 PU per 12-band national pass |
| CDSE openEO | yes `SENTINEL2_L2A` | `SENTINEL1_GRD` | 2015 onward | OAuth account | 10,000 credits/month | yes (datacube, batch) | possible (7 credits/sync request) | doubtful: 2 jobs, 100x100 km tested |
| MS Planetary Computer | yes, COG, West Europe | GRD (no COG), RTC CC-BY-4.0 (account flag) | S2 2015-06-27; S1 2014-10-10 | none (anonymous SAS) | no documented limit | none | very good (COG windowed reads, same region as Europe) | best candidate; offset 1000 harmonization needed |
| GEE | `S2_SR_HARMONIZED` (2017-03-28+) | `COPERNICUS/S1_GRD` | S2 from 2017-03 | Google account + noncommercial project | 150-1000 EECU-h/month | yes | good | uncertain, test needed |
| AWS Earth Search | yes, COG, us-west-2 | GRD requester-pays | 2015-06-27 (Europe L2A from 2017-04) | none for S2 | no documented limit | none | good but cross-region | feasible, slower from Germany |

## (verify) items from KICKOFF.md
| ID | Claim in KICKOFF.md | Finding | Verdict (CONFIRMED / CORRECTED / OPEN) | Source |
|---|---|---|---|---|
| V10 | CDSE account gives STAC, openEO, Sentinel Hub and S3 access, all within free quotas | True with limits: S3/OData/STAC 12 TB/30 d, 4 conn, 20 MB/s, 2000 req/min; Sentinel Hub 10,000 PU and 10,000 req/month; openEO 10,000 credits/month. STAC search shown without a token; downloads/S3/SH/openEO need account credentials. Free quotas do not cover a national Sentinel Hub scan. | CONFIRMED (with quotas stated) | [1][2][3][6][7] |
| V11 | Planetary Computer needs no account; STAC API public; planetary-computer package fetches tokens automatically | STAC API and SAS token endpoint worked without credentials on 2026-11-12. Package 1.0.0 signs via `sign`/`sign_inplace`. Caveats: `sentinel-1-rtc` carries `msft:requires_account: true` (not tested for blob read); no numeric rate limits documented; subscription keys apparently no longer obtainable; Hub retired 2024-06-06 (Pro is a separate paid product). | CONFIRMED (RTC caveat OPEN) | [10]-[17] |
| V12 | GEE for non-commercial research; read its terms first | Free for noncommercial individuals/academics/nonprofits; no fee-for-service or paid deliverables; no reselling of the Services; research publications allowed; since 2026-04-27 monthly EECU-hour tiers (150 / 1,000 / 100,000); project verification yearly. | CONFIRMED (with the tier limits) | [21]-[24] |

## What this means for our method
- Chips (a): use Planetary Computer (COG, West Europe) or CDSE S3 as primary; Sentinel Hub is feasible for chips on PU (0.0625 PU) but the 10,000 requests/month cap limits to about 10,000 chip-requests/month; plan a monthly request budget before choosing it.
- National scan (b): Sentinel Hub and openEO free quotas are too small; use client-side streaming from PC COGs with band subsetting and cloud pre-filter from STAC metadata, aggregate on the fly, store only features. Budget ~0.6-2.8 TB/month of reads (derived).
- Harmonize PB>=04.00 (offset 1000 for scenes on/after 2022-01-25) when using PC or CDSE; do not double-apply on GEE HARMONIZED.
- Use `s2:processing_baseline` and Cloud Score+ (GEE only) or SCL for masking; note scenes in PC may be reprocessed (item with 2022 acquisition had baseline 05.10, processed 2024).
- Attribution to carry in GitHub README and outputs: "Contains modified Copernicus Sentinel data [Year]" [9]. Do not redistribute raw GEE-served imagery.
- Add a retry/backoff on 429 and re-sign SAS tokens roughly every 30 min (observed lifetime ~40-45 min, derived).

## Open questions
1. Exact MGRS tile count over Germany (derive from the ESA tiling-grid KML or a STAC query for one cloud-free day).
2. Whether `sentinel-1-rtc` blob reads work without an account and its coverage over Germany.
3. Official PC rate limits / terms (terms page only seen via search excerpt; official page fetch returned only a title).
4. Whether the CDSE 10,000-credit "temporary boost" ends; CDSE openEO process list for compositing; CDSE STAC search auth requirement.
5. Whether a private individual's research qualifies for the GEE Partner tier (not needed; Contributor suffices).
6. Whether Earth Search `sentinel-2-l2a` bucket is requester-pays (unstated; examples use `--no-sign-request`).
7. Re-check quota numbers directly in a browser (pages were summarised by a small model).

## Sources
[1] CDSE, Quotas and Limitations. https://documentation.dataspace.copernicus.eu/Quotas.html (no date shown; retrieved 2026-11-12)
[2] CDSE, STAC product catalogue. https://documentation.dataspace.copernicus.eu/APIs/STAC.html (no date; 2026-11-12)
[3] CDSE/Sentinel Hub, Processing Unit. https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/ProcessingUnit.html (no date; 2026-11-12)
[4] CDSE, openEO credit usage. https://documentation.dataspace.copernicus.eu/APIs/openEO/credit_usage.html (no date; references March 2026; 2026-11-12)
[5] CDSE, openEO. https://documentation.dataspace.copernicus.eu/APIs/openEO/openEO.html (no date; 2026-11-12)
[6] CDSE, S3 access. https://documentation.dataspace.copernicus.eu/APIs/S3.html (no date; 2026-11-12)
[7] CDSE, Sentinel Hub authentication. https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html (no date; 2026-11-12)
[8] CDSE openEO collections list. https://openeo.dataspace.copernicus.eu/openeo/1.2/collections (live; 2026-11-12; partially read)
[9] European Commission, Legal notice on the use of Copernicus Sentinel Data and Service Information. https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice (PDF, no date; 2026-11-12)
[10] PC STAC collection sentinel-2-l2a. https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a (live; 2026-11-12)
[11] PC STAC collection sentinel-1-rtc. https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-rtc (live; 2026-11-12)
[12] PC STAC collection sentinel-1-grd. https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-grd (live; 2026-11-12)
[13] PC SAS token endpoint. https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a and .../sentinel-1-rtc (live; 2026-11-12)
[14] Retiring the Hub on June 6th, 2024. https://github.com/microsoft/PlanetaryComputer/discussions/347 (announced 2024-05-21; retrieved 2026-11-12)
[15] Microsoft Planetary Computer Pro, Microsoft Learn. https://learn.microsoft.com/en-us/azure/planetary-computer (updated_at 2026-06-11; retrieved 2026-11-12)
[16] planetary-computer-sdk-for-python README. https://raw.githubusercontent.com/microsoft/planetary-computer-sdk-for-python/main/README.md (2026-11-12)
[17] Issue #464 subscription keys. https://github.com/microsoft/PlanetaryComputer/issues/464 (comments Dec 2025 and Aug 2026; 2026-11-12)
[18] PC example notebook, baseline change. https://raw.githubusercontent.com/microsoft/PlanetaryComputerExamples/main/datasets/sentinel-2-l2a/baseline-change.ipynb (2026-11-12)
[19] PC STAC search, item S2A_MSIL2A_20220630T102041_R065_T33UUU_20240703T001206. https://planetarycomputer.microsoft.com/api/stac/v1/search?collections=sentinel-2-l2a&limit=1&bbox=13.3,52.5,13.4,52.6&datetime=2022-06-01T00:00:00Z/2022-06-30T23:59:59Z (2026-11-12)
[20] Supplemental Terms of Use for Microsoft Planetary Computer Previews. https://planetarycomputer.microsoft.com/terms (last updated Jan 2023 per search excerpt; page fetch returned only title; SECONDARY)
[21] Google Earth Engine, Noncommercial use. https://earthengine.google.com/noncommercial/ (no date; 2026-11-12)
[22] Google Earth Engine Terms of Service. https://earthengine.google.com/terms/ (last modified 2022-09-29; 2026-11-12)
[23] Earth Engine noncommercial quota tiers. https://developers.google.com/earth-engine/guides/noncommercial_tiers (effective 2026-04-27; 2026-11-12)
[24] Earth Engine usage limits. https://developers.google.com/earth-engine/guides/usage (no date; 2026-11-12)
[25] GEE catalog COPERNICUS/S2_SR_HARMONIZED. https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED (2026-11-12)
[26] GEE catalog COPERNICUS/S1_GRD. https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD (2026-11-12)
[27] GEE catalog Cloud Score+. https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED (2026-11-12)
[28] Element84 Earth Search collections. https://earth-search.aws.element84.com/v1/collections (live; 2026-11-12). [28b] Search query https://earth-search.aws.element84.com/v1/search?collections=sentinel-2-l2a&bbox=5.85,47.27,15.05,55.06&datetime=2025-07-01T00:00:00Z/2025-07-05T23:59:59Z&limit=200 (numberMatched 349)
[29] Registry of Open Data on AWS, Sentinel-2 COGs. https://registry.opendata.aws/sentinel-2-l2a-cogs/ (2026-11-12)
[30] SentiWiki, S2 mission. https://sentiwiki.copernicus.eu/web/s2-mission (2026-11-12)
[31] https://pypi.org/pypi/pystac-client/json ; [32] .../planetary-computer/json ; [33] .../odc-stac/json ; [34] .../stackstac/json ; [35] .../openeo/json ; [36] .../sentinelhub/json (all 2026-11-12)
[37] CDSE Terms and Conditions. https://dataspace.copernicus.eu/terms-and-conditions (no version date; 2026-11-12)
Secondary: CDSE forum post on PB04.00 offset in CDSE STAC (found via search, https://forum.dataspace.copernicus.eu/t/sentinel-2-baseline-04-00-offset-csde-stac-derived-ndvi-doesnt-match-copernicus-browser-ndvi/5417), not opened.


## Addendum 2026-11-18: Sentinel Hub quota reset (imagery engineer)

The Sentinel Hub requests and processing units are **calendar-month** quotas. CDSE Quotas and Limitations page
(https://documentation.dataspace.copernicus.eu/Quotas.html, read 2026-11-18): "The following limitations and quotas
are monthly and reset on the first day of every month", listing requests per month and PU per month. The rolling
30-day window applies only to the S3/OData/STAC transfer limit (12 TB). So November use counts until 2026-11-30 and
the quota starts again on 2026-12-01 (reset time of day not stated). The account quota endpoint was not queried.
