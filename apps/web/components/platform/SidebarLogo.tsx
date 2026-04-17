import { cn } from '@/lib/utils'

export function SidebarLogo({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={cn('shrink-0', className)}
      viewBox="0 0 72 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M43 10c8 0 15 5 18 12-4-3-9-5-14-5 4 3 7 8 7 14 0 4-1 8-3 11 6-3 10-9 10-16 0-7-4-13-10-16-2 0-5 0-8 0Z"
        fill="#D62839"
        opacity="0.92"
      />
      <path
        d="M35 12c10 0 18 8 18 18 0 2 0 4-1 6-2-9-9-14-17-18-5-2-10-3-15-3 4-2 9-3 15-3Z"
        fill="#E63946"
      />
      <rect x="10" y="20" width="34" height="28" rx="5" stroke="#1F2A44" strokeWidth="3.5" />
      <path d="M22 54h10" stroke="#1F2A44" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M27 48v6" stroke="#1F2A44" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M24 29h6" stroke="#1F2A44" strokeWidth="3" strokeLinecap="round" />
      <rect x="25" y="21" width="15" height="23" rx="7.5" fill="white" stroke="#1F2A44" strokeWidth="3" />
      <path d="M27.5 32c0-3.8 3.1-6.9 6.9-6.9s6.9 3.1 6.9 6.9v6.1H27.5V32Z" fill="#D62839" />
      <path d="M34.4 28.5v7.5" stroke="white" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M30.6 32.3h7.6" stroke="white" strokeWidth="2.8" strokeLinecap="round" />
      <circle cx="27" cy="41" r="1.6" fill="#1F2A44" />
    </svg>
  )
}
