---
type: skill
level: working
last-used: 2025-10
evidence: IMU project (Kalman/Madgwick/complementary, Allan deviation); Continental radar+IMU prototype; Valeo HMM
cv-ready: true
---
# Sensor Fusion
Hand-implemented Kalman filter with gyro-bias estimation on nRF52840; Allan deviation noise characterization; hard/soft-iron mag calibration. Radar+IMU motion compensation at [[Continental ADAS]]. Driver-intention HMM at Valeo (60%+ accuracy from vehicle dynamics signals).

## Repo verification 2026-09-11 (nightly critic, /home/shashaank/Projects/imu)
- The Allan deviation characterisation and the filter comparison are SEPARATE pieces of work and must never be causally chained. No Allan-derived quantity feeds any filter. The Kalman noise terms are stock, `_Qangle = 0.001f`, `_Qbias = 0.003f`, `_Rmeasure = 0.03f` in `include/orientation-kalman.h`, commented "Tune for responsiveness vs smoothness"; the complementary filter uses `alpha = 0.98f` and Madgwick `beta = 0.1f`. The Allan capture is `output/v1.0-static-imu-log/` and the filter run is `output/v5.0-serial-plotter/`.
- All three estimators DID consume identical samples. `output/v5.0-serial-plotter/run03.csv` carries `comp_*`, `kal_*` and `mad_*` columns over roughly 60,000 rows. But **no comparison result exists**, no error metric, no reference attitude, no plot, no verdict. The three yaw estimates disagree by roughly fifteen degrees with no ground truth. Claim the shared input, never a comparison outcome.
- The Kalman implementation follows TKJElectronics, named in the header comment at `include/orientation-kalman.h:7`. He wrote the code, so "implemented" holds; "derived myself" does not. The gyro bias state `[angle, gyro_bias]` applied in the prediction step is real.
- Magnetometer hard and soft iron: he ran the capture and applied the correction, but the offsets and matrix in `include/magnetometer.h` came from the PJRC MotionCal GUI, which ships in the repo root. No ellipsoid fit of his own. Say he ran and applied the calibration, not that he fitted it.
