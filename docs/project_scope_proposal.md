# Project Scope And Research Proposal

## Project Context

This project is part of a Seminar research effort at William Paterson University focused on autonomous driving systems. The current research team includes:

- Dylan Weaver
- Michael
- Shan

The project also connects strongly with Dylan Weaver's broader interest in artificial intelligence, machine learning, embedded systems, and long-term graduate research.

## Proposal Title

**Simulation to Real-World Autonomous Vehicles with Collision Avoidance and Mesh Networking**

## Current Research Goal

The current goal of this project is to build a practical autonomous driving research pipeline that begins in simulation and gradually moves toward small-scale real-world testing.

In simple terms, the project is intended to:

1. Train autonomous driving behavior in simulation.
2. Collect and organize driving data at scale.
3. Test learned models in closed-loop simulation.
4. Develop a safe path toward small-scale physical deployment.
5. Expand into connected multi-vehicle collision avoidance using shared telemetry.

## Core Research Objective

The main objective is to reduce the gap between simulation and physical deployment while building a scalable research platform for connected autonomous systems.

This means the project is not only about making one vehicle drive in CARLA. It is also about building a long-term research foundation for:

- sim-to-real transfer
- collision avoidance
- connected vehicle coordination
- safe testing workflows
- multi-agent intelligence

## Current Scope Of Work

The current scope of the project is centered on the simulation phase and the supporting software pipeline.

That includes:

- CARLA-based autonomous driving experiments
- Python-based control and training workflows
- behavior cloning with PyTorch
- data collection from camera and vehicle state
- replay and inference in simulation
- telemetry sharing and central coordination prototypes

At the current stage, the repository is being used as the main software foundation for:

- collecting sensor data
- training driving models
- testing those models in simulation
- exploring cooperative collision awareness through shared vehicle state

## Simulation-Based Training Scope

The first structured phase of the research uses the CARLA simulator as the main development and training environment.

CARLA is being used to support:

- lane following
- steering prediction
- throttle prediction
- brake prediction
- speed regulation
- collision-aware multi-vehicle experimentation

The initial model-training approach is based on an end-to-end convolutional neural network in PyTorch using:

- camera images
- steering labels
- throttle labels
- brake labels
- vehicle speed and state information

To improve generalization, the broader proposed training strategy includes domain randomization such as:

- lighting variation
- road texture changes
- tire friction variation
- sensor noise
- camera blur

## Planned Transition To Physical Testing

The long-term goal is not to stay only in simulation. The planned next stage is a small-scale real-world autonomous vehicle platform, likely based on a 1/10 or 1/8 scale RC chassis.

The proposed physical platform would include:

- embedded Linux compute such as Jetson Nano or Orin Nano
- camera system
- IMU
- wheel encoders
- steering and motor control interface

This physical platform is intended to serve as a lower-risk and lower-cost bridge between CARLA and real-world autonomy.

## Guardian Safety Layer

Before full autonomy is trusted on a physical vehicle, the first real-world milestone is planned to be a crash-avoidance guardian layer.

In that phase:

- a human driver would still keep manual control
- the AI system would monitor the environment continuously
- if a collision risk becomes too high, the system would override unsafe input

The intervention could include:

- throttle cut
- braking
- minimal steering correction

This guardian-layer approach is important because it:

- reduces the risk of hardware damage
- supports safer real-world data collection
- creates measurable safety metrics
- mirrors real-world automotive safety-system development

Planned evaluation metrics include:

- collision rate before and after guardian mode
- false intervention rate
- reaction latency
- near-miss frequency

## Multi-Vehicle Mesh Networking Scope

After validating single-vehicle performance, the long-term research goal is to expand into a multi-agent autonomous vehicle system.

In that stage, multiple vehicles would share state information through a central or distributed coordination layer.

Each vehicle would broadcast data such as:

- position
- velocity
- heading
- short-horizon trajectory estimate

The coordination layer would then:

- aggregate vehicle states
- detect possible conflicts
- estimate collision probability
- issue corrective actions or advisories when needed

If communication is lost, each vehicle should still operate locally with onboard perception. When communication is available, shared awareness should improve safety and coordination.

This makes the project relevant to:

- intelligent transportation systems
- connected autonomous vehicles
- cooperative perception
- distributed control

## Current Research Questions

The project is intended to support research questions such as:

- How well do driving models trained in CARLA transfer to physical small-scale vehicles?
- How much does shared telemetry improve collision awareness compared with local-only driving?
- How does communication latency affect safety performance?
- How does the system scale as more vehicles are added?
- Can cooperative awareness compensate for perception uncertainty?

## Infrastructure And Resource Needs

To support the broader scope of this work, the project proposal includes the need for:

- a Linux-based workstation
- at least an NVIDIA RTX 2070-class GPU with 8 GB VRAM or better
- access to computational resources on and off campus
- funding for small-scale vehicle platforms
- funding for embedded systems and sensor hardware

Linux is preferred in the formal proposal because it aligns well with:

- CARLA support
- CUDA workflows
- robotics tooling
- embedded Jetson deployment

## Continuation Beyond This Seminar

This project is not intended to end with the current Seminar course.

The planned continuation is to develop the work further into graduate-level research at William Paterson University. The current repository should be viewed as the beginning of a larger research program rather than a finished final product.

The longer-term continuation is expected to expand into areas such as:

- perception modeling
- sensor fusion
- reinforcement learning for control systems
- sim-to-real transfer methods
- guardian safety systems
- cooperative multi-vehicle control
- mesh networking protocols for collision avoidance

## What This Repository Represents Today

Today, this repository represents:

- the software base for CARLA experimentation
- the first practical self-driving data pipeline
- an initial training and inference workflow
- a prototype coordination layer for shared telemetry
- a foundation for future simulation and physical testing

## What This Repository Is Intended To Become

Over time, the intended direction is for this repository and its related research outputs to grow into:

- a complete seminar research platform
- a safer sim-to-real transition workflow
- a small-scale real-world autonomous vehicle testbed
- a multi-vehicle cooperative collision-avoidance system
- a longer-term graduate research foundation
