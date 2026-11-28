-- Integrity check: row counts in the cloud catalog must match the local pipeline
SELECT 'fact_district_energy_heat_yearly' AS table_name, COUNT(*) AS n_rows FROM fact_district_energy_heat_yearly
UNION ALL SELECT 'agg_year_energy_heat',        COUNT(*) FROM agg_year_energy_heat
UNION ALL SELECT 'agg_temperature_monthly',     COUNT(*) FROM agg_temperature_monthly
UNION ALL SELECT 'agg_temperature_yearly',      COUNT(*) FROM agg_temperature_yearly
UNION ALL SELECT 'dim_district',                COUNT(*) FROM dim_district
UNION ALL SELECT 'fact_household_energy_heat',  COUNT(*) FROM fact_household_energy_heat
UNION ALL SELECT 'dim_household_housing',       COUNT(*) FROM dim_household_housing
UNION ALL SELECT 'dim_household_socioeconomic', COUNT(*) FROM dim_household_socioeconomic
UNION ALL SELECT 'clean_household_survey',      COUNT(*) FROM clean_household_survey
UNION ALL SELECT 'clean_temperature',           COUNT(*) FROM clean_temperature
UNION ALL SELECT 'clean_electricity',           COUNT(*) FROM clean_electricity
ORDER BY table_name
