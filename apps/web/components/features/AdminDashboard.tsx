'use client'

import { useState } from 'react'
import { getSupabaseBrowser } from '@/lib/supabase-browser'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Users, ShieldCheck, UserCheck, Loader2 } from 'lucide-react'

interface User {
  id: string
  email: string
  full_name: string | null
  organization: string | null
  role: string
  is_active: boolean
  simulation_count: number
  created_at: string
  last_login: string | null
}

interface AdminProps {
  users: User[]
  stats: { totalUsers: number; adminCount: number; activeCount: number }
  currentUserId: string
}

export function AdminDashboard({ users: initialUsers, stats, currentUserId }: AdminProps) {
  const [users, setUsers] = useState(initialUsers)
  const [loading, setLoading] = useState<string | null>(null)
  const supabase = getSupabaseBrowser()

  async function toggleRole(userId: string, currentRole: string) {
    const newRole = currentRole === 'admin' ? 'user' : 'admin'
    setLoading(userId)
    try {
      await supabase.rpc('update_user_role_admin', { target_user_id: userId, new_role: newRole })
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u))
    } catch {}
    setLoading(null)
  }

  async function toggleActive(userId: string, isActive: boolean) {
    setLoading(userId)
    try {
      if (isActive) {
        await supabase.rpc('deactivate_user_admin', { target_user_id: userId })
        setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: false } : u))
      }
    } catch {}
    setLoading(null)
  }

  return (
    <div className="grid gap-5">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Users', value: stats.totalUsers, icon: Users, color: 'from-blue-600/80 to-blue-800/80' },
          { label: 'Admins', value: stats.adminCount, icon: ShieldCheck, color: 'from-rose-600/80 to-rose-800/80' },
          { label: 'Active', value: stats.activeCount, icon: UserCheck, color: 'from-emerald-600/80 to-emerald-800/80' },
        ].map((s) => {
          const Icon = s.icon
          return (
            <Card key={s.label} className={`bg-gradient-to-br ${s.color} border-0`}>
              <CardContent className="pt-5 pb-4 flex items-center justify-between">
                <div>
                  <p className="text-3xl font-bold text-white">{s.value}</p>
                  <p className="text-sm text-white/80">{s.label}</p>
                </div>
                <Icon className="h-8 w-8 text-white/30" />
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>User Management</CardTitle>
          <CardDescription>Manage user roles and account status. Changes take effect immediately.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Institution</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Simulations</TableHead>
                <TableHead>Joined</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>
                    <div>
                      <p className="text-sm font-medium">{u.full_name || '—'}</p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{u.organization || '—'}</TableCell>
                  <TableCell>
                    <Badge variant={u.role === 'admin' ? 'default' : 'secondary'} className="text-[10px]">
                      {u.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={u.is_active ? 'outline' : 'destructive'} className="text-[10px]">
                      {u.is_active ? 'Active' : 'Disabled'}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{u.simulation_count}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      {u.id !== currentUserId && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs"
                            disabled={loading === u.id}
                            onClick={() => toggleRole(u.id, u.role)}
                          >
                            {loading === u.id ? <Loader2 className="h-3 w-3 animate-spin" /> : u.role === 'admin' ? 'Demote' : 'Promote'}
                          </Button>
                          {u.is_active && (
                            <Button
                              variant="destructive"
                              size="sm"
                              className="h-7 text-xs"
                              disabled={loading === u.id}
                              onClick={() => toggleActive(u.id, u.is_active)}
                            >
                              Deactivate
                            </Button>
                          )}
                        </>
                      )}
                      {u.id === currentUserId && (
                        <span className="text-xs text-muted-foreground italic">You</span>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    No users found. Make sure the user_profiles table is set up in Supabase.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
