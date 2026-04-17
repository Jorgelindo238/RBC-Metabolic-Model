import axios from 'axios'

const isBrowser = typeof window !== 'undefined'
const defaultApiBase = isBrowser
  ? '/api'
  : process.env.INTERNAL_WEB_API_BASE_URL || 'http://127.0.0.1:3000/api'
const API_BASE = defaultApiBase

export const apiClient = axios.create({
  baseURL: API_BASE,
})
