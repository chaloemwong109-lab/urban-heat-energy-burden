"""
What this does
--------------
Integrates the cleaned temperature and electricity data into analysis-ready Gold tables.

  1. Spatial join (GeoPandas)
     MEA district points  --sjoin_nearest-->  temperature stations / grid cells
     Each district gets the station that represents its heat exposure, plus the
     distance to it (so we can see how representative the temperature value is).

  2. Temporal harmonisation (DuckDB SQL)
     Daily temperature -> monthly and yearly heat features:
       mean temperature, hottest month, hot days (daily mean >= 30 C),
       cooling degree days (CDD, base 24 C) and data completeness.

  3. Integration (DuckDB SQL)
     Yearly electricity per district  JOIN  district dimension (spatial key)
                                      JOIN  yearly heat features (station_id + year)
     plus derived indicators: YoY change, index vs. first year, share of total,
     and a COVID-period flag (2020-2021) to help the analyst control for that shock.

  4. Integration checks — the run fails if keys don't match, rows are lost or
     duplicated, or required metrics are null. Results go to logs/transform.log.

Outputs (data/gold/)
--------------------
  dim_district.parquet / .geojson        district dimension + nearest station
  agg_temperature_monthly.parquet        station x year x month heat features
  agg_temperature_yearly.parquet         station x year heat features
  fact_district_energy_heat_yearly.parquet   main fact table (district x year)
  agg_year_energy_heat.parquet           city-wide total per year + heat features

Query example (DuckDB):
  SELECT * FROM 'data/gold/fact_district_energy_heat_yearly.parquet' LIMIT 5;
"""

import logging
import sys
import unicodedata
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

# ---------------------------------------------------------------------------
# Paths & parameters
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
BRONZE_DIR = BASE_DIR / "data" / "bronze"
SILVER_DIR = BASE_DIR / "data" / "silver"
GOLD_DIR = BASE_DIR / "data" / "gold"
LOG_DIR = BASE_DIR / "logs"
GOLD_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

SILVER_TEMP = SILVER_DIR / "clean_temperature.parquet"
SILVER_ELEC = SILVER_DIR / "clean_electricity.parquet"
REF_DISTRICTS = BRONZE_DIR / "ref_mea_districts.csv"
REF_STATIONS = BRONZE_DIR / "ref_temperature_stations.csv"

CRS_WGS84 = "EPSG:4326"
CRS_UTM47N = "EPSG:32647"   # metric CRS for Bangkok -> distances in metres
HOT_DAY_C = 30.0            # a "hot day" = daily mean temperature >= 30 C
CDD_BASE_C = 24.0           # cooling-degree-day base temperature for a tropical city
MIN_COMPLETENESS = 0.95     # a year/month needs >= 95% of its days to be used
COVID_YEARS = (2020, 2021)
BKK_BBOX = {"lat": (13.3, 14.3), "lon": (100.1, 101.1)}  # sanity box for coordinates

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "transform.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Transform")


class IntegrationError(Exception):
    """Raised when an integration check fails (keys, row counts, nulls)."""


def check(condition: bool, message: str) -> None:
    if not condition:
        logger.error(f"[CHECK FAILED] {message}")
        raise IntegrationError(message)
    logger.info(f"[CHECK PASSED] {message}")


def normalise_name(s: pd.Series) -> pd.Series:
    """Thai text can have the same visible name with different code points -> NFC + strip."""
    return s.astype(str).map(lambda x: unicodedata.normalize("NFC", x).strip())


# ---------------------------------------------------------------------------
# Step 1 — load inputs
# ---------------------------------------------------------------------------
def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    for p in (SILVER_TEMP, SILVER_ELEC, REF_DISTRICTS, REF_STATIONS):
        if not p.exists():
            raise FileNotFoundError(f"Missing input: {p.relative_to(BASE_DIR)} "
                                    "(run 01_ingest.py and 02_validate_clean.py first)")

    districts = pd.read_csv(REF_DISTRICTS, encoding="utf-8")
    stations = pd.read_csv(REF_STATIONS, encoding="utf-8")
    districts["district"] = normalise_name(districts["district"])

    # Reference tables skip 02 (they are tiny, curated lookups), so check them here.
    check(districts["district"].is_unique, f"district reference has unique names ({len(districts)} districts)")
    check(stations["station_id"].is_unique, f"station reference has unique ids ({len(stations)} station(s))")
    for name, df in (("district", districts), ("station", stations)):
        ok = (df["lat"].between(*BKK_BBOX["lat"]) & df["lon"].between(*BKK_BBOX["lon"])).all()
        check(bool(ok), f"all {name} coordinates are inside the Bangkok-metro bounding box")
    return districts, stations


# ---------------------------------------------------------------------------
# Step 2 — spatial join: district -> nearest temperature station (GeoPandas)
# ---------------------------------------------------------------------------
def build_dim_district(districts: pd.DataFrame, stations: pd.DataFrame) -> gpd.GeoDataFrame:
    logger.info("--- [Spatial] district -> nearest temperature station (sjoin_nearest) ---")
    g_d = gpd.GeoDataFrame(
        districts, geometry=gpd.points_from_xy(districts["lon"], districts["lat"]), crs=CRS_WGS84
    ).to_crs(CRS_UTM47N)
    g_s = gpd.GeoDataFrame(
        stations[["station_id", "station_name", "lat", "lon"]].rename(
            columns={"lat": "station_lat", "lon": "station_lon"}),
        geometry=gpd.points_from_xy(stations["lon"], stations["lat"]), crs=CRS_WGS84,
    ).to_crs(CRS_UTM47N)

    joined = gpd.sjoin_nearest(g_d, g_s, how="left", distance_col="distance_m")
    # equal-distance ties would duplicate a district -> keep the first (lowest station_id)
    joined = (joined.sort_values(["district", "station_id"])
                    .drop_duplicates("district", keep="first")
                    .drop(columns=["index_right"]))
    joined["distance_km"] = (joined["distance_m"] / 1000).round(2)
    joined = joined.drop(columns=["distance_m"]).to_crs(CRS_WGS84)

    check(joined["station_id"].notna().all(), "every district is linked to a temperature station")
    logger.info(f"    district->station distance: min {joined['distance_km'].min()} km, "
                f"median {joined['distance_km'].median():.2f} km, max {joined['distance_km'].max()} km")
    cols = ["district", "district_en", "former_name", "province", "lat", "lon",
            "station_id", "station_name", "distance_km", "geometry"]
    return joined[cols].sort_values("district_en").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 3 — temporal harmonisation: daily -> monthly / yearly heat features (DuckDB)
# ---------------------------------------------------------------------------
def build_temperature_aggregates(con: duckdb.DuckDBPyConnection, stations: pd.DataFrame) -> None:
    logger.info("--- [Temporal] daily temperature -> monthly & yearly heat features ---")
    cols = con.execute(f"SELECT * FROM read_parquet('{SILVER_TEMP}') LIMIT 0").df().columns
    if "station_id" in cols:
        station_expr = "station_id"
    elif len(stations) == 1:
        # Checkpoint data has one Bangkok series -> tag it with the only station id
        station_expr = f"'{stations['station_id'].iloc[0]}'"
    else:
        raise IntegrationError("Silver temperature has no station_id but there are several stations")

    con.execute(f"""
        CREATE OR REPLACE TABLE temp_daily AS
        SELECT {station_expr} AS station_id,
               CAST(date AS DATE) AS date,
               CAST(year AS INTEGER) AS year,
               CAST(month AS INTEGER) AS month,
               avg_temp
        FROM read_parquet('{SILVER_TEMP}')
        WHERE avg_temp IS NOT NULL
    """)
    dupes = con.execute("""SELECT COUNT(*) FROM (SELECT station_id, date FROM temp_daily
                           GROUP BY ALL HAVING COUNT(*) > 1)""").fetchone()[0]
    check(dupes == 0, "temperature has one row per station per day")

    con.execute(f"""
        CREATE OR REPLACE TABLE agg_temperature_monthly AS
        SELECT station_id, year, month,
               COUNT(*)                                             AS n_days,
               day(last_day(make_date(year, month, 1)))             AS days_in_month,
               ROUND(COUNT(*) / day(last_day(make_date(year, month, 1))), 3) AS completeness,
               ROUND(COUNT(*) / day(last_day(make_date(year, month, 1))), 3)
                   >= {MIN_COMPLETENESS}                            AS is_complete_month,
               ROUND(AVG(avg_temp), 2)                              AS mean_temp_c,
               MAX(avg_temp)                                        AS max_daily_mean_c,
               CAST(SUM(CASE WHEN avg_temp >= {HOT_DAY_C} THEN 1 ELSE 0 END) AS INTEGER) AS hot_days,
               ROUND(SUM(GREATEST(avg_temp - {CDD_BASE_C}, 0)), 1)  AS cdd
        FROM temp_daily
        GROUP BY station_id, year, month
        ORDER BY station_id, year, month
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE agg_temperature_yearly AS
        WITH y AS (
            SELECT station_id, year,
                   COUNT(*)                                              AS n_days,
                   CASE WHEN (year % 4 = 0 AND year % 100 <> 0) OR year % 400 = 0
                        THEN 366 ELSE 365 END                            AS days_in_year,
                   ROUND(AVG(avg_temp), 2)                               AS mean_temp_c,
                   CAST(SUM(CASE WHEN avg_temp >= {HOT_DAY_C} THEN 1 ELSE 0 END) AS INTEGER) AS hot_days,
                   ROUND(SUM(GREATEST(avg_temp - {CDD_BASE_C}, 0)), 1)   AS cdd
            FROM temp_daily GROUP BY station_id, year
        ),
        m AS (
            SELECT station_id, year, MAX(mean_temp_c) AS hottest_month_mean_c
            FROM agg_temperature_monthly GROUP BY station_id, year
        )
        SELECT y.station_id, y.year, y.n_days, y.days_in_year,
               ROUND(y.n_days / y.days_in_year, 3)                    AS completeness,
               ROUND(y.n_days / y.days_in_year, 3) >= {MIN_COMPLETENESS} AS is_complete_year,
               y.mean_temp_c, m.hottest_month_mean_c, y.hot_days, y.cdd
        FROM y JOIN m USING (station_id, year)
        ORDER BY station_id, year
    """)
    incomplete = con.execute(
        "SELECT list(year) FROM agg_temperature_yearly WHERE NOT is_complete_year").fetchone()[0]
    logger.info(f"    years with < {MIN_COMPLETENESS:.0%} temperature coverage (excluded from fact): {incomplete}")


# ---------------------------------------------------------------------------
# Step 4 — integration: electricity x district x heat (DuckDB)
# ---------------------------------------------------------------------------
def build_fact(con: duckdb.DuckDBPyConnection) -> None:
    logger.info("--- [Integration] electricity x district dimension x yearly heat ---")
    elec = con.execute(f"SELECT * FROM read_parquet('{SILVER_ELEC}')").df()
    elec["district"] = normalise_name(elec["district"])
    con.register("elec_df", elec)
    con.execute("""CREATE OR REPLACE TABLE elec AS
                   SELECT CAST(year AS INTEGER) AS year, district,
                          CAST(consumption_million_kwh AS DOUBLE) AS consumption_million_kwh
                   FROM elec_df""")

    # Key check 1: every electricity district must exist in the dimension
    unmatched = con.execute("""SELECT list(DISTINCT e.district) FROM elec e
                               ANTI JOIN dim_district d USING (district)""").fetchone()[0]
    check(not unmatched, f"all electricity districts match the district dimension (unmatched: {unmatched or 'none'})")

    dupes = con.execute("""SELECT COUNT(*) FROM (SELECT year, district FROM elec
                           GROUP BY ALL HAVING COUNT(*) > 1)""").fetchone()[0]
    check(dupes == 0, "electricity has one row per district per year")

    con.execute(f"""
        CREATE OR REPLACE TABLE fact_district_energy_heat_yearly AS
        SELECT
            e.year,
            e.year + 543                                         AS year_be,
            d.district, d.district_en, d.province,
            d.station_id, d.distance_km                          AS station_distance_km,
            e.consumption_million_kwh,
            ROUND(100.0 * (e.consumption_million_kwh
                  / LAG(e.consumption_million_kwh) OVER w - 1), 2)  AS yoy_change_pct,
            ROUND(100.0 * e.consumption_million_kwh
                  / FIRST_VALUE(e.consumption_million_kwh) OVER w, 2) AS index_first_year_100,
            ROUND(100.0 * e.consumption_million_kwh
                  / SUM(e.consumption_million_kwh) OVER (PARTITION BY e.year), 2) AS share_of_total_pct,
            t.mean_temp_c, t.hottest_month_mean_c, t.hot_days, t.cdd,
            t.completeness                                       AS temp_completeness,
            e.year IN {COVID_YEARS}                              AS covid_period
        FROM elec e
        JOIN dim_district d            USING (district)
        JOIN agg_temperature_yearly t  ON t.station_id = d.station_id
                                      AND t.year = e.year
                                      AND t.is_complete_year
        WINDOW w AS (PARTITION BY e.district ORDER BY e.year)
        ORDER BY d.district_en, e.year
    """)

    # Key check 2: rows are not lost or duplicated by the joins
    expected = con.execute("""SELECT COUNT(*) FROM elec e JOIN dim_district d USING (district)
                              JOIN agg_temperature_yearly t ON t.station_id = d.station_id
                               AND t.year = e.year AND t.is_complete_year""").fetchone()[0]
    n_elec = con.execute("SELECT COUNT(*) FROM elec").fetchone()[0]
    n_fact = con.execute("SELECT COUNT(*) FROM fact_district_energy_heat_yearly").fetchone()[0]
    check(n_fact == expected, f"fact row count = joinable electricity rows ({n_fact}/{n_elec})")
    dropped = con.execute("""SELECT list(DISTINCT year ORDER BY year) FROM elec WHERE year NOT IN
                             (SELECT year FROM fact_district_energy_heat_yearly)""").fetchone()[0]
    if dropped:
        logger.warning(f"    electricity years without complete temperature (dropped): {dropped}")

    # Key check 3: required metrics are present
    nulls = con.execute("""SELECT COUNT(*) FROM fact_district_energy_heat_yearly
                           WHERE consumption_million_kwh IS NULL OR mean_temp_c IS NULL
                              OR cdd IS NULL OR station_id IS NULL""").fetchone()[0]
    check(nulls == 0, "no nulls in key metrics (consumption, mean_temp_c, cdd, station_id)")

    con.execute("""
        CREATE OR REPLACE TABLE agg_year_energy_heat AS
        SELECT year, year_be,
               COUNT(*)                                       AS n_districts,
               ROUND(SUM(consumption_million_kwh), 2)         AS total_consumption_million_kwh,
               ANY_VALUE(mean_temp_c)                         AS mean_temp_c,
               ANY_VALUE(hottest_month_mean_c)                AS hottest_month_mean_c,
               ANY_VALUE(hot_days)                            AS hot_days,
               ANY_VALUE(cdd)                                 AS cdd,
               ANY_VALUE(covid_period)                        AS covid_period
        FROM fact_district_energy_heat_yearly
        GROUP BY year, year_be
        ORDER BY year
    """)
    con.execute("""
        CREATE OR REPLACE TABLE agg_year_energy_heat AS
        SELECT *, ROUND(100.0 * (total_consumption_million_kwh
                    / LAG(total_consumption_million_kwh) OVER (ORDER BY year) - 1), 2) AS yoy_change_pct
        FROM agg_year_energy_heat ORDER BY year
    """)


# ---------------------------------------------------------------------------
# Step 5 — write Gold zone
# ---------------------------------------------------------------------------
def export_table(con: duckdb.DuckDBPyConnection, table: str) -> None:
    out = GOLD_DIR / f"{table}.parquet"
    con.execute(f"COPY {table} TO '{out}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    logger.info(f"    saved {out.relative_to(BASE_DIR)} ({n} rows)")


def log_preview(con: duckdb.DuckDBPyConnection) -> None:
    """A first look at the hypothesis (heat -> electricity use). Full analysis is in the notebook."""
    r_all, r_nocovid, n = con.execute("""
        SELECT ROUND(corr(cdd, total_consumption_million_kwh), 3),
               ROUND(corr(cdd, total_consumption_million_kwh) FILTER (WHERE NOT covid_period), 3),
               COUNT(*)
        FROM agg_year_energy_heat
    """).fetchone()
    logger.info(f"    PREVIEW Pearson r(CDD, total consumption) = {r_all} (n={n} years); "
                f"excluding COVID years = {r_nocovid}  -- small n, indicative only")


def main() -> int:
    logger.info("=== Starting Transformation & Integration (Silver -> Gold) ===")
    try:
        districts, stations = load_inputs()
        dim = build_dim_district(districts, stations)

        con = duckdb.connect()  # in-process, in-memory: Parquet files are the storage
        dim_df = pd.DataFrame(dim.drop(columns="geometry"))
        con.register("dim_df", dim_df)
        con.execute("CREATE OR REPLACE TABLE dim_district AS SELECT * FROM dim_df")

        build_temperature_aggregates(con, stations)
        build_fact(con)

        logger.info("--- [Gold] writing outputs ---")
        for table in ("dim_district", "agg_temperature_monthly", "agg_temperature_yearly",
                      "fact_district_energy_heat_yearly", "agg_year_energy_heat"):
            export_table(con, table)
        geojson = GOLD_DIR / "dim_district.geojson"
        dim.to_file(geojson, driver="GeoJSON")
        logger.info(f"    saved {geojson.relative_to(BASE_DIR)} (for maps)")

        log_preview(con)
        con.close()
    except Exception as exc:
        logger.error(f"=== Transformation FAILED: {exc} ===\n")
        return 1

    logger.info("=== Transformation Stage Finished Successfully ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
