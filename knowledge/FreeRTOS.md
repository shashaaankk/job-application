---
type: skill
level: working
last-used: 2025-05
evidence: Ball-Balancing Robot research project (ESP32/FreeRTOS distributed control)
cv-ready: true
---
# FreeRTOS
Distributed control system on ESP32 and FreeRTOS nodes, with UDP inter-node comms and sensing and actuation tasks scheduled at 2 and 4 milliseconds. See [[Ball-Balancing Robot]] and [[Real-Time Control]].

Corrected here. The earlier wording said sub-10ms real-time loops, which the project note's repo verification rejects, since the periods are configured by `vTaskDelayUntil` and no execution time was ever measured.
