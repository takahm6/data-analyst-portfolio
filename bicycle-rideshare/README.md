# Cyclistic Bike-Share Case Study

**How do annual members and casual riders use Cyclistic bikes differently?**

This is my capstone for the Google Data Analytics Professional Certificate. Cyclistic is a fictional company, but the data is real: every Divvy bike-share ride in Chicago in 2025, about 5.5 million trips. I cleaned and analyzed the full year in Python, added daily temperature data and OpenStreetMap points of interest, and built an interactive station map in Tableau Public to show where casual riders concentrate.

**Author:** Makiko Tsuda · **Last updated:** October 2026 · **Data:** Divvy trips, January–December 2025

## Key findings

- **Casual riders use the bikes far more than ride counts suggest.** They take 35.5% of rides but 47.3% of total riding time. Their average ride is 19.9 minutes, compared with 12.2 for members.
- **Casual riding is seasonal.** Casual rides grow 14 times from January to August (members: 4 times). From June to August, casual riders account for more riding time than members.
- **Members commute; casual riders ride for leisure.** Members peak Tuesday to Thursday at 8am and 5pm. Casual riders peak on Saturday, when they take 47% of all rides.
- **Casual riders gather at the lakefront and major attractions.** Stations at Navy Pier, Millennium Park and Shedd Aquarium are 70–80% casual. Busy stations within 300 m of a notable attraction are 41% casual, compared with 34% for those farther away.

## Recommendations

1. Launch a **seasonal summer membership**, promoted from April, with a credit toward the annual plan in September.
2. Build membership benefits around **longer leisure rides**, and promote them on weekends.
3. Target **lakefront and attraction stations** with on-site promotions and partner discounts.

## Notebooks

| Notebook | What it covers |
|---|---|
| [01_prepare_and_clean.ipynb](notebooks/01_prepare_and_clean.ipynb) | Data sources, ROCCC check, cleaning log (5.55M → 5.4M rides), temperature and points-of-interest preparation |
| [02_analysis.ipynb](notebooks/02_analysis.ipynb) | Analysis, charts, station map, summary, recommendations and limitations |

**Interactive map:** [Chicago Bike-Share Station Map on Tableau Public](https://public.tableau.com/app/profile/makiko.tsuda/viz/ChicagoBike-ShareStationMap/BikeStationsandPointsofInterest)

<img src="output/Stations%20and%20attractions.png" width="70%" alt="Station map: casual riders concentrate at lakefront and attraction stations">

## Tools

Python (pandas, matplotlib, geopandas) in Jupyter Notebook, and Tableau Public for the map. I chose Python because 5.5 million rows is well beyond Excel's 1-million-row limit, and code keeps every cleaning step repeatable.

## Data sources

- **Trips:** [Divvy trip data](https://divvy-tripdata.s3.amazonaws.com/index.html), published by Motivate International Inc. under the [Divvy Data License Agreement](https://divvybikes.com/data-license-agreement).
- **Weather:** [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api).
- **Points of interest and Metra stations:** © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL), downloaded through Overpass Turbo.

## Folder structure

```
bicycle-rideshare/
├── notebooks/   01_prepare_and_clean.ipynb, 02_analysis.ipynb
├── processed/   small cleaned tables used by the analysis and the map
├── output/      map image
└── raw/         monthly trip files (not included; see below)
```

## How to reproduce

1. Download the 12 monthly files for 2025 from the [Divvy trip data index](https://divvy-tripdata.s3.amazonaws.com/index.html), unzip them, and put the CSVs in `raw/`.
2. Run `01_prepare_and_clean.ipynb` from top to bottom. It creates `processed/rides_2025_clean.parquet` (about 280 MB, so it isn't stored in this repository).
3. Run `02_analysis.ipynb`.

Requires Python 3 with pandas, numpy, matplotlib, pyarrow and geopandas.
