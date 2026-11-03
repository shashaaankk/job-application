---
type: project
level: strong
last-used: 2025-05
evidence: IPVS research project, Uni Stuttgart
cv-ready: true
---
# Ball-Balancing Robot (5G Delay in Networked Control)
Distributed control on ESP32/[[FreeRTOS]]; UDP sockets between sensor/compute/actuator nodes; sub-10ms C++ loops; latency measurement under injected impairments (stable at 5–7ms).
Links: [[C++]], [[Real-Time Control]]

## Interface evidence (repo-verified 2026-08-25, cv-ready)
Verified by reading the code in github.com/shashaaankk/RP-Ball-Balancing-Robot (local checkout /home/shashaank/M.Sc/Research_Project/WS_24BallBalacingRobot), prompted by the stenon card question and his answer that the ESP32 nodes used UART.
- Hardware UART on ESP32: `HardwareSerial DynamixelSerial(2)` in main.cpp; motor.cpp writes and reads Dynamixel command packets over Serial1 with explicit rx/tx pins and baudrate. Claimable as direct UART peripheral work on ESP32.
- Direct GPIO and ADC: trackpad.cpp drives the resistive touchpad pins with pinMode, digitalWrite, INPUT_PULLDOWN and analogRead to alternate excitation and measurement axes.
- Ethernet PHY: utils.cpp brings up a LAN8720 over the ESP32 ETH driver; UDP packet comms between sensing, compute and actuation nodes.
- Control stack in the same sources: PID controller plus inverse kinematics, FreeRTOS tasks, and a custom network emulator using lock-free single-producer single-consumer ring buffers with stochastic loss and Gaussian jitter (README).
- SPI: NOT present in this repo; SPI stays unattached to a specific board.
He noted 2026-08-25 the READMEs need improving and he will do it.

## Networking evidence (user-stated 2026-07-15, cv-ready)
- Worked on TSN (Time Sensitive Networking) — beyond the coursework line: applied in the research project context.
- Characterized wireless 5G signals on physical hardware within the deterministic networking project (IPVS research project context).
- Tools confirmed by user: gdb and Jupyter Notebook are used working tools (claimable on documents).

## Causality CORRECTED (user-stated 2026-09-15, cv-ready)
The project was DESIGNED to study the characteristics of the network and their effect on distributed control. The robot is the testbed, the apparatus built to serve that study. Never narrate it the other way around, built a robot and then got curious about the network. Letters and CVs present the network study as the purpose and the robot as the instrument.

## Delay figures CORRECTED (repo-verified 2026-09-11, nightly run)
The "stable at 5-7ms" phrasing above is WRONG at source and must not be reused. Verified against
`test_results/evaluation_results/results_summary_onboard_emulator.csv` in the local checkout.
- The sweep tests delay at 0, 5, 10 and 20 ms. At 5 ms the settling probability is 0.9 with 0 of 10 trials falling off. **At 10 ms the result is identical, 0.9 and 0 of 10.** Degradation appears at 20 ms, 0.6 with 3 of 10 falling off.
- No row anywhere produces a boundary at 7 ms. The claimable statement is that control held with no measured degradation through 10 ms of added delay and broke down by 20 ms.
- The 5-7 figure appears to come from the 6GDetCom dataset file names `Emu_D_3_J_4_PL_2` and `Emu_D_6_J_7_PL_5`, and the second of those gave 0.6 with 4 of 10 falling off, which is not stable.

## Emulator scope (repo-verified 2026-09-11)
The network emulator is his own work, Box-Muller Gaussian jitter and an `esp_random()` loss gate in `include/network_emulator.h`. It is an IN-PROCESS FreeRTOS ring buffer, not an injector on the wire. The README states it reproduces an unreliable UDP channel without external networking hardware, and the checked-in configuration is `CFG_STANDALONE 1`, `CFG_DISTRIBUTED 0`, `NW_EMULATOR 1`. Never write that impairments were injected into the real distributed link.

## Loop timing scope (repo-verified 2026-09-11)
`TRKPD_SAMPLE_TIME 2` ms and `MOTOR_SAMPLE_TIME 4` ms in `ball_balancing_robot/include/tasks.h` are CONFIGURED periods enforced by `vTaskDelayUntil`. No loop-execution-time measurement exists in the repo, so "ran under 10ms" overstates. Say the loops are scheduled at 2 and 4 ms. Separately, the `Tc` column in the results CSV is mean SETTLING time at 10.6 to 15.7 ms and is easily confused with loop period.
