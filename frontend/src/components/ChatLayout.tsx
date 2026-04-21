import type { ReactNode } from 'react'

type ChatLayoutProps = {
  children: ReactNode
  history: ReactNode
  dataPane: ReactNode
  infoPane: ReactNode
  activeTab: 'chat' | 'data' | 'info'
  onTabChange: (tab: 'chat' | 'data' | 'info') => void
  dataTabEnabled: boolean
}

export function ChatLayout({ children, history, dataPane, infoPane, activeTab, onTabChange, dataTabEnabled }: ChatLayoutProps) {
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
          <button
            className={`tabBtn${activeTab === 'info' ? ' tabBtn--active' : ''}`}
            onClick={() => onTabChange('info')}
          >
            Artefakte & Steps
          </button>
        </div>
        <div className="tabContent">
          {activeTab === 'chat' ? children : activeTab === 'data' ? dataPane : infoPane}
        </div>
      </main>
      <aside className="historyPane">{history}</aside>
    </div>
  )
}
