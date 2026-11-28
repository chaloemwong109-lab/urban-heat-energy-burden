-- Pearson r between yearly CDD and total electricity, with and without COVID years
SELECT
  ROUND(CORR(cdd, total_consumption_million_kwh), 3)                                AS r_all_years,
  COUNT(*)                                                                          AS n_years,
  ROUND(CORR(cdd, total_consumption_million_kwh) FILTER (WHERE NOT covid_period), 3) AS r_excl_covid,
  COUNT(*) FILTER (WHERE NOT covid_period)                                          AS n_years_excl_covid
FROM agg_year_energy_heat
