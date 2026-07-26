"""
Main orchestrator for closed-loop building control.

Coordinates EnergyPlus simulation, LLM agent, and tool execution
in a real-time control loop.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add pyenergyplus import (bundled with EnergyPlus installation)
try:
    from pyenergyplus.api import EnergyPlusAPI
except ImportError:
    print("❌ pyenergyplus not found in Python path.")
    print("   pyenergyplus is bundled with EnergyPlus, not available via pip.")
    print()
    print("   Solutions:")
    print("   1. Add EnergyPlus install directory to PYTHONPATH:")
    print("      Windows: set PYTHONPATH=C:\\EnergyPlusV24-2-0")
    print("      Linux/Mac: export PYTHONPATH=/usr/local/EnergyPlus-24-2-0")
    print()
    print("   2. Or add to sys.path in your script before importing:")
    print("      import sys")
    print("      sys.path.insert(0, 'C:\\\\EnergyPlusV24-2-0')  # Windows")
    print()
    
    # Try to auto-detect and add common EnergyPlus install locations
    import platform
    possible_paths = []
    
    if platform.system() == "Windows":
        # Check common Windows install locations
        import glob
        possible_paths = glob.glob("C:\\EnergyPlusV*")
    elif platform.system() == "Darwin":  # macOS
        import glob
        possible_paths = glob.glob("/Applications/EnergyPlus-*")
    else:  # Linux
        import glob
        possible_paths.extend(glob.glob("/usr/local/EnergyPlus-*"))
        possible_paths.extend(glob.glob("/opt/EnergyPlus-*"))
    
    if possible_paths:
        print(f"   Found possible EnergyPlus installations:")
        for path in possible_paths:
            print(f"     - {path}")
        print()
        # Try to add the first one and retry import
        sys.path.insert(0, possible_paths[0])
        try:
            from pyenergyplus.api import EnergyPlusAPI
            print(f"✓ Successfully imported pyenergyplus from: {possible_paths[0]}\n")
        except ImportError:
            print("   Auto-detection failed. Please set PYTHONPATH manually.")
            sys.exit(1)
    else:
        print("   No EnergyPlus installation detected. Please install EnergyPlus first:")
        print("   https://github.com/NREL/EnergyPlus/releases")
        sys.exit(1)

from energyplus_bridge import EnergyPlusBridge
from llm_agent import LLMAgent
from tools import ToolExecutor, get_tool_schemas, format_tool_call_result


# Configuration
LLM_CALL_INTERVAL_MINUTES = 60  # How often to query LLM (simulated minutes)
COMFORT_BOUNDS = (20.0, 24.0)    # Temperature comfort range (°C)
PMV_BOUNDS = (-0.5, 0.5)         # PMV comfort range
OLLAMA_MODEL = "qwen2.5:7b-instruct"  # LLM model to use
OLLAMA_URL = "http://localhost:11434"


class BuildingOrchestrator:
    """Orchestrates closed-loop control between EnergyPlus and LLM agent."""
    
    def __init__(self, 
                 idf_path: str,
                 weather_path: str,
                 output_dir: str,
                 zones: List[str],
                 verbose: bool = False):
        """
        Initialize orchestrator.
        
        Args:
            idf_path: Path to IDF building model file
            idf_path: Path to EPW weather file
            output_dir: Directory for simulation outputs and logs
            zones: List of zone names to control
            verbose: Print detailed debug information
        """
        self.idf_path = idf_path
        self.weather_path = weather_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.zones = zones
        self.verbose = verbose
        
        # Initialize components
        print("Initializing Eco-Loop Building Agents...")
        print(f"  IDF: {idf_path}")
        print(f"  Weather: {weather_path}")
        print(f"  Zones: {zones}")
        
        self.bridge = EnergyPlusBridge(zones)
        self.agent = LLMAgent(
            model=OLLAMA_MODEL,
            ollama_url=OLLAMA_URL,
            tool_schemas=get_tool_schemas(),
            comfort_bounds=COMFORT_BOUNDS,
            pmv_bounds=PMV_BOUNDS
        )
        self.tool_executor = ToolExecutor(self.bridge)
        
        # Logging
        self.log_file = self.output_dir / f"ai_controlled_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.log_entries = []
        
        # State tracking
        self.last_llm_call_time = 0.0
        self.timestep_count = 0
        self.simulation_complete = False
        self.warmup_complete = False  # Track when warmup ends
        
        print("✓ Orchestrator initialized\n")
    
    def callback_begin_zone_timestep(self, state) -> int:
        """
        EnergyPlus callback: Called at beginning of each zone timestep.
        
        This is where we read sensors and potentially make control decisions.
        """
        try:
            self.timestep_count += 1
            
            # Read current sensor data
            sensor_data = self.bridge.read_sensors(state)
            current_time = sensor_data.get("sim_time_hours", 0)
            
            # If warmup just completed, reset timer for main simulation
            if self.warmup_complete and self.last_llm_call_time > current_time:
                if self.verbose:
                    print(f"   [DEBUG] Resetting timer: last_call was {self.last_llm_call_time:.2f}h, now {current_time:.2f}h")
                self.last_llm_call_time = 0.0
            
            if self.verbose and self.timestep_count % 10 == 0:
                print(f"⏱ Timestep {self.timestep_count}, Sim time: {current_time:.1f} hours")
            
            # Check if it's time for LLM decision
            time_since_last_call = (current_time - self.last_llm_call_time) * 60  # Convert to minutes
            
            # Debug: Log timing every 10 timesteps
            if self.verbose and self.timestep_count % 10 == 0:
                print(f"   [DEBUG] current_time={current_time:.2f}h, last_call={self.last_llm_call_time:.2f}h, delta={time_since_last_call:.1f}min, threshold={LLM_CALL_INTERVAL_MINUTES}min")
            
            if time_since_last_call >= LLM_CALL_INTERVAL_MINUTES or self.last_llm_call_time == 0:
                self._make_control_decision(sensor_data, state)
                self.last_llm_call_time = current_time
            
            # Log current state every timestep (for analysis)
            self._log_state(sensor_data, llm_called=False)
            
        except Exception as e:
            print(f"❌ Error in callback: {e}")
            import traceback
            traceback.print_exc()
        
        return 0  # Continue simulation
    
    def _make_control_decision(self, sensor_data: Dict[str, Any], state):
        """Make control decision using LLM agent."""
        try:
            timestamp = sensor_data.get("timestamp", "unknown")
            print(f"\n🧠 LLM Decision Point - {timestamp}")
            print("=" * 60)
            
            # Show current status
            for zone_name, zone_data in sensor_data.get("zones", {}).items():
                temp = zone_data.get("temperature_c", 0)
                pmv = zone_data.get("pmv", 0)
                hvac_kw = zone_data.get("hvac_power_kw", 0)
                print(f"  {zone_name}: {temp:.1f}°C, PMV={pmv:.2f}, HVAC={hvac_kw:.2f}kW")
            
            # Get LLM decision
            reasoning, tool_calls = self.agent.make_control_decision(sensor_data)
            
            print(f"\n💭 LLM Reasoning:")
            print(f"  {reasoning[:200]}..." if len(reasoning) > 200 else f"  {reasoning}")
            
            # Execute tool calls
            if tool_calls:
                print(f"\n🔧 Executing {len(tool_calls)} tool call(s):")
                for i, call in enumerate(tool_calls, 1):
                    tool_name = call.get("name", "unknown")
                    tool_args = call.get("arguments", {})
                    
                    print(f"  {i}. {tool_name}({json.dumps(tool_args)})")
                    
                    # Execute tool
                    result = self.tool_executor.execute_tool(tool_name, tool_args)
                    result_str = format_tool_call_result(tool_name, result)
                    print(f"     {result_str}")
                    
                    # Verify setpoint changes were applied
                    if tool_name in ["set_cooling_setpoint", "set_heating_setpoint"]:
                        if not result.get("success"):
                            print(f"     ⚠ Warning: Setpoint change failed - {result.get('error', 'unknown error')}")
                        else:
                            # Actuator write already happened in tool_executor._set_cooling_setpoint/_set_heating_setpoint
                            # which called bridge.write_actuators() with the actual value
                            if self.verbose:
                                print(f"     ✓ Actuator write confirmed: {result.get('message', '')}")
                
            else:
                print("  No actions taken")
            
            # Log this decision
            self._log_state(sensor_data, llm_called=True, reasoning=reasoning, tool_calls=tool_calls)
            
            print("=" * 60 + "\n")
            
        except Exception as e:
            print(f"❌ Error making control decision: {e}")
            import traceback
            traceback.print_exc()
    
    def _log_state(self, sensor_data: Dict[str, Any], llm_called: bool = False,
                   reasoning: str = "", tool_calls: List[Dict] = None):
        """Log current state to file."""
        log_entry = {
            "timestamp": sensor_data.get("timestamp", ""),
            "sim_time_hours": sensor_data.get("sim_time_hours", 0),
            "outdoor_temp_c": sensor_data.get("outdoor_temp_c", 0),
            "zones": sensor_data.get("zones", {}),
            "llm_called": llm_called
        }
        
        if llm_called:
            log_entry["llm_reasoning"] = reasoning
            log_entry["tool_calls"] = tool_calls or []
        
        self.log_entries.append(log_entry)
    
    def callback_after_new_environment_warmup_complete(self, state) -> int:
        """Called after warmup period completes."""
        print("✓ Warmup period complete, starting main simulation\n")
        # Mark warmup as complete and reset timer
        self.warmup_complete = True
        self.last_llm_call_time = 0.0
        return 0
    
    def run(self):
        """Run the simulation with closed-loop control."""
        print("Starting EnergyPlus simulation with AI control...")
        print(f"LLM call interval: every {LLM_CALL_INTERVAL_MINUTES} simulated minutes\n")
        
        try:
            api = EnergyPlusAPI()
            state = api.state_manager.new_state()
            
            # Store API reference in bridge
            self.bridge.api = api
            
            # Register EMS sensors/actuators
            api.runtime.callback_begin_new_environment(state, self.bridge.setup_sensors)
            api.runtime.callback_begin_new_environment(state, self.bridge.setup_actuators)
            api.runtime.callback_after_new_environment_warmup_complete(
                state,
                self.callback_after_new_environment_warmup_complete
            )
            
            # Register main control callback
            api.runtime.callback_begin_zone_timestep_before_set_current_weather(
                state,
                self.callback_begin_zone_timestep
            )
            
            # Set update tool executor log path
            err_file = self.output_dir / "eplusout.err"
            self.tool_executor.log_file_path = str(err_file)
            
            # Run simulation
            start_time = time.time()
            
            # Convert paths to strings for API
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
            print(f"✓ Simulation Complete!")
            print(f"{'=' * 60}")
            print(f"  Wall-clock time: {elapsed:.1f} seconds")
            print(f"  Timesteps: {self.timestep_count}")
            print(f"  LLM calls: {len([e for e in self.log_entries if e.get('llm_called')])}")
            print(f"  Log file: {self.log_file}")
            print(f"  Output dir: {self.output_dir}")
            
            # Agent statistics
            stats = self.agent.get_statistics()
            print(f"\n  Agent Statistics:")
            print(f"    Total decisions: {stats['total_decisions']}")
            print(f"    Total tool calls: {stats['total_tool_calls']}")
            print(f"    Avg tools/decision: {stats['avg_tools_per_decision']:.1f}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Simulation failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to save logs anyway
            try:
                self._save_logs()
            except:
                pass
            
            return False
    
    def _save_logs(self):
        """Save log entries to JSON file."""
        with open(self.log_file, 'w') as f:
            json.dump({
                "run_info": {
                    "idf": self.idf_path,
                    "weather": self.weather_path,
                    "zones": self.zones,
                    "llm_model": OLLAMA_MODEL,
                    "llm_call_interval_min": LLM_CALL_INTERVAL_MINUTES,
                    "comfort_bounds_c": COMFORT_BOUNDS,
                    "pmv_bounds": PMV_BOUNDS,
                    "timesteps": self.timestep_count
                },
                "log_entries": self.log_entries
            }, f, indent=2)
        
        print(f"\n✓ Saved {len(self.log_entries)} log entries to {self.log_file}")


def main():
    parser = argparse.ArgumentParser(description="Eco-Loop Building Agents - AI-controlled EnergyPlus simulation")
    parser.add_argument("--idf", type=str, help="Path to IDF file",
                       default="../models/SmallOffice_EMS.idf")
    parser.add_argument("--weather", type=str, help="Path to weather file",
                       default="../models/Chicago.epw")
    parser.add_argument("--output", type=str, help="Output directory",
                       default="../logs")
    parser.add_argument("--zones", type=str, nargs="+", help="Zone names to control",
                       default=["West Zone"])
    parser.add_argument("--days", type=int, help="Number of simulation days (modifies IDF)",
                       default=None)
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    idf_path = script_dir / args.idf
    weather_path = script_dir / args.weather
    output_dir = script_dir / args.output
    
    # Check files exist
    if not idf_path.exists():
        print(f"❌ IDF file not found: {idf_path}")
        print(f"   Please ensure the building model file exists")
        sys.exit(1)
    
    if not weather_path.exists():
        print(f"❌ Weather file not found: {weather_path}")
        print(f"   Please ensure the weather file exists")
        print(f"   You can copy from: c:\\Users\\vaira\\OneDrive\\Desktop\\Honeywell\\energyplus_test\\Chicago.epw")
        sys.exit(1)
    
    # Create and run orchestrator
    orchestrator = BuildingOrchestrator(
        idf_path=str(idf_path),
        weather_path=str(weather_path),
        output_dir=str(output_dir),
        zones=args.zones,
        verbose=args.verbose
    )
    
    success = orchestrator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
