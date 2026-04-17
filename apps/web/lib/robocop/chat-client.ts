import type { ResearchContext, RoBoCopChatRequest, RoBoCopChatResponse } from '@/types/research-context'
import { apiClient } from '@/lib/api-client'

/**
 * Client for RoBoCop Research Chat API
 */
export async function sendRoBoCopChatMessage(
  context: ResearchContext,
  message: string,
  conversationHistory?: any[]
): Promise<RoBoCopChatResponse> {
  const request: RoBoCopChatRequest = {
    context: context as any, // Type assertion for API compatibility
    message,
    conversationHistory,
  }

  const response = await apiClient.post<RoBoCopChatResponse>('/robocop/research/chat', request)
  return response.data
}
