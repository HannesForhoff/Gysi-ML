import type { ReactNode } from 'react'

type ChatLayoutProps = {
  children: ReactNode
  status: ReactNode
  history: ReactNode
  dataPane: ReactNode
  activeTab: 'chat' | 'data'
  onTabChange: (tab: 'chat' | 'data') => void
  dataTabEnabled: boolean
}

export function ChatLayout({ children, status, history, dataPane, activeTab, onTabChange, dataTabEnabled }: ChatLayoutProps) {
  return (
    <div className="layout">
      <main className="chatPane">
        <div className="tabBar">
          <button
            className={`tabBtn${activeTab === 'chat' ? ' tabBtn--active' : ''}`}
            onClick={() => onTabChange('chat')}
          >
            Chat
          </button>
          <button
            className={`tabBtn${activeTab === 'data' ? ' tabBtn--active' : ''}`}
            onClick={() => onTabChange('data')}
            disabled={!dataTabEnabled}
          >
            Daten
          </button>
        </div>
        <div className="tabContent">
          {activeTab === 'chat' ? children : dataPane}
        </div>
      </main>
      <aside className="statusPane">{status}</aside>
      <aside className="historyPane">{history}</aside>
    </div>
  )
}
