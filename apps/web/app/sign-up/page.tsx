'use client'

import { useState } from 'react'
import { getSupabaseBrowser } from '@/lib/supabase-browser'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import { SidebarLogo } from '@/components/platform/SidebarLogo'

const ROLES = [
  'PhD Student',
  'Postdoctoral Fellow',
  'Master Student',
  'Research Associate',
  'Professor',
  'Lab Manager',
  'Research Engineer',
  'Clinical Researcher',
  'Industry Scientist',
  'Other',
]

export default function SignUpPage() {
  const [fullName, setFullName] = useState('')
  const [institution, setInstitution] = useState('')
  const [role, setRole] = useState('')
  const [department, setDepartment] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const supabase = getSupabaseBrowser()

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
        data: {
          full_name: fullName,
          institution,
          role,
          department,
        },
      },
    })

    if (error) {
      setError(error.message)
    } else {
      setSuccess(true)
    }
    setLoading(false)
  }

  const inputClass = "h-10 bg-[rgba(255,255,255,0.04)] border-[rgba(255,255,255,0.08)] text-[#e2e5ea] placeholder:text-[#4b5563] focus-visible:ring-[rgba(214,40,57,0.4)] focus-visible:border-[rgba(214,40,57,0.3)]"

  if (success) {
    return (
      <div className="fixed inset-0 z-50 bg-[#0f1117] flex flex-col items-center justify-center px-4">
        <div className="w-full max-w-[420px] text-center space-y-6">
          <div className="inline-flex items-center justify-center rounded-2xl bg-white p-3 shadow-lg mx-auto">
            <SidebarLogo className="h-12 w-12" />
          </div>
          <div className="space-y-2">
            <CheckCircle2 className="h-10 w-10 text-emerald-400 mx-auto" />
            <h1 className="text-2xl font-bold text-[#e2e5ea]">Check your email</h1>
            <p className="text-sm text-[#9ca3af] max-w-xs mx-auto">
              We sent a confirmation link to <strong className="text-[#e2e5ea]">{email}</strong>. Click the link to activate your account.
            </p>
          </div>
          <a href="/sign-in" style={{ color: '#d62839' }} className="inline-flex items-center text-sm hover:text-[#ef4444] font-medium">
            Back to sign in
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 bg-[#0f1117] flex flex-col items-center justify-center px-4 overflow-y-auto py-12">
      <div className="w-full max-w-[460px] space-y-6">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center rounded-2xl bg-white p-3 shadow-lg mx-auto">
            <SidebarLogo className="h-10 w-10" />
          </div>
          <h1 className="text-2xl font-bold text-[#e2e5ea] tracking-tight">Create your account</h1>
          <p className="text-sm text-[#9ca3af]">Red Blood Cell Research Platform</p>
        </div>

        <Card className="border-[rgba(255,255,255,0.08)] bg-[#1a1d23]">
          <CardContent className="pt-6">
            <form onSubmit={handleSignUp} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-[#9ca3af]">Full name <span className="text-red-400">*</span></Label>
                  <Input type="text" placeholder="Dr. Jane Smith" value={fullName} onChange={(e) => setFullName(e.target.value)} required className={inputClass} />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#9ca3af]">Institution <span className="text-red-400">*</span></Label>
                  <Input type="text" placeholder="Polytechnique Montreal" value={institution} onChange={(e) => setInstitution(e.target.value)} required className={inputClass} />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-[#9ca3af]">Function <span className="text-red-400">*</span></Label>
                  <Select value={role} onValueChange={setRole} required>
                    <SelectTrigger className={`w-full ${inputClass}`}>
                      <SelectValue placeholder="Select your role" />
                    </SelectTrigger>
                    <SelectContent>
                      {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-[#9ca3af]">Department</Label>
                  <Input type="text" placeholder="Chemical Engineering" value={department} onChange={(e) => setDepartment(e.target.value)} className={inputClass} />
                </div>
              </div>

              <div className="pt-2 border-t border-[rgba(255,255,255,0.06)] space-y-4">
                <div className="space-y-2">
                  <Label className="text-[#9ca3af]">Email address <span className="text-red-400">*</span></Label>
                  <Input type="email" placeholder="researcher@institution.edu" value={email} onChange={(e) => setEmail(e.target.value)} required className={inputClass} />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#9ca3af]">Password <span className="text-red-400">*</span></Label>
                  <Input type="password" placeholder="Minimum 6 characters" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} className={inputClass} />
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg bg-[rgba(214,40,57,0.1)] border border-[rgba(214,40,57,0.2)] p-3">
                  <AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">{error}</p>
                </div>
              )}

              <Button type="submit" disabled={loading || !role} className="w-full h-10 bg-[#d62839] hover:bg-[#bf2332] text-white font-medium gap-2">
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                Create account
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-[#6b7280]">
          Already have an account?{' '}
          <a href="/sign-in" style={{ color: '#d62839' }} className="hover:text-[#ef4444] font-medium">Sign in</a>
        </p>

        <p className="text-center text-[10px] text-[#4b5563]">
          Polytechnique Montreal &middot; Jolicoeur Lab &mdash; 2026
        </p>
      </div>
    </div>
  )
}
