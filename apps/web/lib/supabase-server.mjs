import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { getSupabaseConfig } from './supabase.mjs'

export async function getSupabaseServer() {
  const config = getSupabaseConfig()
  if (!config) {
    return null
  }

  const cookieStore = await cookies()

  return createServerClient(config.url, config.anonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
    },
  })
}
