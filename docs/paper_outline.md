# Evaluating Shared Telemetry for Cooperative Collision Awareness in a CARLA-Based Autonomous Driving System

## Thesis Statement

Shared fleet telemetry can improve collision awareness in multi-vehicle autonomous driving by giving each vehicle access to nearby vehicle state and predicted path information beyond local sensing alone.

## 1. Abstract

- Summarize the autonomous driving safety problem.
- State the limitation of local-only vehicle awareness.
- Introduce the proposed telemetry-assisted coordination system.
- Mention the CARLA simulation environment.
- State the evaluation method: local-only driving vs telemetry-assisted driving.
- Briefly list the main metrics: collision count, near-collision count, path conflict detection, and route completion.
- End with the main conclusion of the study.

## 2. Introduction

- Introduce autonomous driving and the importance of safe vehicle interaction.
- Explain that collision avoidance becomes harder in multi-vehicle environments.
- Discuss the limits of onboard sensing such as range, occlusion, and delayed awareness.
- Introduce the idea of shared telemetry for cooperative awareness.
- Present CARLA as the simulation platform used in the project.
- End with the purpose of the paper.

## 3. Problem Statement

- Define the central problem: local-only autonomous vehicles may not have enough information to anticipate nearby traffic conflicts.
- Explain why this matters in dense traffic, merging, intersections, and multi-agent environments.
- State the practical consequence: collisions or unsafe decisions may occur before local sensing alone can react.
- Conclude with the exact problem addressed by the project.

## 4. Research Questions and Hypothesis

### Research Questions

1. Does shared vehicle telemetry improve collision awareness compared with local-only driving?
2. Does predicted-path sharing improve safety more than sharing only current state?
3. How sensitive is the system to delayed or stale telemetry?
4. Does a centralized coordinator reduce unsafe interactions in multi-vehicle CARLA scenarios?

### Hypothesis

- Telemetry-assisted coordination will reduce collisions and near-collisions compared with local-only autonomous driving in CARLA.

## 5. Background and Related Concepts

- Briefly explain CARLA as an autonomous driving simulator.
- Define behavior cloning and why it is used in this project.
- Define telemetry in the context of autonomous vehicles.
- Explain centralized coordination and collision advisory generation.
- Introduce the concept of cooperative collision awareness.

## 6. System Overview

- Describe the complete system pipeline from simulation to evaluation.
- Explain that the project supports:
  - simulation startup
  - dataset collection
  - model training
  - closed-loop inference
  - telemetry publishing
  - central coordination
  - collision advisory generation
- Briefly explain how these parts connect.

## 7. System Design and UML Summary

- Use the UML package to explain the design.
- Identify the main actors:
  - Project Developer / Researcher
  - Simulation Runtime
  - Central Fleet Database
  - Other Fleet Vehicles
- Identify the main use cases:
  - Configure / Start Simulation
  - Collect Sensor Dataset
  - Train Driving Model
  - Run Autonomous Drive
  - Publish Vehicle Telemetry
  - Receive Collision Advisory
  - Store Episode Logs and Metrics
- Explain the most important classes:
  - SimulationConfig
  - SimulatorClient
  - CarlaSimulatorClient
  - MockSimulatorClient
  - DrivingObservation
  - ModelController
  - EpisodeRecorder
  - DrivingDataset
  - DrivingModel
  - FleetMessage
  - FleetCoordinator

## 8. Methodology

- Explain how the system will be evaluated.
- Define the two experiment conditions:
  - local-only driving
  - telemetry-assisted driving
- Describe the scenarios to be tested:
  - straight path interaction
  - intersection crossing
  - path overlap
  - multi-vehicle proximity
- Explain how repeated runs will be used for comparison.

## 9. Implementation

- Describe how the project is implemented in code.
- Explain the command pipeline:
  - collect
  - train
  - infer
  - serve
- Describe the central telemetry server and SQLite storage.
- Explain how telemetry messages are generated and consumed.
- Explain how alerts are returned to the client.

## 10. Experimental Setup

- Specify the software environment.
- Specify Python version and major dependencies.
- Specify CARLA configuration if the CARLA backend is used.
- Define:
  - number of vehicles
  - number of runs
  - number of training epochs
  - dataset size
  - route or scenario settings
- State how results will be recorded and compared.

## 11. Evaluation Metrics

- Collision count
- Near-collision count
- Route completion success
- Number of generated advisories
- Timing of advisory response
- Predicted path conflict detection rate

## 12. Results

- Present the outcomes for local-only driving.
- Present the outcomes for telemetry-assisted driving.
- Compare both conditions using tables or figures.
- Show whether telemetry reduced collisions or improved route completion.
- Keep this section factual before interpretation.

## 13. Discussion

- Explain what the results mean.
- Discuss whether shared telemetry improved collision awareness.
- Analyze when telemetry helped the most.
- Discuss where the system remained limited.
- Explain the impact of stale data or missing messages.
- Discuss the strength and weakness of centralized coordination.

## 14. Limitations

- The current driving model is simplified.
- Data quality depends on the collection controller.
- Advisory output is not yet deeply fused into steering or braking.
- Simulation results may not fully transfer to real-world vehicles.
- Centralized coordination introduces dependency on communication reliability.

## 15. Future Work

- Use a stronger teacher driver for CARLA data collection.
- Expand the system to more realistic multi-agent scenarios.
- Add network delay and packet-loss simulation.
- Compare centralized coordination with decentralized or mesh coordination.
- Integrate advisory output directly into vehicle control.
- Evaluate larger-scale fleet interactions.

## 16. Conclusion

- Restate the problem.
- Summarize the proposed system.
- Answer the research question based on the results.
- State whether shared telemetry improved collision awareness in the CARLA-based system.
- End with the broader significance of cooperative autonomous driving.

## 17. Suggested Figures

- System architecture diagram
- Use case diagram
- Static relationship diagram
- Communication diagram for telemetry flow
- Experimental comparison chart

## 18. Suggested Tables

- Project components and responsibilities
- Scenario definitions
- Evaluation metrics
- Experimental results summary

## 19. Key Problem Statement

Autonomous vehicles relying only on local perception may lack sufficient awareness of nearby vehicles in multi-agent environments, motivating the use of shared telemetry for cooperative collision awareness.

## 20. Key Research Objective

This project evaluates whether centralized sharing of fleet telemetry improves collision awareness and safety performance in a CARLA-based autonomous driving system.
