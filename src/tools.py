"""
Tool definitions for LLM function calling.

Defines the tools available to the LLM agent, including JSON schemas
and implementation functions that interact with the EnergyPlus bridge.
"""

import json
from typing import Dict, List, Any, Optional


# Tool JSON Schemas (OpenAPI-style for function calling)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_zone_status",
            "description": "Get current status of a building zone including temperature, comfort, energy use, and setpoints",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {
                        "type": "string",
                        "description": "Zone name (e.g., 'Core', 'Perimeter', 'Zone1'). Use 'all' to get all zones."
                    }
                },
                "required": ["zone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_cooling_setpoint",
            "description": "Set the cooling setpoint temperature for a zone. Only active when cooling is needed (zone too warm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {
                        "type": "string",
                        "description": "Zone name to control"
                    },
                    "value": {
                        "type": "number",
                        "description": "Cooling setpoint in Celsius (18-30°C). Zone cools if temperature exceeds this."
                    }
                },
                "required": ["zone", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_heating_setpoint",
            "description": "Set the heating setpoint temperature for a zone. Only active when heating is needed (zone too cold).",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {
                        "type": "string",
                        "description": "Zone name to control"
                    },
                    "value": {
                        "type": "number",
                        "description": "Heating setpoint in Celsius (15-26°C). Zone heats if temperature falls below this."
                    }
                },
                "required": ["zone", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_log_errors",
            "description": "Check recent EnergyPlus error log for warnings or errors. Use this if control actions seem ineffective.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lines": {
                        "type": "number",
                        "description": "Number of recent log lines to check (default: 50)"
                    }
                },
                "required": []
            }
        }
    }
]


class ToolExecutor:
    """Executes tool calls by bridging LLM requests to EnergyPlus bridge."""
    
    def __init__(self, bridge, log_file_path: Optional[str] = None):
        """
        Initialize tool executor.
        
        Args:
            bridge: EnergyPlusBridge instance
            log_file_path: Path to EnergyPlus error log (eplusout.err)
        """
        self.bridge = bridge
        self.log_file_path = log_file_path
        
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Dictionary of tool arguments
            
        Returns:
            Dictionary containing tool result
        """
        try:
            if tool_name == "get_zone_status":
                return self._get_zone_status(arguments)
            elif tool_name == "set_cooling_setpoint":
                return self._set_cooling_setpoint(arguments)
            elif tool_name == "set_heating_setpoint":
                return self._set_heating_setpoint(arguments)
            elif tool_name == "get_recent_log_errors":
                return self._get_recent_log_errors(arguments)
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }
    
    def _get_zone_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get current zone status from bridge."""
        zone = args.get("zone", "all")
        
        try:
            sensor_data = self.bridge.read_sensors()
            
            if zone == "all":
                return {
                    "success": True,
                    "zones": sensor_data.get("zones", {}),
                    "timestamp": sensor_data.get("timestamp", ""),
                    "outdoor_temp_c": sensor_data.get("outdoor_temp_c", None)
                }
            else:
                zones = sensor_data.get("zones", {})
                if zone in zones:
                    return {
                        "success": True,
                        "zone": zone,
                        **zones[zone],
                        "timestamp": sensor_data.get("timestamp", "")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Zone '{zone}' not found. Available zones: {list(zones.keys())}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read zone status: {str(e)}"
            }
    
    def _set_cooling_setpoint(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Set cooling setpoint via bridge."""
        zone = args.get("zone")
        value = args.get("value")
        
        if zone is None or value is None:
            return {
                "success": False,
                "error": "Missing required arguments: zone, value"
            }
        
        # Validate range
        if value < 18 or value > 30:
            return {
                "success": False,
                "error": f"Cooling setpoint {value}°C out of range (18-30°C)"
            }
        
        try:
            self.bridge.write_actuators({
                f"{zone}_cooling_setpoint": value
            })
            return {
                "success": True,
                "message": f"Set {zone} cooling setpoint to {value}°C",
                "zone": zone,
                "new_setpoint_c": value
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to set cooling setpoint: {str(e)}"
            }
    
    def _set_heating_setpoint(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Set heating setpoint via bridge."""
        zone = args.get("zone")
        value = args.get("value")
        
        if zone is None or value is None:
            return {
                "success": False,
                "error": "Missing required arguments: zone, value"
            }
        
        # Validate range
        if value < 15 or value > 26:
            return {
                "success": False,
                "error": f"Heating setpoint {value}°C out of range (15-26°C)"
            }
        
        try:
            self.bridge.write_actuators({
                f"{zone}_heating_setpoint": value
            })
            return {
                "success": True,
                "message": f"Set {zone} heating setpoint to {value}°C",
                "zone": zone,
                "new_setpoint_c": value
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to set heating setpoint: {str(e)}"
            }
    
    def _get_recent_log_errors(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Parse recent lines from EnergyPlus error log."""
        lines = args.get("lines", 50)
        
        if not self.log_file_path:
            return {
                "success": False,
                "error": "Error log path not configured"
            }
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read last N lines
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
            # Filter for warnings and errors
            errors = []
            warnings = []
            for line in recent_lines:
                line_lower = line.lower()
                if '** severe  **' in line_lower or '**  fatal  **' in line_lower:
                    errors.append(line.strip())
                elif '** warning **' in line_lower:
                    warnings.append(line.strip())
            
            return {
                "success": True,
                "errors": errors,
                "warnings": warnings,
                "total_lines_checked": len(recent_lines)
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Error log file not found (simulation may not have started)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read log: {str(e)}"
            }


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return list of tool schemas for LLM function calling."""
    return TOOL_SCHEMAS


def format_tool_call_result(tool_name: str, result: Dict[str, Any]) -> str:
    """
    Format tool execution result as readable string for LLM.
    
    Args:
        tool_name: Name of tool that was called
        result: Result dictionary from tool execution
        
    Returns:
        Formatted string description of result
    """
    if not result.get("success", False):
        return f"❌ {tool_name} failed: {result.get('error', 'Unknown error')}"
    
    if tool_name == "get_zone_status":
        if "zones" in result:
            # Multiple zones
            zone_summaries = []
            for zone_name, zone_data in result["zones"].items():
                zone_summaries.append(
                    f"{zone_name}: {zone_data.get('temperature_c', '?')}°C "
                    f"(setpoints: {zone_data.get('heating_setpoint_c', '?')}-{zone_data.get('cooling_setpoint_c', '?')}°C, "
                    f"PMV: {zone_data.get('pmv', '?')}, "
                    f"HVAC: {zone_data.get('hvac_power_kw', '?')} kW)"
                )
            return "✓ Zone status:\n" + "\n".join(zone_summaries)
        else:
            # Single zone
            return (
                f"✓ {result.get('zone', 'Zone')}: {result.get('temperature_c', '?')}°C, "
                f"PMV: {result.get('pmv', '?')}, "
                f"HVAC: {result.get('hvac_power_kw', '?')} kW"
            )
    
    elif tool_name in ["set_cooling_setpoint", "set_heating_setpoint"]:
        return f"✓ {result.get('message', 'Setpoint updated')}"
    
    elif tool_name == "get_recent_log_errors":
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])
        if not errors and not warnings:
            return "✓ No recent errors or warnings in log"
        else:
            msg = f"✓ Found {len(errors)} error(s), {len(warnings)} warning(s)\n"
            if errors:
                msg += "Errors: " + "; ".join(errors[:3])  # Show first 3
            if warnings:
                msg += "\nWarnings: " + "; ".join(warnings[:3])
            return msg
    
    return f"✓ {tool_name} completed"
