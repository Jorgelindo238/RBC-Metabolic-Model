import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'
import { ACTIVE_WORKSPACE_COOKIE } from '../../../lib/server-workspace-context.mjs'
import { getSupabaseConfig } from '../../../lib/supabase.mjs'

export async function GET(request) {
  const redirectUrl = new URL('/', request.url)
  const response = NextResponse.redirect(redirectUrl)
  response.headers.set('Cache-Control', 'private, no-store')
  const config = getSupabaseConfig()

  if (!config) {
    response.cookies.delete(ACTIVE_WORKSPACE_COOKIE)
    return response
  }

  const supabase = createServerClient(config.url, config.anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options)
        })
      },
    },
  })

  await supabase.auth.signOut()
  response.cookies.delete(ACTIVE_WORKSPACE_COOKIE)
  return response
}
