# Results Directory

This directory contains analysis outputs comparing AI-controlled vs. baseline simulations.

## Generated Files

After running `analyze_results.py`, you'll find:

### 1. energy_comparison.png
Visualization showing:
- Cumulative energy consumption over time (AI vs. baseline)
- Instantaneous HVAC power demand
- Peak demand comparison

### 2. comfort_analysis.png
Visualization showing:
- Zone temperature over time with comfort bounds
- PMV (Predicted Mean Vote) thermal comfort metric
- Heating and cooling setpoint adjustments by AI

### 3. savings_summary.csv
Quantitative metrics table:
- Total energy consumption (kWh)
- Peak power demand (kW)
- Comfort performance (% time in comfort range)
- Average temperature and PMV
- Setpoint statistics

## Typical Results

A successful AI control strategy typically achieves:
- **Energy savings**: 5-15% reduction vs. fixed setpoints
- **Peak demand reduction**: 10-20% lower peaks
- **Comfort maintenance**: ≥90% time within comfort bounds
- **Adaptive behavior**: Setpoints widen during comfortable periods, tighten during stress

## Interpreting Results

**Good AI Performance**:
- Lower cumulative energy curve (AI below baseline)
- Similar or better comfort percentage
- Smoother power profile (fewer spikes)
- Evidence of adaptive setpoints in response to conditions

**Areas for Improvement**:
- If energy savings < 5%: Increase LLM call frequency or improve prompt
- If comfort < baseline: Tighten comfort bounds in system prompt
- If erratic control: Reduce temperature change increments, add smoothing

## Example Interpretation

```csv
metric,baseline,ai_controlled,improvement
total_energy_kwh,156.3,142.1,+9.1%
peak_power_kw,8.4,7.2,+14.3%
comfort_time_pct,89.2,91.5,+2.6%
```

This shows the AI achieved 9% energy savings, 14% peak reduction, and slightly better comfort than fixed setpoints.
