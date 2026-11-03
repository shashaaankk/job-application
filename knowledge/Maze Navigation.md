---
type: project
level: working
last-used: 2026-07
evidence: repo ~/Projects/rl-turtlebot-maze + ~/turtlebot3_ws/src/maze_world (slam_toolbox.yaml, nav2_params.yaml verified 2026-07-21); user-stated status 2026-07-21
cv-ready: true
---
# Maze Navigation with TurtleBot3 (ongoing)
Gazebo Harmonic simulation of TB3 Waffle in generated maze worlds ([[ROS2]] Jazzy, ros_gz bridging of cmd_vel/odom/clock). slam_toolbox integrated for online 2D mapping and localization. Diagnosed and fixed floor-friction fault that immobilized the robot (mu/slip tuning in world SDF). Maze generator scripts (DFS).
CORRECTED 2026-09-11 (nightly run, repo-verified against /home/shashaank/Projects/rl-turtlebot-maze). The 2026-07-21 user-stated plan of "Nav2 integration plus an LLM-based high-level navigator for mapless solving" is SUPERSEDED by his own design notes two days later and must not be claimed. vault/ideas/idea-001__2026-07-23.md states that under perceptual aliasing no single-observation recognizer, "descriptor, scene graph, or LLM", can disambiguate look-alike places, and vault/sessions/2026-07-23-11-43-55.md records scene-graph and LLM place recognition as rejected for this environment. The design is map-based, not mapless. Nav2 exists only in the superseded /home/shashaank/turtlebot3_ws/src/maze_world tree, not in the active repo.

ACTUAL current direction (cv-ready, from idea-001 and idea-002): multi-hypothesis deferred loop-closure verification for aliased mazes. Loop closure reframed as re-localization against the robot's own partial map under a multimodal belief. Four ordered mechanisms, an odometry gate that spawns hypotheses only when disagreement is explainable by accumulated drift on a chi-square test, free-space contradiction as the killer using the negative information in each lidar ray, a backward audit requiring a hypothesis to explain the traversed route in order, and a forward deferred SPRT-style test over map-predicted scans. An edge enters the pose graph only when one hypothesis survives and crosses a high evidence threshold. Grounded in full-text reads of ROVER (arXiv 2508.13488), Seq-SPRT (arXiv 2512.09447), SGLC (arXiv 2407.08106) and BoWG (arXiv 2510.22529).

STALENESS NOTE: newest project file dates to 2026-07-25 and the design notes to 2026-07-23, so "ongoing" is accurate only if he has resumed. Present-progressive bullets should be checked with him before the next variant.
NOT evidenced: completed autonomous navigation, fleet concepts, VDA5050, real-robot deployment.
Links: [[ROS2]]
