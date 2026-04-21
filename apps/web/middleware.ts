import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname
  const isPublicCalibrationTaxonomy =
    request.method === 'GET' && pathname === '/api/calibration/available-parameters'

  if (isPublicCalibrationTaxonomy) {
    return NextResponse.next({ request })
  }

  const bypassAuth = process.env.NODE_ENV !== 'production' || process.env.NEXT_PUBLIC_BYPASS_AUTH === 'true'
  if (bypassAuth) {
    return NextResponse.next({ request })
  }

  let supabaseResponse = NextResponse.next({ request })

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseAnonKey) {
    return supabaseResponse
  }

  const { createServerClient } = await import('@supabase/ssr')

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet: Array<{ name: string; value: string; options?: Record<string, unknown> }>) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
        supabaseResponse = NextResponse.next({ request })
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options as any)
        )
      },
    },
  })

  const { data: { user } } = await supabase.auth.getUser()

  if (!user && !pathname.startsWith('/sign-in') && !pathname.startsWith('/sign-up') && !pathname.startsWith('/auth')) {
    const url = request.nextUrl.clone()
    url.pathname = '/sign-in'
    return NextResponse.redirect(url)
  }

  if (user && (pathname.startsWith('/sign-in') || pathname.startsWith('/sign-up'))) {
    const url = request.nextUrl.clone()
    url.pathname = '/'
    url.search = '?feature=home'
    return NextResponse.redirect(url)
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|images/|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
