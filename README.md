# Carvana_summary

Script to assist in comparison shopping on the Carvana website.

Fetches, via the Carvana API, details for a list of vehicles in `carvana_ids.txt`, gathering information on year, make, model, and trim as well as vin, mileage, features, and imperfections and creates a CSV file summarizing them all, filtering out common and uninteresting features, and pritorizing other features according to the ranking in `feature_priority.txt`

As you browse the Carvana website, add the vehilce ID (the Carvana one in the URL, not the VIN) to the `carvana_ids.txt` file.  Rerun to generate a new CSV, results older than an hour a refreshed.


## Usage

```
% python3 carvana_compare.py
```
