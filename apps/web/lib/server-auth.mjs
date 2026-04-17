import { hasSupabaseCredentials } from './supabase.mjs'
import { getSupabaseServer } from './supabase-server.mjs'

function isMissingSessionError(error) {
  return /auth session missing/i.test(error?.message || '')
}

export async function getServerAuthContext() {
  if (!hasSupabaseCredentials()) {
    return {
      missingCredentials: true,
      supabase: null,
      user: null,
      isAuthenticated: false,
      authState: 'credentials_missing',
      authError: null,
    }
  }

  const supabase = await getSupabaseServer()
  if (!supabase) {
    return {
      missingCredentials: true,
      supabase: null,
      user: null,
      isAuthenticated: false,
      authState: 'credentials_missing',
      authError: null,
    }
  }

  const { data, error } = await supabase.auth.getUser()
  const user = data?.user ?? null

  if (error) {
    if (isMissingSessionError(error)) {
      return {
        missingCredentials: false,
        supabase,
        user: null,
        isAuthenticated: false,
        authState: 'anonymous',
        authError: null,
      }
    }

    return {
      missingCredentials: false,
      supabase,
      user: null,
      isAuthenticated: false,
      authState: 'auth_error',
      authError: error.message,
    }
  }

  if (!user) {
    return {
      missingCredentials: false,
      supabase,
      user: null,
      isAuthenticated: false,
      authState: 'anonymous',
      authError: null,
    }
  }

  return {
    missingCredentials: false,
    supabase,
    user,
    isAuthenticated: true,
    authState: 'authenticated',
    authError: null,
  }
}

export async function getServerAdminContext() {
  const authContext = await getServerAuthContext()
  if (!authContext.isAuthenticated || !authContext.supabase) {
    return { ...authContext, isAdmin: false, profile: null }
  }

  try {
    const { data, error } = await authContext.supabase.rpc('is_admin')
    const isAdmin = data === true
    
    let profile = null
    if (isAdmin) {
      const { data: profileData } = await authContext.supabase
        .from('user_profiles')
        .select('*')
        .eq('id', authContext.user.id)
        .single()
      profile = profileData
    }

    return { ...authContext, isAdmin, profile }
  } catch {
    return { ...authContext, isAdmin: false, profile: null }
  }
}
