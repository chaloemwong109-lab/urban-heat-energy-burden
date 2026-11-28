-- Q1: housing characteristics vs heat-related health impacts (household star schema)
SELECT 'roof_material' AS feature, h.roof_material AS category,
       COUNT(*) AS households,
       ROUND(AVG(f.health_impact_count), 2)        AS avg_health_symptoms_0_3,
       ROUND(100.0 * AVG(f.impact_insomnia), 1)    AS pct_insomnia,
       ROUND(100.0 * AVG(f.impact_headache_fatigue), 1) AS pct_headache_fatigue
FROM fact_household_energy_heat f JOIN dim_household_housing h USING (household_code)
GROUP BY h.roof_material
UNION ALL
SELECT 'ventilation_quality', h.ventilation_quality, COUNT(*),
       ROUND(AVG(f.health_impact_count), 2), ROUND(100.0 * AVG(f.impact_insomnia), 1),
       ROUND(100.0 * AVG(f.impact_headache_fatigue), 1)
FROM fact_household_energy_heat f JOIN dim_household_housing h USING (household_code)
GROUP BY h.ventilation_quality
UNION ALL
SELECT 'surrounding_shade', h.surrounding_shade, COUNT(*),
       ROUND(AVG(f.health_impact_count), 2), ROUND(100.0 * AVG(f.impact_insomnia), 1),
       ROUND(100.0 * AVG(f.impact_headache_fatigue), 1)
FROM fact_household_energy_heat f JOIN dim_household_housing h USING (household_code)
GROUP BY h.surrounding_shade
ORDER BY feature, avg_health_symptoms_0_3 DESC
