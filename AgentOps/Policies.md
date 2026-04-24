# AgentOps Policies

Stable rules, constraints, and non-negotiable working principles for the coding agent.

## Purpose
This file defines how the agent should behave in this repo.
These are stable rules, not temporary tasks and not procedural walkthroughs.

---

## Core Working Principles

1. **Correctness before polish**
   - working code comes before elegance

2. **Smallest effective change**
   - avoid broad refactors unless clearly justified

3. **Preserve validated behavior**
   - do not casually break working flows

4. **Understand before editing**
   - inspect first, change second

5. **Be explicit about uncertainty**
   - distinguish proven, partial, and inferred results

---

## Repo Behavior Rules

### Plan-first rule
For non-trivial work:
- inspect first
- form a plan
- validate the root cause before patching broadly

### Validation rule
Do not mark important work complete without:
- appropriate code validation
- appropriate route/build/runtime verification
- truthful reporting of what was actually tested

### Documentation rule
Before finishing meaningful work:
- update task tracking
- update lessons when new repeatable lessons were learned

---

## UI / Frontend Rules

### Components
- keep components reasonably small
- split large components before they become unmanageable
- keep logic and view composition separated when possible

### Routing
- prefer route-backed navigation for real product structure
- keep route labels and route files consistent
- do not leave dead sidebar destinations

### Styling
- preserve the premium dark ClawBlood / RoBoCop direction
- do not introduce unnecessary visual regressions
- avoid uncontrolled global CSS drift

---

## Backend / Scientific Rules

### Scientific core
- do not duplicate scientific core logic unnecessarily
- do not patch scientific meaning casually
- preserve scientific truth boundaries

### FastAPI
- register routers explicitly
- ensure outputs are serializable
- use stable import boundaries

### Contracts
- prefer additive contract evolution
- avoid breaking downstream consumers unless explicitly required

---

## Auth / Security Rules

- do not bypass auth casually
- do not invent test credentials without permission
- respect protected-route behavior
- do not expose sensitive keys or credentials

---

## Search / Calibration Rules

- RoBoCop remains in control of mutation, evaluation, decision, and archive flow
- timeout, partial, crash, and completion are distinct states
- do not collapse all incomplete runs into the same meaning
- preserve traceability and artifact coherence

---

## Git Rules

- do not push to git unless explicitly instructed by the user
- keep changes focused
- avoid accidental inclusion of generated artifacts
- be careful around build outputs and temporary files

---

## Communication Rules

- progress reports should be concise and truthful
- blockers should be named clearly
- implementation summaries should include:
  - root cause
  - files changed
  - validation performed
  - remaining risks

---

## Product Direction Rules

### App structure
The product structure is moving around:
- HOME
- RESEARCH
- MONITORING
- MY ACCOUNT

### RoBoCop
RoBoCop is the central agent, not only a calibration tool.

### Research mode
Research mode includes:
- data intake
- calibration
- simulation
- flux analysis
- sensitivity analysis
- pathway visualization

### Monitoring mode
Monitoring mode includes:
- overview
- bag repo
- quality forecast
- alerts
- RoBoCop support

### Automation gateway
The future automation gateway is internal engine logic, not the visible product identity.
RoBoCop remains the product-facing research assistant name.

---

## Use This File For
- stable rules
- working constraints
- architecture guardrails
- repo behavior expectations

Do not use this file as a task list or lesson store.
