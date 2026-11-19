# Note on sentinelhub_cost_estimate.csv

Reset rule: Sentinel Hub requests and PU reset on the first day of each calendar month (CDSE Quotas and Limitations,
https://documentation.dataspace.copernicus.eu/Quotas.html, read 2026-11-18); only the S3/OData/STAC transfer limit is a
rolling 30-day window. The counts in the CSV ("used this month") are therefore November counts, and December starts at zero.
Plan agreed with the author: Sentinel-1 for all 150 chips in November (`make chips-s1`), Sentinel-2 in December (`make chips-s2`).
