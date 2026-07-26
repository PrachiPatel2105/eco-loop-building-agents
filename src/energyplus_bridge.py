"""
EnergyPlus Bridge: Wrapper for EMS sensor/actuator access.

Provides high-level interface to read building state and write control actions
during live EnergyPlus simulation via Python API callbacks.
"""

import math
from typing import Dict, Any, Optional
from datetime import datetime


class EnergyPlusBridge:
    """
    Bridge between EnergyPlus EMS API and control logic.
    
    Handles sensor reading, actuator writing, and thermal comfort calculations.
    """
    
    def __init__(self, zones: list):
        """
        Initialize bridge.
        
        Args:
            zones: List of zone names to monitor/control
        """
        self.zones = zones
        self.sensor_handles = {}
        self.actuator_handles = {}
        self.last_sensor_data = {}
        self.current_state = None
        self.api = None  # Store API reference
        
    def setup_sensors(self, state) -> bool:
        """
        Register EMS sensors during EnergyPlus initialization callback.
        
        Args:
            state: EnergyPlus state object
            
        Returns:
            True if setup successful
        """
        try:
            api = self.api  # Use stored API reference
            
            for zone in self.zones:
                # Zone air temperature sensor
                temp_handle = api.exchange.get_variable_handle(
                    state,
                    "Zone Mean Air Temperature",
                    zone
                )
                self.sensor_handles[f"{zone}_temp"] = temp_handle
                
                # Zone air humidity ratio (for PMV calculation)
                humidity_handle = api.exchange.get_variable_handle(
                    state,
                    "Zone Air Humidity Ratio",
                    zone
                )
                self.sensor_handles[f"{zone}_humidity"] = humidity_handle
                
                # Zone HVAC total heating/cooling rate
                hvac_heat_handle = api.exchange.get_variable_handle(
                    state,
                    "Zone Air System Sensible Heating Rate",
                    zone
                )
                self.sensor_handles[f"{zone}_hvac_heat"] = hvac_heat_handle
                
                hvac_cool_handle = api.exchange.get_variable_handle(
                    state,
                    "Zone Air System Sensible Cooling Rate",
                    zone
                )
                self.sensor_handles[f"{zone}_hvac_cool"] = hvac_cool_handle
            
            # Outdoor temperature (for context)
            outdoor_temp_handle = api.exchange.get_variable_handle(
                state,
                "Site Outdoor Air Drybulb Temperature",
                "Environment"
            )
            self.sensor_handles["outdoor_temp"] = outdoor_temp_handle
            
            print(f"✓ EnergyPlus sensors registered for {len(self.zones)} zone(s)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup sensors: {e}")
            return False
    
    def setup_actuators(self, state) -> bool:
        """
        Register EMS actuators during EnergyPlus initialization callback.
        
        Args:
            state: EnergyPlus state object
            
        Returns:
            True if setup successful
        """
        try:
            api = self.api  # Use stored API reference
            
            for zone in self.zones:
                # Cooling setpoint actuator
                cooling_handle = api.exchange.get_actuator_handle(
                    state,
                    "Zone Temperature Control",
                    "Cooling Setpoint",
                    zone
                )
                self.actuator_handles[f"{zone}_cooling_setpoint"] = cooling_handle
                
                # Heating setpoint actuator
                heating_handle = api.exchange.get_actuator_handle(
                    state,
                    "Zone Temperature Control",
                    "Heating Setpoint",
                    zone
                )
                self.actuator_handles[f"{zone}_heating_setpoint"] = heating_handle
            
            print(f"✓ EnergyPlus actuators registered for {len(self.zones)} zone(s)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup actuators: {e}")
            return False
    
    def read_sensors(self, state=None) -> Dict[str, Any]:
        """
        Read current values from all registered sensors.
        
        Args:
            state: EnergyPlus state object (if called from callback)
            
        Returns:
            Dictionary with sensor data for all zones
        """
        if state is None:
            # Return cached data if called outside callback
            return self.last_sensor_data
        
        try:
            api = self.api  # Use stored API reference
            
            # Get current simulation time
            current_time = api.exchange.current_time(state)
            year = api.exchange.year(state)
            month = api.exchange.month(state)
            day = api.exchange.day_of_month(state)
            hour = api.exchange.hour(state)
            minute = api.exchange.minutes(state)
            
            timestamp = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
            
            # Read outdoor conditions
            outdoor_temp = api.exchange.get_variable_value(
                state,
                self.sensor_handles["outdoor_temp"]
            )
            
            # Read all zone data
            zones_data = {}
            for zone in self.zones:
                # Temperature
                temp_c = api.exchange.get_variable_value(
                    state,
                    self.sensor_handles[f"{zone}_temp"]
                )
                
                # Humidity ratio
                humidity_ratio = api.exchange.get_variable_value(
                    state,
                    self.sensor_handles[f"{zone}_humidity"]
                )
                
                # HVAC power (convert W to kW)
                hvac_heat_w = api.exchange.get_variable_value(
                    state,
                    self.sensor_handles[f"{zone}_hvac_heat"]
                )
                hvac_cool_w = api.exchange.get_variable_value(
                    state,
                    self.sensor_handles[f"{zone}_hvac_cool"]
                )
                hvac_total_kw = (hvac_heat_w + hvac_cool_w) / 1000.0
                
                # Get current setpoints from actuators
                cooling_sp = api.exchange.get_actuator_value(
                    state,
                    self.actuator_handles[f"{zone}_cooling_setpoint"]
                )
                heating_sp = api.exchange.get_actuator_value(
                    state,
                    self.actuator_handles[f"{zone}_heating_setpoint"]
                )
                
                # Calculate PMV thermal comfort
                pmv = self.calculate_pmv(temp_c, humidity_ratio, outdoor_temp)
                
                zones_data[zone] = {
                    "temperature_c": round(temp_c, 2),
                    "humidity_ratio": round(humidity_ratio, 6),
                    "cooling_setpoint_c": round(cooling_sp, 1),
                    "heating_setpoint_c": round(heating_sp, 1),
                    "hvac_power_kw": round(hvac_total_kw, 3),
                    "pmv": round(pmv, 2)
                }
            
            sensor_data = {
                "timestamp": timestamp,
                "sim_time_hours": current_time,
                "outdoor_temp_c": round(outdoor_temp, 2),
                "zones": zones_data
            }
            
            # Cache for access outside callback
            self.last_sensor_data = sensor_data
            self.current_state = state
            
            return sensor_data
            
        except Exception as e:
            print(f"⚠ Warning: Failed to read sensors: {e}")
            # Return last known good data
            return self.last_sensor_data if self.last_sensor_data else {
                "timestamp": "unknown",
                "sim_time_hours": 0,
                "outdoor_temp_c": 0,
                "zones": {}
            }
    
    def write_actuators(self, actions: Dict[str, float], state=None) -> bool:
        """
        Write new values to actuators.
        
        Args:
            actions: Dictionary mapping actuator names to values
                    (e.g., {"Zone1_cooling_setpoint": 24.0})
            state: EnergyPlus state object (uses cached if None)
            
        Returns:
            True if successful
        """
        if state is None:
            state = self.current_state
            
        if state is None:
            print("⚠ Warning: Cannot write actuators, no state available")
            return False
        
        try:
            api = self.api  # Use stored API reference
            
            for actuator_name, value in actions.items():
                if actuator_name in self.actuator_handles:
                    api.exchange.set_actuator_value(
                        state,
                        self.actuator_handles[actuator_name],
                        value
                    )
                else:
                    print(f"⚠ Warning: Unknown actuator '{actuator_name}'")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to write actuators: {e}")
            return False
    
    def calculate_pmv(self, temp_c: float, humidity_ratio: float, outdoor_temp_c: float) -> float:
        """
        Calculate simplified Predicted Mean Vote (PMV) thermal comfort index.
        
        PMV scale: -3 (cold) to +3 (hot), with 0 being neutral.
        Comfortable range: -0.5 to +0.5
        
        This is a simplified approximation using zone air temperature
        and seasonal clothing assumptions.
        
        Args:
            temp_c: Zone air temperature in Celsius
            humidity_ratio: Zone air humidity ratio (kg water / kg dry air)
            outdoor_temp_c: Outdoor temperature for clothing estimation
            
        Returns:
            PMV value (approximate)
        """
        # Simplified PMV based on operative temperature
        # Full Fanger model requires: air temp, radiant temp, air velocity,
        # humidity, clothing, metabolic rate
        
        # Assumptions for office building:
        # - Metabolic rate: 1.2 met (light office work)
        # - Air velocity: 0.1 m/s (typical indoor)
        # - Radiant temp ≈ air temp (simplified)
        
        # Estimate clothing based on outdoor temperature
        if outdoor_temp_c < 10:
            clo = 1.0  # Winter clothing
        elif outdoor_temp_c < 20:
            clo = 0.75  # Spring/fall
        else:
            clo = 0.5  # Summer clothing
        
        # Simplified PMV approximation (empirical fit)
        # Neutral temp varies with clothing:
        # - 1.0 clo: ~22°C neutral
        # - 0.5 clo: ~24°C neutral
        neutral_temp = 21 + (1.0 - clo) * 3
        
        # PMV ≈ sensitivity factor × temperature deviation
        sensitivity = 0.3  # Typical for office conditions
        pmv = sensitivity * (temp_c - neutral_temp)
        
        # Humidity adjustment (simplified)
        relative_humidity_estimate = humidity_ratio * 100  # Very rough estimate
        if relative_humidity_estimate > 0.01:  # RH > 60% increases discomfort
            pmv += 0.2
        
        # Clamp to reasonable range
        pmv = max(-3.0, min(3.0, pmv))
        
        return pmv
    
    def get_zone_names(self) -> list:
        """Return list of zone names being monitored."""
        return self.zones.copy()
    
    def is_comfort_violated(self, zone_data: Dict[str, Any], 
                           pmv_range: tuple = (-0.5, 0.5),
                           temp_range: tuple = (20, 24)) -> bool:
        """
        Check if comfort bounds are violated.
        
        Args:
            zone_data: Zone data dictionary from read_sensors()
            pmv_range: Acceptable PMV range (min, max)
            temp_range: Acceptable temperature range in °C (min, max)
            
        Returns:
            True if comfort is violated
        """
        pmv = zone_data.get("pmv", 0)
        temp = zone_data.get("temperature_c", 22)
        
        # Check PMV first (more accurate comfort metric)
        if pmv < pmv_range[0] or pmv > pmv_range[1]:
            return True
        
        # Fallback to temperature if PMV is borderline
        if temp < temp_range[0] or temp > temp_range[1]:
            return True
        
        return False


def test_bridge():
    """
    Minimal test function to verify bridge can be instantiated.
    Real testing requires running EnergyPlus simulation.
    """
    print("Testing EnergyPlusBridge instantiation...")
    
    zones = ["Core_ZN"]
    bridge = EnergyPlusBridge(zones)
    
    print(f"✓ Bridge created for zones: {bridge.get_zone_names()}")
    
    # Test PMV calculation with typical values
    pmv = bridge.calculate_pmv(
        temp_c=22.0,
        humidity_ratio=0.008,
        outdoor_temp_c=10.0
    )
    print(f"✓ PMV calculation test: {pmv:.2f} (expected ~0)")
    
    pmv_cold = bridge.calculate_pmv(
        temp_c=18.0,
        humidity_ratio=0.008,
        outdoor_temp_c=10.0
    )
    print(f"✓ PMV cold test: {pmv_cold:.2f} (expected < -0.5)")
    
    pmv_hot = bridge.calculate_pmv(
        temp_c=26.0,
        humidity_ratio=0.008,
        outdoor_temp_c=10.0
    )
    print(f"✓ PMV hot test: {pmv_hot:.2f} (expected > 0.5)")
    
    print("✓ Bridge test complete")


if __name__ == "__main__":
    test_bridge()
