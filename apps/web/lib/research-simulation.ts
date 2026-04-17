import { useSyncExternalStore } from 'react'
import type { SimulationParams, SimulationResult } from '@/hooks/use-simulation'
import {
  RESEARCH_SIMULATION_CHANGE_EVENT,
  RESEARCH_SIMULATION_STORAGE_KEY,
  type ResearchSimulationSnapshot,
} from '@/types/research-simulation'

const MAX_REPLAY_FRAMES = 4

let cachedSnapshotRaw: string | null = null
let cachedSnapshotValue: ResearchSimulationSnapshot | null = null

function buildReplayFrameIndices(totalFrames: number) {
  if (totalFrames <= MAX_REPLAY_FRAMES) {
    return Array.from({ length: totalFrames }, (_, index) => index)
  }

  const maxIndex = totalFrames - 1
  const targets = [0, maxIndex / 3, (2 * maxIndex) / 3, maxIndex]
  const indices = [...new Set(targets.map((value) => Math.round(value)))]

  return indices.sort((left, right) => left - right)
}

function sampleSeries<T>(series: T[], indices: number[]) {
  return indices.map((index) => series[index] ?? series[series.length - 1])
}

export function readPersistedResearchSimulationSnapshot(): ResearchSimulationSnapshot | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw =
      window.localStorage.getItem(RESEARCH_SIMULATION_STORAGE_KEY) ??
      window.sessionStorage.getItem(RESEARCH_SIMULATION_STORAGE_KEY)
    if (!raw) {
      cachedSnapshotRaw = null
      cachedSnapshotValue = null
      return null
    }

    if (raw === cachedSnapshotRaw) {
      return cachedSnapshotValue
    }

    const parsed = JSON.parse(raw) as ResearchSimulationSnapshot
    cachedSnapshotRaw = raw
    cachedSnapshotValue = parsed
    return parsed
  } catch {
    window.localStorage.removeItem(RESEARCH_SIMULATION_STORAGE_KEY)
    window.sessionStorage.removeItem(RESEARCH_SIMULATION_STORAGE_KEY)
    cachedSnapshotRaw = null
    cachedSnapshotValue = null
    return null
  }
}

export function persistLatestResearchSimulationSnapshot(snapshot: ResearchSimulationSnapshot | null) {
  if (typeof window === 'undefined') {
    return
  }

  try {
    if (snapshot) {
      const serialized = JSON.stringify(snapshot)
      window.localStorage.setItem(RESEARCH_SIMULATION_STORAGE_KEY, serialized)
      window.sessionStorage.setItem(RESEARCH_SIMULATION_STORAGE_KEY, serialized)
      cachedSnapshotRaw = serialized
      cachedSnapshotValue = snapshot
    } else {
      window.localStorage.removeItem(RESEARCH_SIMULATION_STORAGE_KEY)
      window.sessionStorage.removeItem(RESEARCH_SIMULATION_STORAGE_KEY)
      cachedSnapshotRaw = null
      cachedSnapshotValue = null
    }
  } catch {
    // Ignore storage quota or serialization issues and keep the in-memory state.
  }

  window.dispatchEvent(new Event(RESEARCH_SIMULATION_CHANGE_EVENT))
}

export function subscribeToResearchSimulationChanges(onStoreChange: () => void) {
  if (typeof window === 'undefined') {
    return () => {}
  }

  const handleChange = () => onStoreChange()

  window.addEventListener('storage', handleChange)
  window.addEventListener(RESEARCH_SIMULATION_CHANGE_EVENT, handleChange)

  return () => {
    window.removeEventListener('storage', handleChange)
    window.removeEventListener(RESEARCH_SIMULATION_CHANGE_EVENT, handleChange)
  }
}

export function buildResearchSimulationSnapshot(
  result: SimulationResult,
  params: SimulationParams
): ResearchSimulationSnapshot {
  const replayFrameIndices = buildReplayFrameIndices(result.t.length)
  const replayTimes = sampleSeries(result.t, replayFrameIndices)
  const replayRows = sampleSeries(result.x, replayFrameIndices).map((row) => [...row])
  const replayLog = Array.isArray(result.log) ? result.log.slice(0, 8) : []
  const replayFluxData = result.flux_data
    ? {
        times: sampleSeries(result.flux_data.times, replayFrameIndices),
        fluxes: Object.fromEntries(
          Object.entries(result.flux_data.fluxes).map(([reaction, series]) => [
            reaction,
            sampleSeries(series, replayFrameIndices),
          ])
        ),
      }
    : null
  const snapshotId =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${replayTimes.length}-${result.n_metabolites}`

  return {
    snapshotId,
    capturedAt: new Date().toISOString(),
    params: { ...params },
    result: {
      success: result.success,
      t: replayTimes,
      x: replayRows,
      metabolite_names: [...result.metabolite_names],
      n_points: replayTimes.length,
      n_metabolites: result.n_metabolites,
      solver: result.solver,
      duration: result.duration,
      custom_params_source: result.custom_params_source,
      log: replayLog,
      research_data_mode: result.research_data_mode,
      active_dataset_id: result.active_dataset_id ?? null,
      active_dataset_label: result.active_dataset_label ?? null,
      dataset_applied: result.dataset_applied,
      dataset_fallback_reason: result.dataset_fallback_reason ?? null,
      dataset_applied_metabolites: Array.isArray(result.dataset_applied_metabolites)
        ? [...result.dataset_applied_metabolites]
        : [],
      flux_data: replayFluxData,
    },
  }
}

export function useLatestResearchSimulationSnapshot() {
  return useSyncExternalStore(
    subscribeToResearchSimulationChanges,
    readPersistedResearchSimulationSnapshot,
    () => null
  )
}
