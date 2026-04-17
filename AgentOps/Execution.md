# AgentOps Execution

Execution style, validation flow, reporting discipline, and completion standards.

## Purpose
This file defines how work should be executed and reported in practice.

It is about:
- how to work
- how to verify
- how to report
- how to decide whether work is actually done

It is not the same as Tasks, Memory, Skills, or Policies.

---

## Default Execution Model

### 1. Inspect first
Before changing code:
- inspect the relevant files
- identify the actual execution path
- avoid guessing

### 2. Plan if the work is non-trivial
For multi-file, architecture, or workflow changes:
- state the objective
- state current behavior
- state likely root cause
- state intended implementation path
- state validation plan

### 3. Implement the smallest coherent change
- prefer minimal, reversible edits
- preserve working behavior where possible
- avoid broad speculative rewrites

### 4. Validate directly
Use the most direct verification that the task requires:
- type check
- build
- route verification
- browser verification
- scientific artifact verification
- trace verification
- contract validation

### 5. Report truthfully
At the end:
- summarize what changed
- say what was validated
- say what remains unproven
- identify blockers or residual risks

---

## Validation Expectations

### Required mindset
Ask:
- does it work?
- was it actually tested?
- is the evidence direct?
- would a strong staff engineer accept this as complete?

### Common validation types
- `npx tsc --noEmit`
- build verification
- route existence verification
- browser verification
- real artifact inspection
- contract parsing/validation
- trace inspection
- run monitoring evidence

### Done means
A task is done only when:
- the issue is addressed
- the implementation matches repo direction
- the relevant validation was performed
- obvious regressions were checked
- the result is documented clearly

---

## Reporting Flow

### At task start
State:
- what seems to be happening
- what you will inspect
- what you expect to verify

### During work
Provide concise progress updates:
- what was found
- what changed
- what remains
- what is blocked

### At task end
Summarize:
- root cause
- files changed
- implementation summary
- validation performed
- remaining risks
- next recommended step

---

## Blocker Handling

When blocked:
- stop pretending progress exists if it does not
- identify the exact blocker
- document whether it is:
  - auth blocker
  - environment blocker
  - missing config
  - long-running validation
  - incomplete artifact generation
  - unclear requirement

Do not hide blockers behind vague language.

---

## State Management

Before starting:
- check `AgentOps/Tasks.md`
- check `AgentOps/Memory.md`
- check repo-specific constraints

While working:
- keep the active work state updated
- preserve meaningful checkpoints

Before finishing:
- update `AgentOps/Tasks.md` if the active state changed materially
- update `AgentOps/Memory.md` if a reusable lesson was learned

---

## Run Discipline

### Long-running workflows
For long scientific runs:
- distinguish slow-but-healthy from stuck
- inspect intermediate artifacts before declaring failure
- do not overclaim success before top-level outputs exist

### Authenticated UI work
For protected flows:
- verify auth path availability before promising browser validation

### Trace / observability work
For LangGraph / LangSmith tasks:
- verify root trace first
- then verify node traces
- separate “trace exists” from “trace is richly useful”

---

## Use This File For
- execution discipline
- validation discipline
- reporting discipline
- definition of done

Do not use this file as a repo policy file or a lesson dump.