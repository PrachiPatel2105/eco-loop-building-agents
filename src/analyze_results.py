"""
Analysis script: Compare AI-controlled vs baseline runs and generate dashboard.

Creates visualizations and CSV summary of energy savings and comfort performance.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import sys

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np
except ImportError:
    print("❌ Missing dependencies. Run: pip install pandas matplotlib seaborn numpy")
    sys.exit(1)


# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)


def load_run_data(log_file: str) -> Tuple[Dict, pd.DataFrame]:
    """
    Load run log file and convert to DataFrame.
    
    Returns:
        (run_info_dict, dataframe_of_timesteps)
    """
    with open(log_file, 'r') as f:
        data = json.load(f)
    
    run_info = data.get("run_info", {})
    log_entries = data.get("log_entries", [])
    
    # Flatten log entries into rows
    rows = []
    for entry in log_entries:
        base_row = {
            "timestamp": entry.get("timestamp", ""),
            "sim_time_hours": entry.get("sim_time_hours", 0),
            "outdoor_temp_c": entry.get("outdoor_temp_c", 0),
            "llm_called": entry.get("llm_called", False),
            "control_type": entry.get("control_type", "ai")
        }
        
        # Extract zone data
        zones = entry.get("zones", {})
        for zone_name, zone_data in zones.items():
            row = base_row.copy()
            row["zone"] = zone_name
            row["temperature_c"] = zone_data.get("temperature_c", 0)
            row["cooling_setpoint_c"] = zone_data.get("cooling_setpoint_c", 0)
            row["heating_setpoint_c"] = zone_data.get("heating_setpoint_c", 0)
            row["hvac_power_kw"] = zone_data.get("hvac_power_kw", 0)
            row["pmv"] = zone_data.get("pmv", 0)
            rows.append(row)
    
    df = pd.DataFrame(rows)
    return run_info, df


def calculate_metrics(df: pd.DataFrame, comfort_temp_range: Tuple[float, float] = (20, 24),
                     comfort_pmv_range: Tuple[float, float] = (-0.5, 0.5)) -> Dict:
    """Calculate performance metrics from DataFrame."""
    
    # Energy metrics
    total_energy_kwh = df["hvac_power_kw"].sum() * (df["sim_time_hours"].max() / len(df))
    peak_power_kw = df["hvac_power_kw"].max()
    avg_power_kw = df["hvac_power_kw"].mean()
    
    # Comfort metrics
    temp_in_range = df[(df["temperature_c"] >= comfort_temp_range[0]) & 
                       (df["temperature_c"] <= comfort_temp_range[1])]
    comfort_time_pct = (len(temp_in_range) / len(df)) * 100 if len(df) > 0 else 0
    
    pmv_in_range = df[(df["pmv"] >= comfort_pmv_range[0]) & 
                      (df["pmv"] <= comfort_pmv_range[1])]
    pmv_comfort_pct = (len(pmv_in_range) / len(df)) * 100 if len(df) > 0 else 0
    
    avg_temp = df["temperature_c"].mean()
    avg_pmv = df["pmv"].mean()
    
    # Setpoint metrics
    avg_cooling_sp = df["cooling_setpoint_c"].mean()
    avg_heating_sp = df["heating_setpoint_c"].mean()
    cooling_sp_std = df["cooling_setpoint_c"].std()
    heating_sp_std = df["heating_setpoint_c"].std()
    
    return {
        "total_energy_kwh": total_energy_kwh,
        "peak_power_kw": peak_power_kw,
        "avg_power_kw": avg_power_kw,
        "comfort_time_pct": comfort_time_pct,
        "pmv_comfort_pct": pmv_comfort_pct,
        "avg_temperature_c": avg_temp,
        "avg_pmv": avg_pmv,
        "avg_cooling_setpoint_c": avg_cooling_sp,
        "avg_heating_setpoint_c": avg_heating_sp,
        "cooling_setpoint_std": cooling_sp_std,
        "heating_setpoint_std": heating_sp_std
    }


def plot_energy_comparison(df_baseline: pd.DataFrame, df_ai: pd.DataFrame, output_dir: Path):
    """Create energy consumption comparison plots."""
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Cumulative energy plot
    ax = axes[0]
    baseline_cumsum = df_baseline.groupby("sim_time_hours")["hvac_power_kw"].sum().cumsum()
    ai_cumsum = df_ai.groupby("sim_time_hours")["hvac_power_kw"].sum().cumsum()
    
    ax.plot(baseline_cumsum.index, baseline_cumsum.values, label="Baseline (Fixed)", linewidth=2)
    ax.plot(ai_cumsum.index, ai_cumsum.values, label="AI Controlled", linewidth=2)
    ax.set_xlabel("Simulation Time (hours)")
    ax.set_ylabel("Cumulative Energy (kWh)")
    ax.set_title("Cumulative Energy Consumption Comparison")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Instantaneous power plot
    ax = axes[1]
    baseline_power = df_baseline.groupby("sim_time_hours")["hvac_power_kw"].sum()
    ai_power = df_ai.groupby("sim_time_hours")["hvac_power_kw"].sum()
    
    ax.plot(baseline_power.index, baseline_power.values, label="Baseline (Fixed)", alpha=0.7)
    ax.plot(ai_power.index, ai_power.values, label="AI Controlled", alpha=0.7)
    ax.set_xlabel("Simulation Time (hours)")
    ax.set_ylabel("HVAC Power (kW)")
    ax.set_title("Instantaneous HVAC Power")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / "energy_comparison.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ Saved energy comparison plot: {output_file}")
    plt.close()


def plot_comfort_analysis(df_baseline: pd.DataFrame, df_ai: pd.DataFrame, output_dir: Path,
                         comfort_range: Tuple[float, float] = (20, 24)):
    """Create comfort analysis plots."""
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    
    # Temperature over time
    ax = axes[0]
    for zone in df_baseline["zone"].unique():
        baseline_zone = df_baseline[df_baseline["zone"] == zone]
        ai_zone = df_ai[df_ai["zone"] == zone]
        
        ax.plot(baseline_zone["sim_time_hours"], baseline_zone["temperature_c"],
                label=f"Baseline - {zone}", linestyle="--", alpha=0.7)
        ax.plot(ai_zone["sim_time_hours"], ai_zone["temperature_c"],
                label=f"AI - {zone}", linewidth=2)
    
    # Comfort band shading
    ax.axhspan(comfort_range[0], comfort_range[1], alpha=0.2, color='green', label='Comfort Range')
    ax.set_xlabel("Simulation Time (hours)")
    ax.set_ylabel("Zone Temperature (°C)")
    ax.set_title("Zone Temperature Over Time")
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    # PMV over time
    ax = axes[1]
    for zone in df_baseline["zone"].unique():
        baseline_zone = df_baseline[df_baseline["zone"] == zone]
        ai_zone = df_ai[df_ai["zone"] == zone]
        
        ax.plot(baseline_zone["sim_time_hours"], baseline_zone["pmv"],
                label=f"Baseline - {zone}", linestyle="--", alpha=0.7)
        ax.plot(ai_zone["sim_time_hours"], ai_zone["pmv"],
                label=f"AI - {zone}", linewidth=2)
    
    ax.axhspan(-0.5, 0.5, alpha=0.2, color='green', label='Comfort Range')
    ax.set_xlabel("Simulation Time (hours)")
    ax.set_ylabel("PMV (Predicted Mean Vote)")
    ax.set_title("Thermal Comfort (PMV) Over Time")
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    # Setpoint comparison
    ax = axes[2]
    for zone in df_baseline["zone"].unique():
        baseline_zone = df_baseline[df_baseline["zone"] == zone]
        ai_zone = df_ai[df_ai["zone"] == zone]
        
        ax.plot(baseline_zone["sim_time_hours"], baseline_zone["cooling_setpoint_c"],
                label=f"Baseline Cool SP - {zone}", linestyle="--", alpha=0.5, color='red')
        ax.plot(ai_zone["sim_time_hours"], ai_zone["cooling_setpoint_c"],
                label=f"AI Cool SP - {zone}", linewidth=2, color='red')
        ax.plot(baseline_zone["sim_time_hours"], baseline_zone["heating_setpoint_c"],
                label=f"Baseline Heat SP - {zone}", linestyle="--", alpha=0.5, color='blue')
        ax.plot(ai_zone["sim_time_hours"], ai_zone["heating_setpoint_c"],
                label=f"AI Heat SP - {zone}", linewidth=2, color='blue')
    
    ax.set_xlabel("Simulation Time (hours)")
    ax.set_ylabel("Setpoint Temperature (°C)")
    ax.set_title("Heating and Cooling Setpoints Over Time")
    ax.legend(loc='best', fontsize=7)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / "comfort_analysis.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✓ Saved comfort analysis plot: {output_file}")
    plt.close()


def generate_summary_csv(metrics_baseline: Dict, metrics_ai: Dict, output_dir: Path):
    """Generate CSV summary of comparison."""
    
    data = []
    
    for metric_name in ["total_energy_kwh", "peak_power_kw", "avg_power_kw",
                        "comfort_time_pct", "pmv_comfort_pct", "avg_temperature_c",
                        "avg_pmv", "avg_cooling_setpoint_c", "avg_heating_setpoint_c"]:
        baseline_val = metrics_baseline.get(metric_name, 0)
        ai_val = metrics_ai.get(metric_name, 0)
        
        # Calculate improvement
        if baseline_val != 0:
            if "energy" in metric_name or "power" in metric_name:
                improvement_pct = ((baseline_val - ai_val) / baseline_val) * 100
            else:
                improvement_pct = ((ai_val - baseline_val) / baseline_val) * 100
        else:
            improvement_pct = 0
        
        data.append({
            "metric": metric_name,
            "baseline": f"{baseline_val:.2f}",
            "ai_controlled": f"{ai_val:.2f}",
            "improvement": f"{improvement_pct:+.1f}%"
        })
    
    df = pd.DataFrame(data)
    output_file = output_dir / "savings_summary.csv"
    df.to_csv(output_file, index=False)
    print(f"✓ Saved savings summary: {output_file}")
    
    return df


def main():
    parser = argparse.ArgumentParser(description="Analyze and compare AI vs baseline runs")
    parser.add_argument("--ai", type=str, required=True, help="Path to AI-controlled log file")
    parser.add_argument("--baseline", type=str, required=True, help="Path to baseline log file")
    parser.add_argument("--output", type=str, default="../results", help="Output directory for plots")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Loading run data...")
    print(f"  AI log: {args.ai}")
    print(f"  Baseline log: {args.baseline}")
    
    # Load data
    try:
        baseline_info, df_baseline = load_run_data(args.baseline)
        ai_info, df_ai = load_run_data(args.ai)
    except Exception as e:
        print(f"❌ Failed to load data: {e}")
        sys.exit(1)
    
    print(f"✓ Loaded baseline: {len(df_baseline)} timesteps")
    print(f"✓ Loaded AI run: {len(df_ai)} timesteps\n")
    
    # Calculate metrics
    print("Calculating metrics...")
    metrics_baseline = calculate_metrics(df_baseline)
    metrics_ai = calculate_metrics(df_ai)
    
    # Print summary
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)
    
    print(f"\nENERGY CONSUMPTION:")
    print(f"  Baseline:      {metrics_baseline['total_energy_kwh']:.1f} kWh")
    print(f"  AI Controlled: {metrics_ai['total_energy_kwh']:.1f} kWh")
    energy_savings_pct = ((metrics_baseline['total_energy_kwh'] - metrics_ai['total_energy_kwh']) / 
                         metrics_baseline['total_energy_kwh'] * 100)
    print(f"  Savings:       {energy_savings_pct:+.1f}%")
    
    print(f"\nPEAK DEMAND:")
    print(f"  Baseline:      {metrics_baseline['peak_power_kw']:.2f} kW")
    print(f"  AI Controlled: {metrics_ai['peak_power_kw']:.2f} kW")
    peak_reduction_pct = ((metrics_baseline['peak_power_kw'] - metrics_ai['peak_power_kw']) / 
                         metrics_baseline['peak_power_kw'] * 100)
    print(f"  Reduction:     {peak_reduction_pct:+.1f}%")
    
    print(f"\nCOMFORT PERFORMANCE:")
    print(f"  Baseline temp comfort:  {metrics_baseline['comfort_time_pct']:.1f}%")
    print(f"  AI temp comfort:        {metrics_ai['comfort_time_pct']:.1f}%")
    print(f"  Baseline PMV comfort:   {metrics_baseline['pmv_comfort_pct']:.1f}%")
    print(f"  AI PMV comfort:         {metrics_ai['pmv_comfort_pct']:.1f}%")
    
    print("\n" + "=" * 60 + "\n")
    
    # Generate visualizations
    print("Generating visualizations...")
    plot_energy_comparison(df_baseline, df_ai, output_dir)
    plot_comfort_analysis(df_baseline, df_ai, output_dir)
    
    # Generate CSV summary
    print("\nGenerating summary CSV...")
    summary_df = generate_summary_csv(metrics_baseline, metrics_ai, output_dir)
    
    print("\n" + summary_df.to_string(index=False))
    
    print(f"\n✓ Analysis complete! Results saved to: {output_dir}")
    print(f"  - energy_comparison.png")
    print(f"  - comfort_analysis.png")
    print(f"  - savings_summary.csv")


if __name__ == "__main__":
    main()
