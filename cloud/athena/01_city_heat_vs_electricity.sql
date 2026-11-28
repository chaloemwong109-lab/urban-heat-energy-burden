-- City-level context: hotter years (CDD) vs total MEA electricity sold, 2016-2025
SELECT year, year_be, total_consumption_million_kwh, cdd, hot_days, mean_temp_c, covid_period
FROM agg_year_energy_heat
ORDER BY year
