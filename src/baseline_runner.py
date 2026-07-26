"""
Baseline runner: Run building simulation with fixed schedules (no AI control).

Provides comparison baseline for evaluating AI control performance.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

try:
    from pyenergyplus.api import EnergyPlusAPI
except ImportError:
    print("❌ pyenergyplus not found in Python path.")
    print("   pyenergyplus is bundled with EnergyPlus, not available via pip.")
    print("   Set PYTHONPATH to your EnergyPlus install directory:")
    print("   Windows: set PYTHONPATH=C:\\EnergyPlusV24-2-0")
    print("   Linux/Mac: export PYTHONPATH=/usr/local/EnergyPlus-24-2-0")
    
    # Try to auto-detect and add common EnergyPlus install locations
    import platform
    import glob
    possible_paths = []
    
    if platform.system() == "Windows":
        possible_paths = glob.glob("C:\\EnergyPlusV*")
    elif platform.system() == "Darwin":  # macOS
        possible_paths = glob.glob("/Applications/EnergyPlus-*")
    else:  # Linux
        possible_paths.extend(glob.glob("/usr/local/EnergyPlus-*"))
        possible_paths.extend(glob.glob("/opt/EnergyPlus-*"))
    
    if possible_paths:
        sys.path.insert(0, possible_paths[0])
        try:
            from pyenergyplus.api import EnergyPlusAPI
            print(f"✓ Auto-detected and loaded from: {possible_paths[0]}\n")
        except ImportError:
            print("   Auto-detection failed. Please set PYTHONPATH manually.")
            sys.exit(1)
    else:
        print("   No EnergyPlus installation detected.")
        sys.exit(1)

from energyplus_bridge import EnergyPlusBridge


class BaselineRunner:
    """Runs simulation with fixed setpoints (no adaptive control)."""
    
    def __init__(self, 
                 idf_path: str,
                 weather_path: str,
                 output_dir: str,
                 zones: List[str],
                 fixed_cooling_sp: float = 24.0,
                 fixed_heating_sp: float = 20.0,
                 verbose: bool = False):
        """
        Initialize baseline runner.
        
        Args:
            idf_path: Path to IDF building model file
            weather_path: Path to EPW weather file
            output_dir: Directory for outputs
            zones: List of zone names
            fixed_cooling_sp: Fixed cooling setpoint (°C)
            fixed_heating_sp: Fixed heating setpoint (°C)
            verbose: Verbose output
        """
        self.idf_path = idf_path
        self.weather_path = weather_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.zones = zones
        self.fixed_cooling_sp = fixed_cooling_sp
        self.fixed_heating_sp = fixed_heating_sp
        self.verbose = verbose
        
        print("Initializing Baseline (Fixed Setpoint) Runner...")
        print(f"  Fixed cooling setpoint: {fixed_cooling_sp}°C")
        print(f"  Fixed heating setpoint: {fixed_heating_sp}°C")
        
        self.bridge = EnergyPlusBridge(zones)
        
        # Logging
        self.log_file = self.output_dir / f"baseline_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.log_entries = []
        
        # State tracking
        self.timestep_count = 0
        self.setpoints_applied = False
        
        print("✓ Baseline runner initialized\n")
    
    def callback_after_new_environment_warmup_complete(self, state) -> int:
        """Called after warmup - apply fixed setpoints."""
        print("✓ Warmup complete, applying fixed setpoints...")
        
        # Apply fixed setpoints to all zones
        actions = {}
        for zone in self.zones:
            actions[f"{zone}_cooling_setpoint"] = self.fixed_cooling_sp
            actions[f"{zone}_heating_setpoint"] = self.fixed_heating_sp
        
        self.bridge.write_actuators(actions, state)
        self.setpoints_applied = True
        
        print(f"  ✓ Fixed setpoints applied to {len(self.zones)} zone(s)\n")
        return 0
    
    def callback_begin_zone_timestep(self, state) -> int:
        """Callback at each timestep - just log data, no control changes."""
        try:
            self.timestep_count += 1
            
            # Read and log sensor data
            sensor_data = self.bridge.read_sensors(state)
            
            if self.verbose and self.timestep_count % 10 == 0:
                current_time = sensor_data.get("sim_time_hours", 0)
                print(f"⏱ Timestep {self.timestep_count}, Sim time: {current_time:.1f} hours")
            
            # Log state
            self._log_state(sensor_data)
            
            # Ensure fixed setpoints stay applied (in case EnergyPlus resets them)
            if self.setpoints_applied:
                actions = {}
                for zone in self.zones:
                    actions[f"{zone}_cooling_setpoint"] = self.fixed_cooling_sp
                    actions[f"{zone}_heating_setpoint"] = self.fixed_heating_sp
                self.bridge.write_actuators(actions, state)
            
        except Exception as e:
            print(f"❌ Error in callback: {e}")
            import traceback
            traceback.print_exc()
        
        return 0
    
    def _log_state(self, sensor_data: Dict[str, Any]):
        """Log current state."""
        log_entry = {
            "timestamp": sensor_data.get("timestamp", ""),
            "sim_time_hours": sensor_data.get("sim_time_hours", 0),
            "outdoor_temp_c": sensor_data.get("outdoor_temp_c", 0),
            "zones": sensor_data.get("zones", {}),
            "control_type": "fixed_baseline"
        }
        self.log_entries.append(log_entry)
    
    def run(self):
        """Run baseline simulation."""
        print("Starting baseline EnergyPlus simulation (fixed setpoints)...\n")
        
        try:
            api = EnergyPlusAPI()
            state = api.state_manager.new_state()
            
            # Store API reference in bridge
            self.bridge.api = api
            
            # Register callbacks
            api.runtime.callback_begin_new_environment(state, self.bridge.setup_sensors)
            api.runtime.callback_begin_new_environment(state, self.bridge.setup_actuators)
            api.runtime.callback_after_new_environment_warmup_complete(
                state,
                self.callback_after_new_environment_warmup_complete
            )
            api.runtime.callback_begin_zone_timestep_before_set_current_weather(
                state,
                self.callback_begin_zone_timestep
            )
            
            # Run simulation
            start_time = time.time()
            
            idf_str = str(Path(self.idf_path).absolute())
            weather_str = str(Path(self.weather_path).absolute())
            output_str = str(self.output_dir.absolute())
            
            api.runtime.run_energyplus(
                state,
                [
                    "-w", weather_str,
                    "-d", output_str,
                    idf_str
                ]
            )
            
            elapsed = time.time() - start_time
            
            # Save logs
            self._save_logs()
            
            print(f"\n{'=' * 60}")
            print(f"✓ Baseline Simulation Complete!")
            print(f"{'=' * 60}")
            print(f"  Wall-clock time: {elapsed:.1f} seconds")
            print(f"  Timesteps: {self.timestep_count}")
            print(f"  Log file: {self.log_file}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Simulation failed: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                self._save_logs()
            except:
                pass
            
            return False
    
    def _save_logs(self):
        """Save logs to JSON."""
        with open(self.log_file, 'w') as f:
            json.dump({
                "run_info": {
                    "idf": self.idf_path,
                    "weather": self.weather_path,
                    "zones": self.zones,
                    "control_type": "fixed_baseline",
                    "fixed_cooling_setpoint_c": self.fixed_cooling_sp,
                    "fixed_heating_setpoint_c": self.fixed_heating_sp,
                    "timesteps": self.timestep_count
                },
                "log_entries": self.log_entries
            }, f, indent=2)
        
        print(f"\n✓ Saved {len(self.log_entries)} log entries to {self.log_file}")


def main():
    parser = argparse.ArgumentParser(description="Baseline runner - Fixed setpoint simulation")
    parser.add_argument("--idf", type=str, help="Path to IDF file",
                       default="../models/SmallOffice_Baseline.idf")
    parser.add_argument("--weather", type=str, help="Path to weather file",
                       default="../models/Chicago.epw")
    parser.add_argument("--output", type=str, help="Output directory",
                       default="../logs")
    parser.add_argument("--zones", type=str, nargs="+", help="Zone names",
                       default=["West Zone"])
    parser.add_argument("--cooling-sp", type=float, help="Fixed cooling setpoint (°C)",
                       default=24.0)
    parser.add_argument("--heating-sp", type=float, help="Fixed heating setpoint (°C)",
                       default=20.0)
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Resolve paths
    script_dir = Path(__file__).parent
    idf_path = script_dir / args.idf
    weather_path = script_dir / args.weather
    output_dir = script_dir / args.output
    
    # Check files
    if not idf_path.exists():
        print(f"❌ IDF file not found: {idf_path}")
        sys.exit(1)
    
    if not weather_path.exists():
        print(f"❌ Weather file not found: {weather_path}")
        sys.exit(1)
    
    # Run baseline
    runner = BaselineRunner(
        idf_path=str(idf_path),
        weather_path=str(weather_path),
        output_dir=str(output_dir),
        zones=args.zones,
        fixed_cooling_sp=args.cooling_sp,
        fixed_heating_sp=args.heating_sp,
        verbose=args.verbose
    )
    
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
