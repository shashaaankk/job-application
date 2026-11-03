---
type: project
level: working
last-used: 2026-08
evidence: user-supplied project entry 2026-08-03 (authored by user, verbatim technical facts)
cv-ready: true
---
# Autonomous Chess-Playing Robot Arms in Simulation
Stack: Python, MuJoCo, PyTorch, NVIDIA NIM (Llama 3.2), NumPy.

Full perceive-decide-act loop in MuJoCo where two ViperX 6-DoF arms play chess against each other. Overhead camera perception feeds an LLM move engine; closed-form inverse kinematics drives pick-and-place manipulation.

Perception: 13-class CNN piece classifier trained on procedurally generated single-piece renders, 99.6% test accuracy, then fine-tuned on crowded multi-piece scenes with exact labels by construction. Fine-tuning removed full-board misreads in live games.

Manipulation: closed-form IK derived and validated to sub-millimetre accuracy against MuJoCo forward kinematics. Reliable grasping through convex decomposition of piece meshes (CoACD), measured gripper-jaw geometry, and tuned contact damping.

Decision layer: LLM move engine via NVIDIA NIM. Perception output serialized to board-state JSON, prompted for UCI moves, executed under semaphore-based turn-taking, with full game logging for failure forensics.

NOT evidenced: real-robot deployment, ROS integration, learned policies or RL, force/torque control, multi-arm collision planning.

Sizing note (measured 2026-08-03): as a 4-bullet entry this block costs roughly the page space of [[Maze Navigation]] plus the SofDCar entry combined. On the 2-page CV it fits alongside the IMU project when both of those rotate out.

Links: [[Maze Navigation]], [[Sensor Fusion]], [[Master Thesis]]

## Repo verification 2026-09-11 (nightly critic, /home/shashaank/Projects/robot-chess)
CONFIRMED his own derivation. `solve_ik` in `src/play_chess.py` lines 189-245 derives the closed-form solution from the ALOHA link geometry using the law of cosines, including a `BETA` correction for the bend in the upper arm. Claim the derivation freely.

**UNVERIFIED: the sub-millimetre validation.** Nothing in the repo computes an IK-versus-FK residual. There is no test directory, no tolerance constant, and the only uses of `site_xpos` are pose caching in `fetch_joint_positions` and a piece-placement distance check in `setup_board.py:159`. The nearest constant is `TIP_CLEAR = 0.001` m of fingertip clearance in `play_chess.py:59`, which is a design clearance and not a measured error. The "validated to sub-millimetre accuracy against MuJoCo forward kinematics" line above is user-supplied and not repo-backed, and it is currently on the CV bullet in every variant. **Do not restate it in letters until Shashank confirms where the number came from.** Asked on the Manipulator Control and Trajectory Planning card, 2026-09-11.
