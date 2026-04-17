'use client'

import { useEffect, useSyncExternalStore } from 'react'

import {
  MONITORING_BAG_RECORDS,
  normalizeMonitoringBagRecord,
  normalizeMonitoringBagRecords,
  type MonitoringBagCreateInput,
  type MonitoringBagRecord,
} from './monitoring-inventory'

const MONITORING_BAG_STORAGE_KEY = 'clawblood.monitoring.bag-inventory'
const MONITORING_BAG_CHANGE_EVENT = 'clawblood.monitoring.bag-inventory-change'
const MONITORING_BAG_API_BASE_URL =
  typeof window !== 'undefined'
    ? '/api'
    : process.env.INTERNAL_WEB_API_BASE_URL || 'http://127.0.0.1:3000/api'

const MONITORING_BAG_SEED_SNAPSHOT = MONITORING_BAG_RECORDS.map((record) => ({ ...record }))

let monitoringBagRecordsSnapshot = MONITORING_BAG_SEED_SNAPSHOT.map((record) => ({ ...record }))
let monitoringBagHydrated = false
let monitoringBagHydrationPromise: Promise<MonitoringBagRecord[]> | null = null

function cloneRecord(record: MonitoringBagRecord): MonitoringBagRecord {
  return { ...record }
}

function readErrorMessage(payload: unknown, fallback: string) {
  if (typeof payload === 'string' && payload.trim()) {
    return payload.trim()
  }

  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  const candidate = payload as { detail?: unknown; message?: unknown }

  if (typeof candidate.detail === 'string' && candidate.detail.trim()) {
    return candidate.detail.trim()
  }

  if (typeof candidate.message === 'string' && candidate.message.trim()) {
    return candidate.message.trim()
  }

  try {
    return JSON.stringify(payload)
  } catch {
    return fallback
  }
}

function readMonitoringBagRecordsFromStorage() {
  if (typeof window === 'undefined') {
    return monitoringBagRecordsSnapshot
  }

  try {
    const raw = window.localStorage.getItem(MONITORING_BAG_STORAGE_KEY)
    if (!raw) {
      return monitoringBagRecordsSnapshot
    }

    const nextRecords = normalizeMonitoringBagRecords(JSON.parse(raw))
    const nextSignature = JSON.stringify(nextRecords)
    const currentSignature = JSON.stringify(monitoringBagRecordsSnapshot)

    if (nextSignature !== currentSignature) {
      monitoringBagRecordsSnapshot = nextRecords
    }

    return monitoringBagRecordsSnapshot
  } catch {
    return monitoringBagRecordsSnapshot
  }
}

function persistMonitoringBagRecords(records: MonitoringBagRecord[]) {
  if (typeof window === 'undefined') {
    return
  }

  monitoringBagRecordsSnapshot = records.map(cloneRecord)
  window.localStorage.setItem(MONITORING_BAG_STORAGE_KEY, JSON.stringify(monitoringBagRecordsSnapshot))
  window.dispatchEvent(new Event(MONITORING_BAG_CHANGE_EVENT))
}

function subscribeMonitoringBagRecords(callback: () => void) {
  if (typeof window === 'undefined') {
    return () => {}
  }

  const handleStorage = () => callback()

  window.addEventListener('storage', handleStorage)
  window.addEventListener(MONITORING_BAG_CHANGE_EVENT, handleStorage)

  return () => {
    window.removeEventListener('storage', handleStorage)
    window.removeEventListener(MONITORING_BAG_CHANGE_EVENT, handleStorage)
  }
}

async function fetchMonitoringBagRecordsFromApi() {
  const response = await fetch(`${MONITORING_BAG_API_BASE_URL}/monitoring/bags`, {
    cache: 'no-store',
  })

  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    throw new Error(readErrorMessage(payload, `Failed to load monitoring bags (${response.status})`))
  }

  const payload = await response.json()
  return normalizeMonitoringBagRecords(payload)
}

async function createMonitoringBagRecordOnApi(input: MonitoringBagCreateInput) {
  const response = await fetch(`${MONITORING_BAG_API_BASE_URL}/monitoring/bags`, {
    body: JSON.stringify(input),
    headers: {
      'Content-Type': 'application/json',
    },
    method: 'POST',
  })

  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    throw new Error(readErrorMessage(payload, `Failed to create monitoring bag (${response.status})`))
  }

  const payload = await response.json()
  const createdRecord = normalizeMonitoringBagRecord(payload)

  if (!createdRecord) {
    throw new Error('The monitoring API returned an invalid bag record.')
  }

  return createdRecord
}

export function getMonitoringBagRecordsSnapshot() {
  return readMonitoringBagRecordsFromStorage()
}

export function setMonitoringBagRecords(records: MonitoringBagRecord[]) {
  persistMonitoringBagRecords(records)
  monitoringBagHydrated = true
}

export function addMonitoringBagRecord(record: MonitoringBagRecord) {
  const current = readMonitoringBagRecordsFromStorage()
  const deduped = current.filter((bag) => bag.bagId !== record.bagId)
  persistMonitoringBagRecords([cloneRecord(record), ...deduped])
  monitoringBagHydrated = true
}

export async function hydrateMonitoringBagRecords(force = false) {
  if (typeof window === 'undefined') {
    return monitoringBagRecordsSnapshot
  }

  if (!force && monitoringBagHydrated) {
    return monitoringBagRecordsSnapshot
  }

  if (monitoringBagHydrationPromise) {
    return monitoringBagHydrationPromise
  }

  monitoringBagHydrationPromise = (async () => {
    try {
      const remoteRecords = await fetchMonitoringBagRecordsFromApi()
      persistMonitoringBagRecords(remoteRecords)
      monitoringBagHydrated = true
      return remoteRecords
    } catch {
      monitoringBagHydrated = true
      return monitoringBagRecordsSnapshot
    } finally {
      monitoringBagHydrationPromise = null
    }
  })()

  return monitoringBagHydrationPromise
}

export async function createMonitoringBagRecord(input: MonitoringBagCreateInput) {
  const createdRecord = await createMonitoringBagRecordOnApi(input)
  const current = readMonitoringBagRecordsFromStorage()
  const nextRecords = [createdRecord, ...current.filter((bag) => bag.bagId !== createdRecord.bagId)]

  persistMonitoringBagRecords(nextRecords)
  monitoringBagHydrated = true

  return createdRecord
}

export function useMonitoringBagInventory() {
  const bags = useSyncExternalStore(
    subscribeMonitoringBagRecords,
    getMonitoringBagRecordsSnapshot,
    () => MONITORING_BAG_SEED_SNAPSHOT
  )

  useEffect(() => {
    void hydrateMonitoringBagRecords()
  }, [])

  return {
    bags,
    createBag: createMonitoringBagRecord,
    refresh: () => hydrateMonitoringBagRecords(true),
  }
}

export function useMonitoringBagRecords() {
  return useMonitoringBagInventory().bags
}
