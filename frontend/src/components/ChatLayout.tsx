import type { ReactNode } from 'react'

type ChatLayoutProps = {
  children: ReactNode
  status: ReactNode
  history: ReactNode
}

export function ChatLayout({ children, status, history }: ChatLayoutProps) {
  return (
    <div className="layout">
      <main className="chatPane">{children}</main>
      <aside className="statusPane">{status}</aside>
      <aside className="historyPane">{history}</aside>
    </div>
  )
}
