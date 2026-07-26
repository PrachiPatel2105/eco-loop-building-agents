"""
LLM Agent: Ollama-based building control agent with function calling.

Manages communication with local Ollama server, handles tool calling,
and implements the control logic prompt.
"""

import json
import time
import requests
from typing import Dict, List, Any, Optional, Tuple
from collections import deque


class LLMAgent:
    """
    LLM-based building control agent using Ollama for local inference.
    
    Handles:
    - System prompt for building control objectives
    - Tool calling with structured function schemas
    - Context management for long simulation runs
    - Error handling and retries
    """
    
    def __init__(self, 
                 model: str = "qwen2.5:7b-instruct",
                 ollama_url: str = "http://localhost:11434",
                 tool_schemas: Optional[List[Dict]] = None,
                 comfort_bounds: Tuple[float, float] = (20.0, 24.0),
                 pmv_bounds: Tuple[float, float] = (-0.5, 0.5)):
        """
        Initialize LLM agent.
        
        Args:
            model: Ollama model name (must support function calling)
            ollama_url: Ollama API endpoint
            tool_schemas: List of tool definitions for function calling
            comfort_bounds: (min_temp_c, max_temp_c) for comfort
            pmv_bounds: (min_pmv, max_pmv) for comfort
        """
        self.model = model
        self.ollama_url = ollama_url
        self.tool_schemas = tool_schemas or []
        self.comfort_bounds = comfort_bounds
        self.pmv_bounds = pmv_bounds
        
        # Context management
        self.state_history = deque(maxlen=100)  # Keep last 100 state readings
        self.action_history = deque(maxlen=50)   # Keep last 50 actions
        
        # System prompt
        self.system_prompt = self._build_system_prompt()
        
        # Verify Ollama connection
        self._verify_connection()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt encoding control objectives."""
        return f"""You are an AI building energy manager controlling a small office building through an EnergyPlus simulation.

OBJECTIVES (in priority order):
1. **Maintain thermal comfort**: Keep zones within comfortable temperature range ({self.comfort_bounds[0]}-{self.comfort_bounds[1]}°C) and PMV between {self.pmv_bounds[0]} and {self.pmv_bounds[1]}
2. **Minimize energy consumption**: Reduce HVAC load when comfort allows
3. **Avoid aggressive changes**: Prefer gradual adjustments (0.5-1°C steps) over large jumps
4. **Peak demand management**: Be aware of total building energy use

CONTROL STRATEGY - YOU MUST ACTIVELY CONTROL SETPOINTS:

**PRIORITY 1 - COMFORT VIOLATIONS (Address IMMEDIATELY):**
- If setpoints are 0.0°C: MUST set initial values (heating=20°C, cooling=24°C)
- If zone temperature > {self.comfort_bounds[1]}°C or PMV > {self.pmv_bounds[1]}: LOWER cooling setpoint by 0.5-1°C
- If zone temperature < {self.comfort_bounds[0]}°C or PMV < {self.pmv_bounds[0]}: RAISE heating setpoint by 0.5-1°C

**PRIORITY 2 - ENERGY EFFICIENCY (When comfort is satisfied):**
- **CRITICAL FOR ENERGY SAVINGS**: If zone IS COMFORTABLE (temp in {self.comfort_bounds[0]}-{self.comfort_bounds[1]}°C AND PMV in {self.pmv_bounds[0]}-{self.pmv_bounds[1]}) AND HVAC power > 3.5 kW, you MUST widen the deadband:
  * RAISE cooling setpoint toward 25-26°C (reduces cooling load)
  * LOWER heating setpoint toward 18-19°C (reduces heating load)
  * This maintains comfort while reducing energy consumption
- If zone is comfortable and HVAC power < 2 kW: maintain current setpoints (already efficient)
- Aim for 3-4°C deadband between heating and cooling when possible

**PRIORITY 3 - OPERATIONAL CONSTRAINTS:**
- Maintain minimum 2°C deadband between heating and cooling to avoid simultaneous operation
- Make gradual changes (0.5-1°C steps) unless comfort is severely violated
- Consider outdoor temperature: mild weather allows wider deadbands

CRITICAL INSTRUCTION:
- You MUST call set_cooling_setpoint or set_heating_setpoint whenever conditions warrant adjustment
- Do NOT just call get_zone_status and report - you must TAKE ACTION to control the building
- Every control decision should result in actual setpoint changes when comfort or efficiency can be improved
- If you see setpoints at 0.0°C, this means no control is active - you MUST set them immediately

AVAILABLE TOOLS:
- get_zone_status: Query current zone conditions (temperature, PMV, setpoints, energy use)
- set_cooling_setpoint: Adjust cooling setpoint (zone cools when temp exceeds this value)
- set_heating_setpoint: Adjust heating setpoint (zone heats when temp falls below this value)
- get_recent_log_errors: Check for EnergyPlus errors if controls seem ineffective

REQUIRED RESPONSE FORMAT:
1. ALWAYS start your response with a brief reasoning paragraph explaining:
   - Current comfort status of each zone
   - Whether any control actions are needed and why
   - What setpoint changes you will make (if any)
2. THEN call the appropriate tools to implement your decision

EXAMPLE GOOD RESPONSES:

**Example 1 - Comfort Violation:**
"West Zone is currently 24.5°C with PMV of 0.6, which exceeds the comfort upper bound of 24°C. This indicates the zone is too warm. I will lower the cooling setpoint from 24°C to 23°C to increase cooling and bring temperature back into the comfort range."
[Then call set_cooling_setpoint with zone="West Zone" and value=23.0]

**Example 2 - Energy Efficiency Opportunity:**
"West Zone is comfortable at 21°C with PMV of 0.1, well within bounds. However, HVAC power is 4.2 kW which is high. Since comfort is satisfied, I will widen the deadband to reduce energy: raising cooling setpoint from 24°C to 25.5°C and lowering heating setpoint from 20°C to 19°C. This maintains comfort while reducing HVAC load."
[Then call set_cooling_setpoint with value=25.5 AND set_heating_setpoint with value=19.0]

**Example 3 - Already Optimal:**
"West Zone is comfortable at 22°C with PMV of 0.0, and HVAC power is only 1.8 kW. Current setpoints (heating=19°C, cooling=25°C) are already efficient with a good deadband. No changes needed."
[Call get_zone_status if needed to confirm, but no setpoint changes]

Remember: You are an ACTIVE controller, not a passive monitor. Make setpoint adjustments to maintain comfort and optimize energy."""

    def _verify_connection(self):
        """Verify Ollama server is accessible and model is available."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            response.raise_for_status()
            
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            if not any(self.model in name for name in model_names):
                print(f"⚠ Warning: Model '{self.model}' not found in Ollama.")
                print(f"   Available models: {', '.join(model_names)}")
                print(f"   Run: ollama pull {self.model}")
            else:
                print(f"✓ Ollama connected, model '{self.model}' available")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to Ollama at {self.ollama_url}")
            print(f"   Error: {e}")
            print(f"   Make sure Ollama is running (try: ollama list)")
            raise
    
    def call_with_tools(self, 
                       context: str, 
                       max_retries: int = 3,
                       timeout: int = 120) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Call LLM with current context and tool schemas.
        
        Args:
            context: Current building state description
            max_retries: Number of retry attempts on failure
            timeout: Timeout in seconds per call
            
        Returns:
            Tuple of (reasoning_text, list_of_tool_calls)
            where each tool call is {"name": str, "arguments": dict}
        """
        for attempt in range(max_retries):
            try:
                # Prepare messages
                messages = [
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ]
                
                # Prepare request payload
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for more consistent decisions
                        "num_predict": 1024   # Enough for reasoning + tool calls
                    }
                }
                
                # Add tools if available
                if self.tool_schemas:
                    payload["tools"] = self.tool_schemas
                
                # Make request
                response = requests.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()
                
                result = response.json()
                message = result.get("message", {})
                
                # Extract reasoning text
                reasoning = message.get("content", "")
                
                # Extract tool calls
                tool_calls = message.get("tool_calls", [])
                
                # Parse tool calls into standard format
                parsed_calls = []
                for call in tool_calls:
                    func = call.get("function", {})
                    parsed_calls.append({
                        "name": func.get("name", ""),
                        "arguments": func.get("arguments", {})
                    })
                
                return reasoning, parsed_calls
                
            except requests.exceptions.Timeout:
                print(f"⚠ LLM call timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    return "Error: LLM call timed out after retries", []
                    
            except requests.exceptions.RequestException as e:
                print(f"⚠ LLM call failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return f"Error: LLM call failed: {str(e)}", []
                    
            except Exception as e:
                print(f"❌ Unexpected error in LLM call: {e}")
                return f"Error: {str(e)}", []
        
        return "Error: Max retries exceeded", []
    
    def make_control_decision(self, sensor_data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Make control decision based on current building state.
        
        Args:
            sensor_data: Current sensor readings from bridge
            
        Returns:
            Tuple of (reasoning, tool_calls)
        """
        # Add to state history
        self.state_history.append(sensor_data)
        
        # Build context from recent history
        context = self._build_context(sensor_data)
        
        # Call LLM with tools
        reasoning, tool_calls = self.call_with_tools(context)
        
        # Log action
        self.action_history.append({
            "timestamp": sensor_data.get("timestamp", "unknown"),
            "reasoning": reasoning,
            "tool_calls": tool_calls
        })
        
        return reasoning, tool_calls
    
    def _build_context(self, current_state: Dict[str, Any]) -> str:
        """
        Build context string from current state and recent history.
        
        Summarizes history to fit in token budget while providing
        enough context for informed decisions.
        """
        # Current state (detailed)
        zones = current_state.get("zones", {})
        timestamp = current_state.get("timestamp", "unknown")
        sim_hours = current_state.get("sim_time_hours", 0)
        outdoor_temp = current_state.get("outdoor_temp_c", 0)
        
        context_parts = [
            f"CURRENT TIME: {timestamp} (Simulation hour: {sim_hours:.1f})",
            f"OUTDOOR TEMPERATURE: {outdoor_temp:.1f}°C",
            "",
            "CURRENT ZONE STATUS:"
        ]
        
        total_hvac_kw = 0
        comfort_violations = []
        setpoint_warnings = []
        
        for zone_name, zone_data in zones.items():
            temp = zone_data.get("temperature_c", 0)
            pmv = zone_data.get("pmv", 0)
            hvac_kw = zone_data.get("hvac_power_kw", 0)
            cooling_sp = zone_data.get("cooling_setpoint_c", 0)
            heating_sp = zone_data.get("heating_setpoint_c", 0)
            
            total_hvac_kw += hvac_kw
            
            # Check for uninitialized setpoints
            if cooling_sp == 0.0 and heating_sp == 0.0:
                setpoint_warnings.append(f"{zone_name}: setpoints at 0.0°C - NO CONTROL ACTIVE!")
            
            # Check comfort
            comfort_status = "✓ Comfortable"
            if pmv < self.pmv_bounds[0] or temp < self.comfort_bounds[0]:
                comfort_status = "❌ TOO COLD"
                comfort_violations.append(f"{zone_name}: too cold")
            elif pmv > self.pmv_bounds[1] or temp > self.comfort_bounds[1]:
                comfort_status = "❌ TOO HOT"
                comfort_violations.append(f"{zone_name}: too hot")
            
            context_parts.append(
                f"  • {zone_name}: {temp:.1f}°C (setpoints: heat={heating_sp:.1f}°C, cool={cooling_sp:.1f}°C) | "
                f"PMV={pmv:.2f} | HVAC={hvac_kw:.2f} kW | {comfort_status}"
            )
        
        context_parts.append(f"\nTOTAL BUILDING HVAC LOAD: {total_hvac_kw:.2f} kW")
        
        # Recent history summary (if available)
        if len(self.state_history) > 5:
            context_parts.append("\n--- RECENT TRENDS (last 5 readings) ---")
            
            recent_states = list(self.state_history)[-5:]
            for zone_name in zones.keys():
                temps = [s.get("zones", {}).get(zone_name, {}).get("temperature_c", 0) 
                        for s in recent_states]
                if temps:
                    temp_change = temps[-1] - temps[0]
                    trend = "↑" if temp_change > 0.5 else "↓" if temp_change < -0.5 else "→"
                    context_parts.append(f"  • {zone_name}: {trend} (Δ{temp_change:+.1f}°C over last period)")
        
        # Recent actions summary
        if self.action_history:
            last_action = list(self.action_history)[-1]
            context_parts.append(f"\n--- LAST ACTION ---")
            context_parts.append(f"Reasoning: {last_action.get('reasoning', 'N/A')[:200]}")
            if last_action.get('tool_calls'):
                context_parts.append(f"Tools called: {len(last_action['tool_calls'])}")
        
        # Decision prompt
        context_parts.append("\n--- YOUR TASK ---")
        
        if setpoint_warnings:
            context_parts.append(f"🚨 CRITICAL: {', '.join(setpoint_warnings)}")
            context_parts.append("YOU MUST set initial setpoints immediately (e.g., heating=20°C, cooling=24°C)")
            context_parts.append("")
        
        if comfort_violations:
            context_parts.append(f"⚠ COMFORT VIOLATIONS DETECTED: {', '.join(comfort_violations)}")
            context_parts.append("Priority: Restore comfort while minimizing energy impact.")
        else:
            context_parts.append("All zones comfortable. Assess if energy optimization opportunities exist.")
        
        context_parts.append("\nAnalyze the situation and use tools to query status or adjust setpoints as needed.")
        
        return "\n".join(context_parts)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Return statistics about agent's decision history."""
        total_decisions = len(self.action_history)
        total_tool_calls = sum(len(a.get("tool_calls", [])) for a in self.action_history)
        
        return {
            "total_decisions": total_decisions,
            "total_tool_calls": total_tool_calls,
            "avg_tools_per_decision": total_tool_calls / total_decisions if total_decisions > 0 else 0,
            "state_history_length": len(self.state_history)
        }


def test_agent():
    """Test LLM agent instantiation and Ollama connection."""
    print("Testing LLM Agent...")
    
    try:
        agent = LLMAgent(
            model="qwen2.5:7b-instruct",
            tool_schemas=[
                {
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "A test tool",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                }
            ]
        )
        
        print("✓ Agent initialized successfully")
        print(f"✓ Model: {agent.model}")
        print(f"✓ Tool schemas: {len(agent.tool_schemas)}")
        
        # Test context building with mock data
        mock_data = {
            "timestamp": "2024-01-15 14:00",
            "sim_time_hours": 38,
            "outdoor_temp_c": 5.0,
            "zones": {
                "Core_ZN": {
                    "temperature_c": 23.5,
                    "cooling_setpoint_c": 24.0,
                    "heating_setpoint_c": 20.0,
                    "pmv": 0.2,
                    "hvac_power_kw": 2.5
                }
            }
        }
        
        context = agent._build_context(mock_data)
        print(f"✓ Context building works ({len(context)} chars)")
        
        print("\n✓ Agent test complete")
        
    except Exception as e:
        print(f"❌ Agent test failed: {e}")
        raise


if __name__ == "__main__":
    test_agent()
