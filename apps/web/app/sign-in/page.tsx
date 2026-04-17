'use client'

import { useState } from 'react'
import { getSupabaseBrowser } from '@/lib/supabase-browser'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Loader2, AlertCircle } from 'lucide-react'
import { SidebarLogo } from '@/components/platform/SidebarLogo'

export default function SignInPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const supabase = getSupabaseBrowser()

  async function handleGoogleSignIn() {
    setGoogleLoading(true)
    setError(null)
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
    if (error) { setError(error.message); setGoogleLoading(false) }
  }

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSuccess(null)

    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) { setError(error.message) }
    else { window.location.href = '/?feature=home' }
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 z-50 bg-[#0f1117] flex flex-col items-center justify-center px-4 overflow-y-auto">
      <div className="w-full max-w-[420px] space-y-8">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center rounded-2xl bg-white p-3 shadow-lg mx-auto">
            <SidebarLogo className="h-12 w-12" />
          </div>
          <h1 className="text-2xl font-bold text-[#e2e5ea] tracking-tight">
            Sign in to airbc
          </h1>
          <p className="text-sm text-[#9ca3af]">
            Red Blood Cell Research Platform
          </p>
        </div>

        <Card className="border-[rgba(255,255,255,0.08)] bg-[#1a1d23]">
          <CardContent className="pt-6 space-y-5">
            <Button
              variant="outline"
              className="w-full h-11 gap-3 border-[rgba(255,255,255,0.1)] bg-[rgba(255,255,255,0.04)] text-[#e2e5ea] hover:bg-[rgba(255,255,255,0.08)] hover:text-white"
              onClick={handleGoogleSignIn}
              disabled={googleLoading}
            >
              {googleLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                </svg>
              )}
              Continue with Google
            </Button>

            <div className="flex items-center gap-3">
              <Separator className="flex-1 bg-[rgba(255,255,255,0.06)]" />
              <span className="text-xs text-[#6b7280] uppercase tracking-wider">or</span>
              <Separator className="flex-1 bg-[rgba(255,255,255,0.06)]" />
            </div>

            <form onSubmit={handleEmailSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[#9ca3af]">Email</Label>
                <Input
                  type="email"
                  placeholder="researcher@institution.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-10 bg-[rgba(255,255,255,0.04)] border-[rgba(255,255,255,0.08)] text-[#e2e5ea] placeholder:text-[#4b5563] focus-visible:ring-[rgba(214,40,57,0.4)] focus-visible:border-[rgba(214,40,57,0.3)]"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#9ca3af]">Password</Label>
                <Input
                  type="password"
                  placeholder="â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="h-10 bg-[rgba(255,255,255,0.04)] border-[rgba(255,255,255,0.08)] text-[#e2e5ea] placeholder:text-[#4b5563] focus-visible:ring-[rgba(214,40,57,0.4)] focus-visible:border-[rgba(214,40,57,0.3)]"
                />
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg bg-[rgba(214,40,57,0.1)] border border-[rgba(214,40,57,0.2)] p-3">
                  <AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">{error}</p>
                </div>
              )}

              {success && (
                <div className="rounded-lg bg-[rgba(74,222,128,0.1)] border border-[rgba(74,222,128,0.2)] p-3">
                  <p className="text-xs text-emerald-300">{success}</p>
                </div>
              )}

              <Button type="submit" disabled={loading} className="w-full h-10 bg-[#d62839] hover:bg-[#bf2332] text-white font-medium gap-2">
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                Sign in
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-[#6b7280]">
          Don&apos;t have an account?{' '}
          <a href="/sign-up" style={{ color: '#d62839' }} className="hover:text-[#ef4444] font-medium">Sign up</a>
        </p>

        <p className="text-center text-[10px] text-[#4b5563]">
          Polytechnique Montreal &middot; Jolicoeur Lab &mdash; 2026
        </p>
      </div>
    </div>
  )
}
