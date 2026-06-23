import { useState, useCallback, useEffect, useRef } from 'react'
import useWebSocket from './hooks/useWebSocket'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import CodeEditor from './components/CodeEditor'
import { getCurrentWindow } from '@tauri-apps/api/window'
import {
  VscTerminalBash, VscFileCode, VscProject,
  VscPulse, VscListTree, VscHubot, VscClearAll,
  VscChromeMinimize, VscChromeMaximize, VscChromeClose,
  VscSearch, VscColorMode, VscSymbolRuler,
} from 'react-icons/vsc'

/* ============================================================
   ZEUSAI — ROOT APPLICATION COMPONENT (FAZ 10: Premium UI)
   Özel title bar, Cmd+K komut paleti, thinking timeline, tema
   ============================================================ */
export default function App() {
  const {
    connected,
    messages,
    sendMessage,
    clearMessages,
  } = useWebSocket()

  // Tauri masaüstü API'si sadece Tauri penceresi içinde mevcuttur.
  // Normal tarayıcıda (npm run dev) bu çağrı hata fırlatıp tüm
  // uygulamayı çökertir (boş ekran). Bu yüzden koruma altına alıyoruz.
  let appWindow = null
  try {
    appWindow = getCurrentWindow()
  } catch (e) {
    appWindow = null
  }

  // ---- Active Tab ----
  const [activeTab, setActiveTab] = useState('chat')

  // ---- Sidebar ----
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [selectedModel, setSelectedModel] = useState('deepseek/deepseek-chat')
  const [apiKeys, setApiKeys] = useState({})
  const [workspacePath, setWorkspacePath] = useState('')

  // ---- Code Editor ----
  const [openFiles, setOpenFiles] = useState([])
  const [activeFile, setActiveFile] = useState(null)

  // ---- Right Panel ----
  const [rightTab, setRightTab] = useState('status')
  const [taskQueue, setTaskQueue] = useState([])
  const [activeAgent, setActiveAgent] = useState(null)
  const [stepCount, setStepCount] = useState(0)

  // ---- File Tree ----
  const [fileTree, setFileTree] = useState([])

  // ---- Faz 10: Tema ----
  const [theme, setTheme] = useState(() => localStorage.getItem('zeusai-theme') || 'dark')

  // ---- Faz 10: Komut Paleti ----
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [paletteQuery, setPaletteQuery] = useState('')
  const paletteRef = useRef(null)
  const paletteInputRef = useRef(null)

  // ---- Faz 10: Thinking Timeline ----
  const [thinkSteps, setThinkSteps] = useState([])

  // ==========================================
  // TEMA DEĞİŞTİRME (FAZ 10)
  // ==========================================
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('zeusai-theme', theme)
  }, [theme])

  const cycleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : prev === 'light' ? 'system' : 'dark')
  }, [])

  const themeLabel = theme === 'dark' ? '🌙 Dark' : theme === 'light' ? '☀️ Light' : '🖥 System'

  // ==========================================
  // KOMUT PALETİ (FAZ 10 — Cmd/Ctrl+K)
  // ==========================================
  const PALETTE_ACTIONS = [
    { id: 'new-chat', label: 'Yeni Sohbet', keywords: 'new chat clear reset', run: () => handleClearSession() },
    { id: 'switch-model', label: 'Model Değiştir', keywords: 'model switch brain ai', run: () => { setSidebarCollapsed(false) } },
    { id: 'open-terminal', label: 'Terminali Aç', keywords: 'terminal console shell', run: () => { setRightTab('terminal') } },
    { id: 'toggle-theme', label: `Tema Değiştir (${themeLabel})`, keywords: 'theme dark light color', run: () => cycleTheme() },
    { id: 'toggle-sidebar', label: 'Sidebar Aç/Kapat', keywords: 'sidebar toggle panel', run: () => setSidebarCollapsed(prev => !prev) },
    { id: 'toggle-files', label: 'Dosya Ağacı', keywords: 'files tree explorer', run: () => { setRightTab('files') } },
    { id: 'agent-status', label: 'Ajan Durumu', keywords: 'agent status pulse', run: () => { setRightTab('status') } },
    { id: 'new-file', label: 'Yeni Dosya Oluştur', keywords: 'new file create', run: () => { sendMessage('user_message', { content: 'Yeni bir dosya oluştur' }) } },
  ]

  const filteredActions = !paletteQuery.trim()
    ? PALETTE_ACTIONS
    : PALETTE_ACTIONS.filter(a =>
        a.label.toLowerCase().includes(paletteQuery.toLowerCase()) ||
        a.keywords.toLowerCase().includes(paletteQuery.toLowerCase())
      )

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen(prev => !prev)
        setPaletteQuery('')
      }
      if (e.key === 'Escape' && paletteOpen) {
        setPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [paletteOpen])

  useEffect(() => {
    if (paletteOpen && paletteInputRef.current) {
      paletteInputRef.current.focus()
    }
  }, [paletteOpen])

  // ==========================================
  // THINKING TIMELINE (FAZ 10)
  // ==========================================
  useEffect(() => {
    const thinkingMsgs = messages.filter(m => m.type === 'thinking' || m.type === 'tool_call' || m.type === 'agent_switch')
    if (thinkingMsgs.length > 0) {
      const steps = thinkingMsgs.slice(-8).map((m, i) => {
        let phase = 'analiz'
        let status = 'done'
        if (m.type === 'thinking') { phase = 'analiz'; status = 'done' }
        else if (m.type === 'tool_call') { phase = 'aksiyon'; status = m.status === 'executing' ? 'running' : (m.status === 'failed' ? 'failed' : 'done') }
        else if (m.type === 'agent_switch') { phase = 'plan'; status = 'done' }

        return {
          id: m.id || i,
          phase,
          status,
          content: m.content || m.tool || m.agent || '',
          agent: m.agent || '',
        }
      })
      setThinkSteps(steps)
    }
  }, [messages])

  // ==========================================
  // HANDLERS
  // ==========================================
  const handleModelChange = useCallback((modelId) => {
    setSelectedModel(modelId)
    sendMessage('set_model', { model: modelId })
  }, [sendMessage])

  const handleApiKeyChange = useCallback((key, value) => {
    setApiKeys(prev => ({ ...prev, [key]: value }))
    sendMessage('set_api_key', { service: key, key: value })
  }, [sendMessage])

  const handleWorkspaceChange = useCallback((path) => {
    setWorkspacePath(path)
    if (path) sendMessage('load_workspace', { path })
  }, [sendMessage])

  const handleFileSelect = useCallback((filename) => {
    setActiveFile(filename)
    if (!openFiles.includes(filename)) setOpenFiles(prev => [...prev, filename])
    setActiveTab('code')
  }, [openFiles])

  const handleFileClose = useCallback((filename) => {
    setOpenFiles(prev => prev.filter(f => f !== filename))
    if (activeFile === filename) {
      const remaining = openFiles.filter(f => f !== filename)
      setActiveFile(remaining.length > 0 ? remaining[remaining.length - 1] : null)
    }
  }, [openFiles, activeFile])

  const handleFileSave = useCallback((filename) => {
    sendMessage('file_saved', { filename })
  }, [sendMessage])

  const handleClearSession = useCallback(() => {
    clearMessages()
    setTaskQueue([])
    setOpenFiles([])
    setActiveFile(null)
    setStepCount(0)
    setActiveAgent(null)
    setThinkSteps([])
    sendMessage('clear_session')
  }, [clearMessages, sendMessage])

  // ==========================================
  // TITLE BAR BUTONLARI (FAZ 10)
  // ==========================================
  const handleMinimize = () => appWindow?.minimize()
  const handleMaximize = () => appWindow?.toggleMaximize()
  const handleClose = () => appWindow?.close()

  // ==========================================
  // RENDER RIGHT PANEL
  // ==========================================
  const renderRightPanel = () => {
    if (rightTab === 'status') {
      return (
        <div className="right-panel__section" style={{ flex: 1 }}>
          <div className="right-panel__section-header">
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><VscPulse />Agent Status</span>
          </div>
          <div className="right-panel__section-content" style={{ padding: 12 }}>
            {/* Thinking Timeline (Faz 10) */}
            {thinkSteps.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div className="task-queue__title" style={{ marginBottom: 6 }}>
                  <VscSymbolRuler style={{ fontSize: 11, marginRight: 4 }} />
                  Thinking Timeline
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {thinkSteps.map(step => {
                    const icon = { analiz: '🔍', plan: '📋', aksiyon: '⚡', gozlem: '👁' }[step.phase] || '→'
                    const colors = {
                      running: 'var(--accent-cyan)',
                      done: 'var(--accent-green)',
                      failed: 'var(--accent-red)',
                    }
                    return (
                      <div key={step.id} style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '3px 8px', borderRadius: 6,
                        fontSize: 11, color: colors[step.status] || 'var(--text-dim)',
                        background: step.status === 'running' ? 'rgba(103,232,249,0.08)' : 'transparent',
                        borderLeft: `2px solid ${colors[step.status] || 'transparent'}`,
                        animation: step.status === 'running' ? 'pulse-glow 2s ease-in-out infinite' : 'none',
                      }}>
                        <span>{icon}</span>
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {step.content}
                        </span>
                        {step.agent && (
                          <span style={{
                            fontSize: 9, padding: '1px 5px', borderRadius: 8,
                            background: 'var(--bg-glass)', color: 'var(--text-dim)',
                          }}>{step.agent}</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Agent Flow */}
            <div className="agent-flow">
              {['Planner', 'Coder', 'Researcher', 'Validator'].map((agent, i) => {
                const agentLower = agent.toLowerCase()
                const isActive = activeAgent === agentLower
                return (
                  <div key={agent} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {i > 0 && <div className={`agent-flow__connector ${isActive ? 'active' : ''}`} />}
                    <div className={`agent-flow__node ${isActive ? 'active ' + agentLower : ''}`}>
                      <VscHubot style={{ fontSize: 10 }} />{agent}
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="agent-step-counter">
              <span className="agent-step-counter__label">Step</span>
              <span className="agent-step-counter__value">{stepCount} / 200</span>
            </div>

            <div className="task-queue">
              <div className="task-queue__title"><VscListTree style={{ fontSize: 11, marginRight: 4 }} />Task Queue</div>
              {taskQueue.length === 0 ? (
                <div style={{ fontSize: 11, color: 'var(--text-dim)', padding: '4px 0' }}>No active tasks</div>
              ) : (
                taskQueue.map((task, i) => (
                  <div key={task.id || i} className="task-item">
                    <span style={{
                      width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                      background: task.status === 'running' ? 'var(--accent-cyan)' :
                        task.status === 'done' ? 'var(--accent-green)' :
                        task.status === 'failed' ? 'var(--accent-red)' : 'var(--text-dim)',
                      animation: task.status === 'running' ? 'pulse-glow 1.5s ease-in-out infinite' : 'none',
                    }} />
                    <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {task.goal || `Task #${i + 1}`}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--text-dim)', textTransform: 'uppercase' }}>{task.status || 'pending'}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )
    }

    if (rightTab === 'files') {
      return (
        <div className="right-panel__section" style={{ flex: 1 }}>
          <div className="right-panel__section-header">
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><VscFileCode />File Tree</span>
          </div>
          <div className="right-panel__section-content">
            <div className="file-tree">
              {fileTree.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-dim)', textAlign: 'center', padding: '24px 12px' }}>
                  <VscProject style={{ fontSize: 32, opacity: 0.2, marginBottom: 8, display: 'block', margin: '0 auto' }} />
                  <span>No workspace loaded</span>
                </div>
              ) : (
                fileTree.map((node, i) => (
                  <div key={node.path || i} className={`file-tree-node ${activeFile === node.path ? 'selected' : ''}`}
                    onClick={() => handleFileSelect(node.path || node.name)}
                    style={{ paddingLeft: ((node.depth || 0) + 1) * 16 + 'px' }}>
                    <span className="file-tree-node__icon">{node.type === 'directory' ? '📁' : '📄'}</span>
                    <span className="file-tree-node__name">{node.name}</span>
                    {node.size && <span className="file-tree-node__size">{node.size}</span>}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )
    }

    if (rightTab === 'terminal') {
      return (
        <div className="right-panel__section" style={{ flex: 1 }}>
          <div className="right-panel__section-header">
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><VscTerminalBash />Terminal</span>
          </div>
          <div className="right-panel__section-content">
            <div className="terminal-panel">
              <div className="terminal-body">
                <div style={{
                  padding: 12, fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
                  color: 'var(--text-secondary)', lineHeight: 1.6, height: '100%',
                  overflow: 'auto', whiteSpace: 'pre-wrap',
                }}>
                  {messages.filter(m => m.type === 'stdout').slice(-100).map((m, i) => (
                    <div key={m.id || i} style={{ color: 'var(--accent-green)', borderBottom: '1px solid var(--border-subtle)', padding: '2px 0' }}>
                      {m.content}
                    </div>
                  ))}
                  {messages.filter(m => m.type === 'stdout').length === 0 && (
                    <span style={{ color: 'var(--text-dim)' }}>Agent stdout output will appear here...</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    }

    return null
  }

  // ==========================================
  // MAIN RENDER
  // ==========================================
  return (
    <>
      <div className="app-bg" />

      {/* FAZ 10: Özel Title Bar */}
      <div className="titlebar" data-tauri-drag-region>
        <div className="titlebar__brand">
          <span className="titlebar__logo">ZeusAI</span>
          <span className="titlebar__version">v5.1</span>
        </div>
        <div className="titlebar__center" data-tauri-drag-region>
          <span className="titlebar__hint">
            {connected ? '🟢 LIVE' : '🔴 OFFLINE'}
          </span>
        </div>
        <div className="titlebar__controls">
          <button className="titlebar__btn" title="Tema Değiştir" onClick={cycleTheme} style={{ fontSize: 12 }}>
            <VscColorMode />
          </button>
          <button className="titlebar__btn" title="Komut Paleti (Ctrl+K)" onClick={() => { setPaletteOpen(true); setPaletteQuery('') }}>
            <VscSearch />
          </button>
          <button className="titlebar__btn" title="Küçült" onClick={handleMinimize}>
            <VscChromeMinimize />
          </button>
          <button className="titlebar__btn" title="Tam Ekran" onClick={handleMaximize}>
            <VscChromeMaximize />
          </button>
          <button className="titlebar__btn titlebar__btn--close" title="Kapat" onClick={handleClose}>
            <VscChromeClose />
          </button>
        </div>
      </div>

      {/* FAZ 10: Komut Paleti Modal */}
      {paletteOpen && (
        <div className="palette-overlay" onClick={() => setPaletteOpen(false)}>
          <div className="palette-dialog" ref={paletteRef} onClick={e => e.stopPropagation()}>
            <div className="palette-search">
              <VscSearch style={{ fontSize: 16, color: 'var(--text-dim)', flexShrink: 0 }} />
              <input
                ref={paletteInputRef}
                className="palette-input"
                placeholder="Komut ara..."
                value={paletteQuery}
                onChange={e => setPaletteQuery(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Escape') setPaletteOpen(false)
                  if (e.key === 'Enter' && filteredActions.length > 0) {
                    filteredActions[0].run()
                    setPaletteOpen(false)
                  }
                }}
              />
              <span style={{ fontSize: 10, color: 'var(--text-dim)', padding: '2px 6px', borderRadius: 4, background: 'var(--bg-glass)' }}>
                esc
              </span>
            </div>
            <div className="palette-results">
              {filteredActions.map((action, idx) => (
                <div
                  key={action.id}
                  className={`palette-item ${idx === 0 ? 'active' : ''}`}
                  onClick={() => { action.run(); setPaletteOpen(false) }}
                  onMouseEnter={(e) => {
                    e.currentTarget.parentElement?.querySelectorAll('.palette-item').forEach(i => i.classList.remove('active'))
                    e.currentTarget.classList.add('active')
                  }}
                >
                  <span style={{ fontSize: 14, flexShrink: 0 }}>
                    {action.id === 'new-chat' ? '💬' :
                     action.id === 'switch-model' ? '🧠' :
                     action.id === 'open-terminal' ? '⚡' :
                     action.id === 'toggle-theme' ? '🎨' : '→'}
                  </span>
                  <span style={{ flex: 1 }}>{action.label}</span>
                  <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{action.keywords.split(' ')[0]}</span>
                </div>
              ))}
              {filteredActions.length === 0 && (
                <div style={{ padding: 12, textAlign: 'center', color: 'var(--text-dim)', fontSize: 12 }}>Sonuç bulunamadı</div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className={`app-layout ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        {/* SIDEBAR */}
        <Sidebar
          model={selectedModel}
          onModelChange={handleModelChange}
          apiKeys={apiKeys}
          onApiKeyChange={handleApiKeyChange}
          workspacePath={workspacePath}
          onWorkspaceChange={handleWorkspaceChange}
          connected={connected}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(prev => !prev)}
        />

        {/* HEADER */}
        <header className="app-header">
          <div className="app-header__tabs">
            <button className={`app-header__tab ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
              <span className="tab-icon">💬</span>Chat
            </button>
            <button className={`app-header__tab ${activeTab === 'code' ? 'active' : ''}`} onClick={() => setActiveTab('code')} disabled={!activeFile}>
              <span className="tab-icon">📝</span>Editor
              {openFiles.length > 0 && (
                <span style={{ fontSize: 9, background: 'var(--bg-glass)', padding: '1px 5px', borderRadius: 8, marginLeft: 4 }}>{openFiles.length}</span>
              )}
            </button>
          </div>
          <div className="app-header__status">
            <button className="btn-icon" title="Oturumu temizle" onClick={handleClearSession}><VscClearAll /></button>
            <div className={`connection-dot ${connected ? 'connected' : ''}`} />
            <span className="connection-label">{connected ? 'LIVE' : 'OFFLINE'}</span>
          </div>
        </header>

        {/* MAIN PANEL */}
        <main className="main-panel">
          {activeTab === 'chat' ? (
            <ChatPanel messages={messages} connected={connected} sendMessage={sendMessage} />
          ) : (
            <CodeEditor openFiles={openFiles} activeFile={activeFile}
              onFileSelect={handleFileSelect} onFileClose={handleFileClose} onFileSave={handleFileSave} />
          )}
        </main>

        {/* RIGHT PANEL */}
        <aside className="right-panel">
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-glass)', flexShrink: 0 }}>
            {[
              { id: 'status', icon: <VscPulse />, label: 'Status' },
              { id: 'files', icon: <VscFileCode />, label: 'Files' },
              { id: 'terminal', icon: <VscTerminalBash />, label: 'Terminal' },
            ].map(tab => (
              <button key={tab.id} onClick={() => setRightTab(tab.id)}
                style={{
                  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                  padding: '8px 0', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5,
                  color: rightTab === tab.id ? 'var(--accent-cyan)' : 'var(--text-dim)',
                  background: rightTab === tab.id ? 'var(--bg-glass)' : 'transparent',
                  borderBottom: rightTab === tab.id ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                  transition: 'all var(--transition-fast)',
                }}>
                {tab.icon}{tab.label}
              </button>
            ))}
          </div>
          {renderRightPanel()}
        </aside>
      </div>
    </>
  )
}
