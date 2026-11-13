'use client'

import type { ReactNode } from 'react'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { RoBoCopChat } from '@/components/features/robocop/RoBoCopChat'
import { sendRoBoCopChatMessage } from '@/lib/robocop/chat-client'
import { usePathname } from 'next/navigation'

export function PlatformShellWithRoBoCop({ children }: { children: ReactNode }) {
  const { context } = useResearchContext()
  const isResearch = usePathname().startsWith('/research')
  
  const handleSendMessage = async (message: string): Promise<string> => {
    if (!context) {
      return 'No research context available.'
    }
    
    try {
      const response = await sendRoBoCopChatMessage(context, message)
      return response.message
    } catch (error) {
      console.error('Chat error:', error)
      return 'Sorry, I encountered an error. Please try again.'
    }
  }
  
  return (
    <>
      {children}
      <RoBoCopChat
        context={context}
        onSendMessage={handleSendMessage}
        className={isResearch ? 'research-chat' : undefined}
      />
    </>
  )
}
