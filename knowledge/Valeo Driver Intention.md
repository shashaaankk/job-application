---
type: project
level: working
last-used: 2024-12
evidence: user account 2026-08-27, full story of the Valeo working-student project
cv-ready: true
---
# Valeo Driver Intention (Working Student, Jul 2024 - Dec 2024)

Problem, in his words. L2+ ADAS acceptance. The driver feels in control doing something and the system does something else, so drivers keep lane keeping switched off. Team was lateral functions, lane keeping and lane centering.

- Scenario evidence gathered first. Example, a heavy truck in the adjacent lane. Drivers deliberately offset toward the free side while no traffic passes; the system pushing them back toward the truck at the slightest overshoot causes discomfort. The opposite case, drowsy or console-distracted drift, is exactly where the system must intervene. If the driver has switched it off out of annoyance, it cannot save them.
- Goal therefore was to sense driver intention and modulate engagement, slightly less strict when the scenario is favorable, fully active on unintended drift.
- He had NO access to a driver monitoring system. Prediction is from vehicle dynamics signals alone.
- The company and partners ran a driver study on the FKFS driving simulator in Stuttgart; drivers' responses and patterns were studied. His use cases and scenarios fed that study.
- He built a Hidden Markov Model that classifies a lane departure as intended or unintended, essentially a two-way confusion-matrix problem, at about **68% precision** without DMS. Recall was about **53%** on a test total of 128 (user-stated 2026-08-27, superseding an earlier uncertain 46). Recall stays OFF the CV; it is interview material only, defended as errors biasing toward intervention, the safe side. User confirmed 2026-08-27 the missed class WAS intended departures read as unintended, so the defense is valid. Never claim F1 or "accuracy".
- No baseline model existed for the use case; heuristics were developed in parallel by others. Never claim "beat a baseline".
- Data work was his. Defined use cases, test scenarios and data acquisition strategies, went on real test drives, built a labeling tool for driving patterns (in Qt/QML, user-stated 2026-10-14), built the ML pipeline that cleans, transforms and integrates CAN traces.
- The model did NOT forecast ahead in time. Forecasting was the planned next step before the position ended in budget cuts. Never claim prediction-in-advance.

## Qt tooling (user-stated 2026-10-14, cv-ready)
The study tooling he built at Valeo, including the driving-pattern labeling tool, was written with Qt, specifically QML (user correction 2026-10-14). The CV bullet "developed Qt-tools for driver studies on test tracks and simulators" is backed by this. QML is the skills-line term he chose; Qt is also accurate.

Letter material, not bullet material. The acceptance story, drivers disabling the system, intention sensing as the path to systems people actually leave on.

## Scenario scope (user correction 2026-10-15)
The heavy truck case is ONE scenario among several in which the system fought a deliberate manoeuvre. Trust and takeover delay were the common pain points behind driver non-acceptance. A letter shows the truck case as one example of several and never as the whole study.

NOT evidenced. Recall number, any baseline comparison, any forecasting horizon, DMS work.
Links: [[Sensor Fusion]]
