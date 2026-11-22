# predictive-maintenance

Experiments in predictive maintenance: detecting machine faults from sensor data
before they cause a breakdown. The focus is on comparing classic signal processing
(domain knowledge) with machine learning, and on understanding when each one wins.

| # | Project | Signal | Methods |
|---|---------|--------|---------|
| 01 | [Bearing vibration](01-bearing-vibration/) | Acceleration (synthetic, real data planned) | RMS, envelope spectrum, autoencoder |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
