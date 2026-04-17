import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

// Create a single supabase client for interacting with your database
let _supabase = null

export function hasSupabaseCredentials() {
  return Boolean(supabaseUrl && supabaseAnonKey)
}

export function getSupabaseConfig() {
  if (!hasSupabaseCredentials()) {
    return null
  }

  return {
    url: supabaseUrl,
    anonKey: supabaseAnonKey,
  }
}

export function getSupabase() {
  if (_supabase) {
    return _supabase
  }

  // Gracefully degrade if no credentials are provided
  const config = getSupabaseConfig()
  if (!config) {
    console.warn('Supabase credentials missing. Supabase actions will fail gracefully.')
    return null
  }

  _supabase = createClient(config.url, config.anonKey)
  return _supabase
}
