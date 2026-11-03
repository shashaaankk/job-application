---
type: skill
level: working
last-used: 2025-05
evidence: distributed PID control on ESP32 nodes under FreeRTOS, Ball-Balancing Robot
cv-ready: true
---
# Real-Time Control
PID control with inverse kinematics distributed across ESP32 nodes under [[FreeRTOS]], with sensing and actuation scheduled at 2 and 4 milliseconds. See [[Ball-Balancing Robot]].

Scope. Those periods are configured and enforced by `vTaskDelayUntil`. No loop execution time was measured, so the claim is that the loops are scheduled at those periods and never that they ran within them.
