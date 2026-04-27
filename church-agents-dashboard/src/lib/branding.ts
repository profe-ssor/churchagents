/**
 * User-facing identity for the chat assistant (orchestrator). Internal code name remains OrchestratorAgent.
 */
export const AI_NAME_SHORT = "CTO"
export const AI_NAME_EXPANSION = "Church Technician Officer"
export const AI_NAME_FULL = `${AI_NAME_SHORT} (${AI_NAME_EXPANSION})` as const

export const AI_ASK_PAGE_TITLE = `Ask ${AI_NAME_SHORT}`
export const AI_ASSISTANT_HEADLINE = AI_NAME_FULL
export const AI_NAV_BADGE = AI_NAME_SHORT
