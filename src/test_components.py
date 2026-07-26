"""
Component testing script.

Tests individual components without requiring full EnergyPlus simulation.
"""

import sys
from pathlib import Path

print("=" * 60)
print("Eco-Loop Building Agents - Component Test")
print("=" * 60)
print()

# Test 1: EnergyPlus Bridge
print("Test 1: EnergyPlus Bridge")
print("-" * 60)
try:
    from energyplus_bridge import test_bridge
    test_bridge()
    print("✓ Bridge test PASSED\n")
except Exception as e:
    print(f"❌ Bridge test FAILED: {e}\n")
    sys.exit(1)

# Test 2: Tools
print("Test 2: Tool Definitions")
print("-" * 60)
try:
    from tools import get_tool_schemas, ToolExecutor, TOOL_SCHEMAS
    
    schemas = get_tool_schemas()
    print(f"✓ Loaded {len(schemas)} tool schemas")
    
    for schema in schemas:
        func = schema.get("function", {})
        print(f"  - {func.get('name', 'unknown')}: {func.get('description', '')[:50]}...")
    
    print("✓ Tool definitions test PASSED\n")
except Exception as e:
    print(f"❌ Tool definitions test FAILED: {e}\n")
    sys.exit(1)

# Test 3: LLM Agent
print("Test 3: LLM Agent")
print("-" * 60)
try:
    from llm_agent import test_agent
    test_agent()
    print("✓ LLM agent test PASSED\n")
except Exception as e:
    print(f"❌ LLM agent test FAILED: {e}")
    print("   This is expected if Ollama is not running")
    print("   Start Ollama and run: ollama pull qwen2.5:7b-instruct\n")

# Test 4: File Checks
print("Test 4: Required Files")
print("-" * 60)

script_dir = Path(__file__).parent
project_dir = script_dir.parent

files_to_check = [
    ("IDF file", project_dir / "models" / "SmallOffice_EMS.idf"),
    ("Baseline IDF", project_dir / "models" / "SmallOffice_Baseline.idf"),
    ("Weather file", project_dir / "models" / "Chicago.epw"),
]

all_files_exist = True
for name, path in files_to_check:
    if path.exists():
        print(f"✓ {name}: {path}")
    else:
        print(f"❌ {name} NOT FOUND: {path}")
        all_files_exist = False

if all_files_exist:
    print("\n✓ All required files present\n")
else:
    print("\n❌ Some files missing. Please check installation.\n")

# Test 5: Dependencies
print("Test 5: Python Dependencies")
print("-" * 60)

deps = [
    ("requests", "HTTP client for Ollama"),
    ("pandas", "Data analysis"),
    ("matplotlib", "Plotting"),
    ("seaborn", "Visualization"),
    ("numpy", "Numerical computing")
]

print("Note: pyenergyplus is bundled with EnergyPlus (not a pip package)\n")

missing_deps = []
for module_name, description in deps:
    try:
        __import__(module_name)
        print(f"✓ {module_name}: {description}")
    except ImportError:
        print(f"❌ {module_name}: NOT INSTALLED ({description})")
        missing_deps.append(module_name)

if missing_deps:
    print(f"\n❌ Missing {len(missing_deps)} dependencies")
    print(f"   Run: pip install {' '.join(missing_deps)}\n")
else:
    print("\n✓ All dependencies installed\n")

# Summary
print("=" * 60)
if all_files_exist and not missing_deps:
    print("✓ ALL TESTS PASSED - Ready to run simulations!")
    print("  Run: python src/orchestrator.py --days 1 --verbose")
else:
    print("⚠ SOME TESTS FAILED - Please fix issues above")
print("=" * 60)
