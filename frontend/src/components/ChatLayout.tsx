import type { ReactNode } from 'react'

type ChatLayoutProps = {
  children: ReactNode
  status: ReactNode
}

export function ChatLayout({ children, status }: ChatLayoutProps) {
  return (
    <div className="layout">
      <main className="chatPane">{children}</main>
      <aside className="statusPane">{status}</aside>
    </div>
  )
}
