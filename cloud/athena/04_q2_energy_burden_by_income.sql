-- Q2: summer energy burden (electricity bill / income, %) and coping limits by income band
SELECT s.monthly_income_range,
       COUNT(*)                                                   AS households,
       ROUND(AVG(f.est_monthly_income_thb), 0)                    AS est_income_thb,
       ROUND(AVG(f.est_summer_elec_thb), 0)                       AS avg_summer_bill_thb,
       ROUND(AVG(f.summer_energy_burden_pct), 1)                  AS avg_burden_pct,
       ROUND(APPROX_PERCENTILE(f.summer_energy_burden_pct, 0.5), 1) AS median_burden_pct,
       ROUND(100.0 * AVG(CASE WHEN f.summer_energy_burden_pct > 10 THEN 1 ELSE 0 END), 1) AS pct_burden_over_10,
       ROUND(100.0 * AVG(CASE WHEN s.reduced_elec_due_to_cost = 'เคย' THEN 1 ELSE 0 END), 1) AS pct_cut_electricity_for_cost,
       ROUND(100.0 * AVG(s.has_ac), 1)                            AS pct_has_ac,
       ROUND(100.0 * AVG(s.barrier_no_budget), 1)                 AS pct_barrier_no_budget
FROM fact_household_energy_heat f JOIN dim_household_socioeconomic s USING (household_code)
GROUP BY s.monthly_income_range
ORDER BY est_income_thb
