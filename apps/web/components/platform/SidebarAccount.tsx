'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { LogOut, Settings, CreditCard, User, Crown, ChevronUp, ChevronDown } from 'lucide-react'
import { SIDEBAR_ACCOUNT_ACTIONS } from '../../lib/platform-navigation.ts'
import type { ProductContextShape } from './platform-shell.types'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

function buildInitials(name?: string | null, email?: string | null) {
  const source = (name || email || 'Researcher').trim()
  const tokens = source.split(/\s+/).filter(Boolean)
  return tokens.slice(0, 2).map(token => token[0]?.toUpperCase() || '').join('') || 'R'
}

function buildPlanLabel(productContext: ProductContextShape) {
  if (productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug) {
    return 'Workspace'
  }

  if (productContext?.isAuthenticated) {
    return 'Researcher'
  }

  return 'Guest'
}

function buildAccountContext(productContext: ProductContextShape) {
  const workspace = productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug
  const organization = productContext?.researcherIdentity?.organizationName

  if (workspace) {
    return `Active workspace · ${workspace}`
  }

  if (organization) {
    return `Organization · ${organization}`
  }

  if (productContext?.isAuthenticated) {
    return 'Personal researcher access'
  }

  return 'Anonymous platform access'
}

export function SidebarAccount({ compact, productContext }: { compact: boolean; productContext: ProductContextShape }) {
  const [open, setOpen] = useState(false)
  const identity = productContext?.researcherIdentity
  const initials = useMemo(
    () => buildInitials(identity?.displayName, identity?.email),
    [identity?.displayName, identity?.email]
  )

  if (compact) {
    return (
      <Link
        aria-label="Open account page"
        className="flex items-center justify-center p-2 rounded-xl hover:bg-muted transition-colors"
        href="/account"
        title="My account"
      >
        <Avatar className="h-8 w-8">
          <AvatarImage src="" alt={identity?.displayName || 'Researcher'} />
          <AvatarFallback className="bg-primary/10 text-primary font-medium text-xs">{initials}</AvatarFallback>
        </Avatar>
      </Link>
    )
  }

  return (
    <div className="mt-auto px-2 pb-4">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            className={cn(
              "flex items-center gap-3 w-full p-2 rounded-xl text-left transition-colors hover:bg-muted",
              open && "bg-muted"
            )}
          >
          <Avatar className="h-10 w-10 border border-border/50">
            <AvatarImage src="" alt={identity?.displayName || 'Researcher'} />
            <AvatarFallback className="bg-gradient-to-br from-primary/80 to-primary/60 text-primary-foreground font-semibold">
              {initials}
            </AvatarFallback>
          </Avatar>
          
          <div className="flex-1 min-w-0 grid gap-0.5">
            <span className="text-sm font-semibold text-foreground truncate">
              {identity?.displayName || 'Researcher'}
            </span>
            <span className="text-xs text-muted-foreground truncate">
              {identity?.email || 'No verified email'}
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0 text-muted-foreground">
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </div>
        </button>
      </PopoverTrigger>
      
      <PopoverContent 
        className="w-[240px] p-2 rounded-2xl shadow-lg border-border/50" 
        align="start" 
        side="top"
        sideOffset={12}
      >
        <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
          My Account
        </div>
        
        <div className="grid gap-1">
          {SIDEBAR_ACCOUNT_ACTIONS.map((action, index) => {
            const isSignOut = action.tone === 'danger';
            
            return (
              <div key={action.title}>
                {isSignOut && index > 0 && <Separator className="my-1" />}
                
                <Link
                  href={action.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors",
                    isSignOut 
                      ? "text-destructive hover:bg-destructive/10 hover:text-destructive" 
                      : "text-foreground hover:bg-muted"
                  )}
                  onClick={() => setOpen(false)}
                >
                  {action.icon === 'account' && !isSignOut && <User className="h-4 w-4" />}
                  {action.icon === 'billing' && !action.badgeText && <CreditCard className="h-4 w-4" />}
                  {action.icon === 'billing' && action.badgeText && <Crown className="h-4 w-4" />}
                  {action.icon === 'settings' && <Settings className="h-4 w-4" />}
                  {isSignOut && <LogOut className="h-4 w-4" />}
                  
                  <span className="flex-1">{action.title}</span>
                  
                  {action.badgeText && (
                    <span className="inline-flex items-center rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-600 ring-1 ring-inset ring-amber-500/20">
                      {action.badgeText}
                    </span>
                  )}
                </Link>
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
    </div>
  )
}
