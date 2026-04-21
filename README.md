# XPAN Simulation Notes

This repository contains a lightweight Python simulator for studying XPAN earbud behavior across three bearer modes:

- `LE` for normal buds
- `P2P` for direct XPAN earbud-to-phone Wi-Fi
- `WHC` for AP-assisted whole-home coverage

The simulator is intentionally system-level rather than packet-level. The goal is to iterate quickly on handover, coverage, and power-management ideas before moving into a heavier environment.

## How To Use The Simulator

### Requirements

- Python 3.10 or newer
- Run from the repository root so the `sim` package resolves correctly

If you are using the local Python installed in this workspace, the command is:

```bash
/Users/apple/Code/Python/.local/python-3.10.14/bin/python3.10 -m sim.run
```

If `python3.10` is already on your `PATH`, you can use:

```bash
python3.10 -m sim.run
```

Important note:

- Do not run `python sim/run.py` directly. Use `python -m sim.run` from the repo root.

### What The Simulator Runs

The default entrypoint iterates through all built-in combinations of:

- profiles:
  - `normal_buds`
  - `xpan_reactive`
  - `xpan_predictive`
  - `xpan_service_aware`
- scenarios:
  - `walk_away`
  - `body_blockage`
  - `mesh_backhaul_stress`
  - `service_aware_use_cases`
- power strategies:
  - `always_on`
  - `static_twt`
  - `adaptive_twt`
  - `predictive_prewake`

`normal_buds` currently runs only with `always_on`, while the XPAN profiles run across all supported power strategies.

### Reading The Output

For each scenario/profile/strategy combination, the simulator prints a result block that includes:

- topology and policy context:
  - `profile`
  - `scenario`
  - `power_strategy`
  - `initial_link`
  - `handover_target`
  - `service_type`
  - `phone_low_power`
- QoE and link metrics:
  - `average_latency_ms`
  - `packet_loss_rate`
  - `interruptions_ms`
  - `underruns`
  - `average_data_rate_mbps`
  - `peak_data_rate_mbps`
  - `min_active_rssi_dbm`
- handover metrics:
  - `handovers`
  - `cold_switches`
  - `bearer_switch_time_ms`
  - `transition_time_ms`
  - `gap_free`
  - `early_switches`
  - `late_switches`
  - `unnecessary_prewarm_events`
  - `ping_pong_count`
  - `average_prediction_lead_time_ms`
- power metrics:
  - `energy_mj`
  - `average_power_mw`
  - `energy_per_delivered_packet_uj`
  - `le_energy_mj`
  - `p2p_energy_mj`
  - `whc_active_energy_mj`
  - `whc_standby_energy_mj`
  - `overlap_energy_mj`
  - `whc_prewarm_time_ms`
  - `whc_active_time_ms`
  - `overlap_time_ms`
  - `average_awake_ratio`
- KPI verdicts:
  - `kpi_checks`

`kpi_checks` is the quickest way to see whether a given policy meets the simulator's current working targets.

### Main Files To Modify

If you want to extend the simulator, these are the main entry points:

- `sim/environment.py` for scenario design
- `sim/link_models.py` for bearer quality models
- `sim/controller.py` for bearer-selection logic
- `sim/handover.py` for transition behavior
- `sim/power.py` for Wi-Fi power-management policies
- `sim/metrics.py` for new summary metrics
- `sim/config.py` for shared thresholds and constants

### Typical Workflow

1. Adjust a scenario, controller, or model.
2. Run `python3.10 -m sim.run` from the repo root.
3. Compare the output blocks across profiles and power strategies.
4. Check `kpi_checks` first, then inspect latency, handover, and power tradeoffs in more detail.

## Current Summary

What has been built so far:

- A Python-based system-level simulator for XPAN earbud behavior
- Three bearer modes:
  - `LE` for normal buds
  - `P2P` for direct XPAN earbud-to-phone Wi-Fi
  - `WHC` for AP-assisted whole-home coverage
- Three scenario families:
  - `walk_away`
  - `body_blockage`
  - `mesh_backhaul_stress`
- XPAN handover profiles:
  - `xpan_reactive`
  - `xpan_predictive`
- KPI evaluation for:
  - 5 GHz bearer usage
  - end-to-end latency
  - max data rate
  - bearer switch time
  - gap-free switching quality
  - whole-home transition time
  - RSSI
- Richer power accounting:
  - total energy
  - average power
  - energy per delivered packet
  - per-bearer and per-phase energy buckets
  - prewarm/active/overlap timing
- Explicit power strategies:
  - `always_on`
  - `static_twt`
  - `adaptive_twt`
  - `predictive_prewake`
- A service-aware XPAN policy path:
  - voice call prefers `LE`
  - music prefers `P2P`
  - move-away can trigger `P2P -> LE`
  - phone low-power mode can trigger `P2P -> LE`

What the simulator is showing right now:

- `normal_buds` fail the XPAN-style bandwidth, band, and coverage expectations, which is consistent with LE-only behavior.
- `xpan_predictive` performs well in the `walk_away` scenario and can meet the current KPI set.
- `xpan_reactive` tends to suffer cold-switch penalties and fails gap-free handover.
- `body_blockage` exposes that abrupt direct-path collapse is still hard to handle cleanly.
- `mesh_backhaul_stress` exposes that a weak infrastructure path can make WHC available but not truly good enough.
- `static_twt` saves more power but is usually more fragile from a QoE perspective.
- `predictive_prewake` is promising because it often balances power and audio continuity better than static scheduling.
- The new service-aware path makes it possible to study application-driven bearer selection instead of treating every XPAN workload as Wi-Fi-first.

Why this matters:

- We now have a baseline simulator that can support both paper-writing and invention ideation.
- The current failures are useful, because they expose the real technical gaps worth targeting.

## Updated Use Cases

The following use cases refine the XPAN behavior model and are important for the next simulator revision:

1. Voice call

- Earbud is XPAN-capable and `P2P` may remain connected in a low-power idle state
- Active voice-call traffic uses `LE`

Interpretation:

- Voice calls may prefer the lower-power, lower-bandwidth bearer when the traffic profile does not require full Wi-Fi throughput.
- This means XPAN earbuds should not be modeled as "Wi-Fi only." They may keep multiple bearers available and choose traffic routing per service type.

2. Music playback

- Earbud is `P2P` connected
- Music traffic uses `P2P` Wi-Fi

Interpretation:

- High-rate continuous media is a natural fit for direct XPAN Wi-Fi.
- This reinforces that bearer choice should depend on application class, not just radio reachability.

3. Earbud moves away from phone

- Bearer switch from `P2P` to `LE`

Interpretation:

- Distance-based fallback is not only `P2P -> WHC`; there is also a direct `P2P -> LE` fallback path.
- This suggests the simulator should evolve from a simple two-bearer XPAN handover model to a multi-bearer policy model.

4. Low-power mode on phone

- Bearer switch from `P2P` to `LE`

Interpretation:

- Bearer switching can be driven by device power state, not only link degradation.
- This is especially important for a future paper or patent because it introduces policy-driven handover triggered by energy intent.

What these use cases imply for the simulator:

- XPAN earbuds should be modeled with at least three bearer choices:
  - `LE`
  - `P2P`
  - `WHC`
- Bearer selection should depend on:
  - traffic type such as voice call versus music
  - distance and signal quality
  - phone power mode
  - whole-home infrastructure readiness
- Future simulation should support:
  - service-aware routing
  - power-state-aware bearer switching
  - direct `P2P -> LE`
  - direct `P2P -> WHC`
  - possibly `LE -> P2P` return when high-throughput media starts

Why this is valuable:

- It makes the simulator closer to a real product behavior model.
- It creates stronger research and patent opportunities around application-aware and power-aware bearer control.

What has now been implemented from these use cases:

- A `service_aware_use_cases` scenario in the simulator
- A service-aware controller that can choose among `LE`, `P2P`, and `WHC`
- Direct switching support for:
  - `LE -> P2P`
  - `P2P -> LE`
  - `P2P -> WHC`
- KPI handling that treats `LE` as valid during:
  - voice-call operation
  - phone low-power mode

## Change Log

### 2026-04-21: Added short-horizon predictive handover scoring

Why this addition was made:

- Simple threshold-triggered prediction was useful, but it was still too close to reactive behavior.
- To study stronger XPAN handover ideas, the simulator should estimate near-future bearer quality and measure whether prediction is early, late, or wasteful.

What was added:

- A short-horizon quality projection for `P2P` and `WHC`
- Predictive switch-gain scoring in addition to raw degradation risk
- Earlier `WHC` prewarm when the projected whole-home path is expected to outperform direct `P2P`
- New handover-evaluation metrics:
  - `early_switches`
  - `late_switches`
  - `unnecessary_prewarm_events`
  - `ping_pong_count`
  - `average_prediction_lead_time_ms`

Why this matters:

- It lets the simulator ask not only "did we switch?" but "did we switch at the right time?"
- It provides a cleaner bridge toward future hybrid rule-based and ML-based handover research.

### 2026-04-21: Improved handover stability and recovery behavior

Why this addition was made:

- The earlier handover model was mostly threshold-driven and could behave too much like a one-way trigger.
- For XPAN policy work, the simulator should represent not just fallback behavior but also stability, anti-ping-pong behavior, and recovery back to a better bearer.

What was added:

- Minimum active-link dwell time before non-forced bearer changes
- Hysteresis-like hold behavior for return transitions
- Predictive recovery from `WHC -> P2P` when direct link quality clearly improves
- More stable service-aware switching between `LE`, `P2P`, and `WHC`
- Forced immediate switch handling for policy-driven cases such as:
  - voice call preferring `LE`
  - phone low-power mode preferring `LE`

Why this matters:

- It makes bearer transitions look more like a real controller and less like an instantaneous threshold crossing.
- It reduces unrealistic oscillation between bearers.
- It lets the simulator study both degradation-driven fallback and improvement-driven return behavior.

### 2026-04-21: Added richer power measurements

Why this addition was made:

- Total energy alone was not enough to explain why a policy performed better or worse.
- XPAN research will likely need to compare power-saving methods beyond TWT, so the simulator should expose where energy is being spent.
- For paper and patent work, it is useful to separate direct-link energy, WHC standby/prewarm cost, and overlap cost during make-before-break transitions.

What was added:

- Total energy in `mJ`
- Average power in `mW`
- Energy per delivered packet in `uJ`
- Per-component energy buckets:
  - `le_energy_mj`
  - `p2p_energy_mj`
  - `whc_active_energy_mj`
  - `whc_standby_energy_mj`
  - `overlap_energy_mj`
- Time-spent counters:
  - `whc_prewarm_time_ms`
  - `whc_active_time_ms`
  - `overlap_time_ms`

Why these metrics matter:

- `whc_standby_energy_mj` shows the cost of predictive prewarming before a switch.
- `overlap_energy_mj` shows the extra cost of warm, gap-free switching.
- `energy_per_delivered_packet_uj` helps normalize power cost against useful work.
- The time counters make it easier to compare different power-saving strategies later, including TWT, duty-cycling, predictive prewake, and hybrid schemes.

What this enables next:

- Compare static versus adaptive power-saving policies more fairly
- Quantify the cost of gap-free handover
- Study whether a policy improves QoE enough to justify extra standby or overlap energy
- Add future TWT or non-TWT power managers on top of the same measurement framework

### 2026-04-21: Added explicit power strategies

Why this addition was made:

- A fixed power model was not enough to study tradeoffs between battery life and QoE.
- The XPAN problem is no longer just "measure energy"; it is "compare power-saving policies and see which ones preserve KPIs."
- This also opens the door to studying methods beyond TWT, which is useful for a stronger paper and better patent scope.

What was added:

- A power-strategy layer in `sim/power.py`
- Initial strategies:
  - `always_on`
  - `static_twt`
  - `adaptive_twt`
  - `predictive_prewake`
- Each strategy can now affect:
  - active Wi-Fi power
  - standby/prewarm power
  - latency/jitter overhead
  - delivery margin
  - effective awake ratio

Why these strategies were chosen:

- `always_on` is the control case with best readiness but worst Wi-Fi power usage.
- `static_twt` is a simple baseline for scheduled power saving but may hurt latency and switching quality.
- `adaptive_twt` represents a more context-aware version that relaxes power saving when QoS risk rises.
- `predictive_prewake` is meant to support the XPAN story directly by waking early when movement, low buffer, or handover pressure suggests trouble ahead.

What this enables next:

- Compare energy and QoE side-by-side for different Wi-Fi power policies
- Show where static TWT is too rigid
- Test whether predictive wake control is better aligned with XPAN whole-home transitions
- Extend the model later with more advanced duty-cycling, AP-assisted scheduling, or hybrid TWT/non-TWT methods

### 2026-04-21: Clarified service-driven bearer use cases

Why this addition was made:

- The earlier simulator treated `LE` mainly as the normal-buds baseline and focused XPAN on `P2P -> WHC`.
- The new use cases show that XPAN earbuds may also use `LE` directly depending on service type and phone power policy.

What was clarified:

- Voice call can use `LE` while `P2P` remains available in low-power idle mode
- Music can prefer `P2P`
- Distance can trigger `P2P -> LE`
- Phone low-power mode can trigger `P2P -> LE`

Why this matters:

- The system is not just link-reactive; it is also application-aware and policy-aware.
- This widens the scope of potential inventions beyond pure coverage extension.
- It points toward a more realistic multi-bearer XPAN controller.

### 2026-04-21: Added first service-aware bearer controller

Why this addition was made:

- The earlier simulator focused mainly on coverage-driven handover.
- The new use cases showed that bearer choice also depends on traffic type and phone power intent.

What was added:

- A service-aware scenario that sequences:
  - voice call on `LE`
  - music on `P2P`
  - move-away fallback
  - phone low-power fallback
- A service-aware controller that:
  - prefers `LE` for voice call
  - prefers `P2P` for music when conditions are good
  - falls back to `LE` for low-power or weak direct-link conditions
  - can still use predictive `P2P -> WHC` logic when Wi-Fi whole-home coverage is the better recovery path

Why this matters:

- It moves the simulator from bearer-quality-only decisions toward product-like policy decisions.
- It strengthens both paper and patent directions around service-aware bearer assignment.

## Possible Paper Ideas

### 1. Predictive Handover for XPAN Earbuds

Possible focus:

- Compare reactive versus predictive `P2P -> WHC` handover
- Measure gap-free quality, transition time, and energy overhead
- Show where predictive handover helps and where it still fails under blockage or infrastructure stress

Possible title:

- `Predictive Handover Control for XPAN Earbuds Across Direct and Whole-Home Wi-Fi Paths`

Why it is strong:

- This is already directly supported by the current simulator structure.
- The scenario results naturally support a paper narrative around where reactive handover breaks down.

### 2. Power Saving Beyond Static TWT

Possible focus:

- Compare `always_on`, `static_twt`, `adaptive_twt`, and `predictive_prewake`
- Show energy versus QoE tradeoffs
- Demonstrate that static TWT alone is too rigid for dynamic XPAN traffic and handover conditions

Possible title:

- `Power-Efficient QoS Preservation for XPAN Earbuds Using Adaptive Wake Strategies`

Why it is strong:

- This goes beyond a narrow TWT-only paper and creates stronger novelty.
- The current simulator already contains the core comparison framework.

### 3. Whole-Home Audio Robustness Under Infrastructure Stress

Possible focus:

- Study how AP quality, congestion, and backhaul load affect `WHC`
- Analyze when switching to WHC is beneficial versus harmful
- Introduce a readiness-aware or confidence-aware switch policy

Possible title:

- `Infrastructure-Aware Bearer Selection for Whole-Home XPAN Audio`

Why it is strong:

- The `mesh_backhaul_stress` scenario already points to this as a meaningful gap.

### 4. Cross-Layer Buffer- and Motion-Aware Wake Control

Possible focus:

- Use motion, buffer state, and link degradation trends together
- Adapt wake policy and handover timing jointly
- Target both battery efficiency and glitch-free audio continuity

Possible title:

- `Cross-Layer Wake Control for Low-Power XPAN Audio Under Mobility`

Why it is strong:

- It connects handover, power management, and wearable context into a single story.

### 5. Application-Aware Bearer Selection for XPAN Earbuds

Possible focus:

- Use voice call, music, motion, and phone low-power state to choose between `LE`, `P2P`, and `WHC`
- Compare throughput-oriented versus energy-oriented traffic placement
- Show that not all XPAN services should stay on Wi-Fi all the time

Possible title:

- `Application-Aware Multi-Bearer Control for XPAN Earbuds`

Why it is strong:

- It directly matches the latest use cases and creates a more product-realistic research problem.

## Possible Patent Ideas

### 1. Predictive P2P-to-WHC Handover with Prewarm Control

Core idea:

- Predict direct-path degradation before failure
- Prewarm WHC
- Execute a warm make-before-break switch only when WHC readiness is sufficient

Potential novelty:

- Using signal trend, motion state, and buffer condition jointly for XPAN handover timing

### 2. Adaptive Wake Scheduling for XPAN Earbuds

Core idea:

- Dynamically adjust wake behavior based on audio urgency, buffer level, congestion, and mobility

Potential novelty:

- A wake controller that changes policy between low-power and high-readiness modes during audio continuity risk

### 3. Predictive Prewake for Gap-Free Whole-Home Audio

Core idea:

- Wake Wi-Fi early when motion or degradation suggests an imminent path transition
- Reduce missed deadlines during handover while still saving energy compared with always-on operation

Potential novelty:

- Earbud-specific predictive prewake tied to handover risk rather than static wake scheduling

### 4. WHC Readiness-Gated Bearer Switching

Core idea:

- Do not switch from direct XPAN path to WHC solely because the direct path is degrading
- First score WHC readiness using congestion, AP quality, and backhaul load

Potential novelty:

- Avoiding harmful transitions into weak whole-home infrastructure even when direct P2P quality is falling

### 5. Joint Power-QoE Optimization Controller

Core idea:

- Select among `always_on`, TWT-like scheduling, adaptive wake, or predictive prewake based on expected energy cost and audio continuity risk

Potential novelty:

- A policy engine that coordinates handover and power strategy selection rather than treating them independently

### 6. Service-Aware XPAN Bearer Assignment

Core idea:

- Route voice-call traffic over `LE`
- Route music or high-rate media over `P2P`
- Change bearer selection dynamically based on application class, mobility, and device power state

Potential novelty:

- Bearer selection based jointly on service type and power policy rather than only on radio quality

### 7. Phone Low-Power-State Triggered XPAN Bearer Reassignment

Core idea:

- Detect phone low-power mode and proactively migrate from `P2P` to `LE`
- Preserve user experience while reducing Wi-Fi power demand on both ends

Potential novelty:

- Energy-intent-driven bearer switching between earbud and phone

### 8. Multi-Bearer Idle-Maintenance for XPAN Earbuds

Core idea:

- Keep `P2P` alive in a low-power idle or standby state while `LE` carries voice traffic
- Allow fast return to higher-throughput media transport when needed

Potential novelty:

- Split between control/standby connectivity and active media bearer selection for wearable audio

## Recommended Next Invention Directions

The strongest paths right now appear to be:

1. `predictive_prewake` plus predictive handover
2. WHC readiness-gated switching
3. hybrid power policy selection instead of a single fixed TWT policy
4. service-aware bearer assignment across `LE`, `P2P`, and `WHC`

Why these are the best current candidates:

- They match the failure modes already visible in the simulator.
- They are broad enough for paper contributions but specific enough to turn into patent disclosures.
- They connect directly to the real XPAN constraints of battery, mobility, gap-free audio, whole-home Wi-Fi dependence, and application-specific traffic behavior.
