# 🎬 Quick Start - Video Recording

## 🚀 3-Step Video Recording Setup

### Step 1: Check System Ready
```bash
CHECK_DEMO_READY.bat
```
✅ Ensure all 5 checks pass before recording

### Step 2: Launch Demo Windows
```bash
PREPARE_VIDEO_DEMO.bat
```
Choose option **6** - Launch ALL Demo Windows

### Step 3: Record & Show Results
```bash
VIEW_RESULTS.bat
```
Open all charts and metrics after sims complete

---

## 📊 What You'll See

### Window 1: Component Tests (Blue) - 30 seconds
```
✓ EnergyPlus connection test
✓ LLM agent communication test
✓ Tool execution test
✓ Sensor reading test
```

### Window 2: AI Simulation (Yellow) ⭐ - Main Demo
```
🧠 LLM Decision Point - 1986-01-01 12:00
  West Zone: 22.1°C, PMV=0.05, HVAC=3.45kW

💭 LLM Reasoning:
  "Zone comfortable, but HVAC high. Widening deadband..."

🔧 Executing tool calls:
  ✓ set_cooling_setpoint → 25.0°C
  ✓ set_heating_setpoint → 19.5°C
```

### Window 3: Baseline Simulation (Purple) - Comparison
- Fixed setpoints (no AI control)
- Runs in parallel for comparison

### Window 4: Progress Monitor (Light Blue) - Status
```
Total timesteps: 288
LLM decisions: 12
Estimated completion: 25.0%
```

---

## ⏱️ Recording Timeline

| Time | Action | What to Show |
|------|--------|--------------|
| 0:00-0:30 | Intro | Project overview, architecture |
| 0:30-1:00 | Component Tests | All checks passing |
| 1:00-4:00 | AI Simulation | 2-3 LLM decision cycles |
| 4:00-5:00 | Progress | Monitor status updates |
| 5:00-7:00 | Results | Charts and metrics |
| 7:00-8:00 | Closing | Key achievements |

---

## 🎯 Key Points to Emphasize

1. **Closed-Loop Control** - Live communication, not post-processing
2. **Explainable AI** - Reasoning text for every decision
3. **Tool Calling** - LLM uses tools to control building
4. **Validated Results** - 100% comfort, quantified energy impact
5. **Production-Ready** - Modular, tested, documented

---

## 📸 Best Screenshots for Video

1. **LLM Decision Point** - Full reasoning + tool calls
2. **Energy Comparison Chart** - Cumulative energy over time
3. **Comfort Analysis Chart** - Temperature staying in bounds
4. **Progress Monitor** - Real-time statistics
5. **System Architecture** - Diagram from README

---

## 🎤 Suggested Script (2-minute version)

"This is Eco-Loop Building Agents - where an LLM autonomously controls building HVAC in real-time through EnergyPlus simulation.

[Show component tests]
First, we validate all components - EnergyPlus connection, LLM communication, all passing.

[Show AI simulation]
Now the simulation runs. Every hour the LLM receives sensor data and makes control decisions. Watch this...

[Point to decision]
Here - the LLM reads temperature 22.1°C, PMV 0.05, power 3.45kW. It reasons: 'Zone comfortable but power high' and adjusts setpoints to save energy. This is genuine autonomous control.

[Show results]
After 2 days, the AI maintained 100% comfort while actively managing energy use. Every decision is logged with explainable reasoning.

[Closing]
Production-ready closed-loop AI control for building automation."

---

## 🛠️ Troubleshooting During Recording

| Issue | Quick Fix |
|-------|-----------|
| Component tests fail | Restart Ollama: `ollama serve` |
| LLM too slow | Edit `orchestrator.py`: Set interval to 120 min |
| No charts generated | Run `run_analysis.bat` manually |
| Window colors wrong | Reopen from `PREPARE_VIDEO_DEMO.bat` |

---

## ✅ Pre-Recording Checklist

- [ ] Screen recording software open (OBS, Camtasia, etc.)
- [ ] `CHECK_DEMO_READY.bat` shows 5/5 ready
- [ ] Ollama running: `ollama list` shows qwen2.5:7b-instruct
- [ ] Terminal font size increased for readability
- [ ] Desktop cleared of distractions
- [ ] Audio/microphone tested if doing voiceover

---

## 📝 Post-Recording Checklist

- [ ] Component tests shown
- [ ] At least 2 LLM decisions captured
- [ ] Reasoning text readable
- [ ] Tool calls visible
- [ ] Results charts displayed
- [ ] Performance metrics explained

---

## 🚀 After Recording

1. **Export video** in HD (1080p recommended)
2. **Add to README** - Link from GitHub
3. **Create thumbnail** - Use energy_comparison.png
4. **Share** on LinkedIn, Twitter with key screenshots
5. **Prepare slides** if presenting live

---

## 💡 Pro Tips

- **Zoom terminal font** to 150% for recording (Ctrl + Mouse Wheel)
- **Use dark theme** terminals for better contrast
- **Record in 1920x1080** for best quality
- **Add captions** in post-production for key moments
- **Keep it short** - 5-8 minutes is ideal for demos
- **Show existing results first** if pressed for time

---

**Ready to record? Double-click `PREPARE_VIDEO_DEMO.bat` and let's go! 🎬**

For detailed guidance, see `VIDEO_RECORDING_GUIDE.md`
