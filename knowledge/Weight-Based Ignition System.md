---
type: project
level: working
last-used: unknown
evidence: prior resume (resume/main_de.tex, "IoT Enabled Weight-Based Ignition System" — C, ESP32, Load Cells, IMU, ThingSpeak) + user attestation 2026-07-28
cv-ready: true
---
# IoT Enabled Weight-Based Ignition System
Scale prototype monitoring truck payload in real time with load cells; working ignition interlock that blocks ignition on overload (user-attested 2026-07-28). Fused accelerometer and gyroscope data to estimate vehicle tilt and correct load cell readings feeding the ignition control (user-attested 2026-07-28; NO filter method attested — do not name complementary/Kalman/Madgwick in any document). Remote telemetry via ThingSpeak. Stack: C, ESP32, load cells, IMU, ThingSpeak.
NOT evidenced: timeline (user declined to state), filter method, deployment beyond scale prototype.
METHOD (user chat statement 2026-07-28): "accelerometer + gyroscope, raw accelerometer trigonometry" — tilt estimate computed from accelerometer data via trigonometry. CV bullets use this narrower claim ("estimated tilt from accelerometer data using trigonometry"), not "fused accel and gyro", to stay within the attested method.
NOTE: distinct from [[Sensor Fusion]] (nRF52840 Cortex-M4 estimator-comparison project) — the two must never share bullet wording; the three-estimator comparison, gyro-bias Kalman, and Allan deviation belong exclusively to the Cortex-M4 project. User initially requested merging the two projects (2026-07-28); resolved as two separate entries with this project's own attested fusion work.
Links: [[Sensor Fusion]]
