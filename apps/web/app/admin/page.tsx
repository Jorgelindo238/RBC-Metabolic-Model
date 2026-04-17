import { redirect } from 'next/navigation'
import { getServerAdminContext } from '../../lib/server-auth.mjs'
import { AdminDashboard } from '../../components/features/AdminDashboard'

export const metadata = { title: 'Admin - airbc' }

export default async function AdminPage() {
  const ctx = await getServerAdminContext()

  if (!ctx.isAuthenticated) {
    redirect('/sign-in')
  }

  if (!ctx.isAdmin) {
    redirect('/?feature=home')
  }

  const supabase = ctx.supabase!
  let users: any[] = []
  let stats = { totalUsers: 0, adminCount: 0, activeCount: 0 }

  try {
    const { data } = await supabase.rpc('get_all_users_admin')
    users = data || []
    stats = {
      totalUsers: users.length,
      adminCount: users.filter((u: any) => u.role === 'admin').length,
      activeCount: users.filter((u: any) => u.is_active).length,
    }
  } catch {}

  return <AdminDashboard users={users} stats={stats} currentUserId={ctx.user!.id} />
}
