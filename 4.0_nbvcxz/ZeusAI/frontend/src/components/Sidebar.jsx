import { useState, useEffect, useCallback } from 'react'
import {
  VscRocket, VscChevronRight, VscChevronDown, VscKey,
  VscServer, VscFolder, VscHistory, VscSettingsGear,
  VscDebugDisconnect, VscCheck, VscClose, VscRefresh,
} from 'react-icons/vsc'

const MODELS = [
  { group: 'Local', items: [
    { id: 'ollama/deepseek-coder-v2', name: 'DeepSeek Coder v2 (Ollama)' },
    { id: 'ollama/llama3.1', name: 'Llama 3.1 (Ollama)' },
    { id: 'ollama/codestral', name: 'Codestral (Ollama)' },
    { id: 'ollama/qwen2.5-coder', name: 'Qwen 2.5 Coder (Ollama)' },
  ]},
  { group: 'Gemini', items: [
    { id: 'gemini/gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
    { id: 'gemini/gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
    { id: 'gemini/gemini-2.0-flash', name: 'Gemini 2.0 Flash' },
  ]},
  { group: 'OpenRouter', items: [
    { id: 'openrouter/anthropic/claude-sonnet-4-20250514', name: 'Claude Sonnet 4' },
    { id: 'openrouter/anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet' },
    { id: 'openrouter/openai/gpt-4o', name: 'GPT-4o' },
    { id: 'openrouter/deepseek/deepseek-r1', name: 'DeepSeek R1' },
    { id: 'openrouter/meta-llama/llama-3.1-405b', name: 'Llama 3.1 405B' },
  ]},
  { group: 'HuggingFace', items: [
    { id: 'huggingface/deepseek-ai/DeepSeek-V3', name: 'DeepSeek V3 (HF)' },
    { id: 'huggingface/Qwen/Qwen2.5-Coder-32B', name: 'Qwen 2.5 Coder 32B (HF)' },
  ]},
  { group: 'Groq', items: [
    { id: 'groq/llama-3.3-70b-versatile', name: 'Llama 3.3 70B (Groq)' },
    { id: 'groq/mixtral-8x7b-32768', name: 'Mixtral 8x7B (Groq)' },
  ]},
]

const API_KEY_FIELDS = [
  { key: 'openrouter', label: 'OpenRouter', envVar: 'OPENROUTER_API_KEY' },
  { key: 'huggingface', label: 'HuggingFace', envVar: 'HF_TOKEN' },
  { key: 'groq', label: 'Groq', envVar: 'GROQ_API_KEY' },
  { key: 'gemini', label: 'Gemini', envVar: 'GEMINI_API_KEY' },
]

const SERVICES = [
  { id: 'docker', label: 'Docker' },
  { id: 'chromadb', label: 'ChromaDB' },
  { id: 'playwright', label: 'Playwright' },
  { id: 'ollama', label: 'Ollama' },
  { id: 'backend', label: 'Backend API' },
]

export default function Sidebar({
  model,
  onModelChange,
  apiKeys,
  onApiKeyChange,
  workspacePath,
  onWorkspaceChange,
  connected,
  collapsed,
  onToggleCollapse,
}) {
  const [sections, setSections] = useState({
    model: true,
    keys: false,
    status: true,
    workspace: true,
    history: false,
  })
  const [systemStatus, setSystemStatus] = useState({})
  const [episodes, setEpisodes] = useState([])
  const [loadingStatus, setLoadingStatus] = useState(false)

  const toggleSection = (key) => {
    setSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  // Fetch system status
  const fetchStatus = useCallback(async () => {
    setLoadingStatus(true)
    try {
      const res = await fetch('/api/status')
      if (res.ok) {
        const data = await res.json()
        setSystemStatus(data)
      }
    } catch {
      setSystemStatus({})
    }
    setLoadingStatus(false)
  }, [])

  // Fetch episodes
  const fetchEpisodes = useCallback(async () => {
    try {
      const res = await fetch('/api/episodes')
      if (res.ok) {
        const data = await res.json()
        setEpisodes(Array.isArray(data) ? data : (data.episodes || []))
      }
    } catch {
      setEpisodes([])
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    fetchEpisodes()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus, fetchEpisodes])

  const getServiceStatus = (serviceId) => {
    if (serviceId === 'backend') return connected ? 'online' : 'offline'
    if (systemStatus.services && systemStatus.services[serviceId]) {
      return systemStatus.services[serviceId] === true ||
        systemStatus.services[serviceId] === 'running'
        ? 'online' : 'offline'
    }
    if (systemStatus[serviceId]) {
      return systemStatus[serviceId] === true ||
        systemStatus[serviceId] === 'running'
        ? 'online' : 'offline'
    }
    return 'pending'
  }

  const formatTime = (ts) => {
    if (!ts) return ''
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  if (collapsed) {
    return (
      <aside className="sidebar" style={{ width: 48, minWidth: 48 }}>
        <div className="sidebar__brand" style={{ justifyContent: 'center', padding: '10px 0' }}>
          <div className="sidebar__brand-icon" onClick={onToggleCollapse} style={{ cursor: 'pointer' }}>
            ZA
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '8px 0' }}>
          <button className="btn-icon" title="Models"><VscServer /></button>
          <button className="btn-icon" title="API Keys"><VscKey /></button>
          <button className="btn-icon" title="Settings"><VscSettingsGear /></button>
          <button className="btn-icon" title="History"><VscHistory /></button>
        </div>
      </aside>
    )
  }

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar__brand">
        <div
          className="sidebar__brand-icon"
          onClick={onToggleCollapse}
          style={{ cursor: 'pointer' }}
          title="Collapse sidebar"
        >
          ZA
        </div>
        <span className="sidebar__brand-text">ZEUSAI</span>
        <span className="sidebar__brand-version">v5.1</span>
      </div>

      <div className="sidebar__content">
        {/* Model Selector */}
        <div className="sidebar__section">
          <div className="sidebar__section-header" onClick={() => toggleSection('model')}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <VscServer style={{ fontSize: 12 }} />
              <span>Model</span>
            </span>
            <span className={`chevron ${sections.model ? 'open' : ''}`}>
              <VscChevronRight />
            </span>
          </div>
          <div
            className={`sidebar__section-body ${!sections.model ? 'collapsed' : ''}`}
            style={{ maxHeight: sections.model ? '200px' : '0' }}
          >
            <div className="form-group">
              <select
                className="form-select"
                value={model}
                onChange={(e) => onModelChange(e.target.value)}
              >
                {MODELS.map(group => (
                  <optgroup key={group.group} label={group.group}>
                    {group.items.map(m => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* API Keys */}
        <div className="sidebar__section">
          <div className="sidebar__section-header" onClick={() => toggleSection('keys')}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <VscKey style={{ fontSize: 12 }} />
              <span>API Keys</span>
            </span>
            <span className={`chevron ${sections.keys ? 'open' : ''}`}>
              <VscChevronRight />
            </span>
          </div>
          <div
            className={`sidebar__section-body ${!sections.keys ? 'collapsed' : ''}`}
            style={{ maxHeight: sections.keys ? '400px' : '0' }}
          >
            {API_KEY_FIELDS.map(field => (
              <div className="form-group" key={field.key}>
                <label className="form-label">{field.label}</label>
                <input
                  className="form-input"
                  type="password"
                  placeholder={`${field.envVar}`}
                  value={apiKeys[field.key] || ''}
                  onChange={(e) => onApiKeyChange(field.key, e.target.value)}
                  autoComplete="off"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Workspace */}
        <div className="sidebar__section">
          <div className="sidebar__section-header" onClick={() => toggleSection('workspace')}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <VscFolder style={{ fontSize: 12 }} />
              <span>Workspace</span>
            </span>
            <span className={`chevron ${sections.workspace ? 'open' : ''}`}>
              <VscChevronRight />
            </span>
          </div>
          <div
            className={`sidebar__section-body ${!sections.workspace ? 'collapsed' : ''}`}
            style={{ maxHeight: sections.workspace ? '100px' : '0' }}
          >
            <div className="form-group">
              <input
                className="form-input mono"
                type="text"
                placeholder="/path/to/project"
                value={workspacePath}
                onChange={(e) => onWorkspaceChange(e.target.value)}
                style={{ fontSize: 11 }}
              />
            </div>
          </div>
        </div>

        {/* System Status */}
        <div className="sidebar__section">
          <div className="sidebar__section-header" onClick={() => toggleSection('status')}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <VscDebugDisconnect style={{ fontSize: 12 }} />
              <span>Services</span>
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <button
                className="btn-icon"
                onClick={(e) => { e.stopPropagation(); fetchStatus() }}
                title="Refresh status"
                style={{ width: 18, height: 18, fontSize: 11 }}
              >
                <VscRefresh style={{ animation: loadingStatus ? 'spin 1s linear infinite' : 'none' }} />
              </button>
              <span className={`chevron ${sections.status ? 'open' : ''}`}>
                <VscChevronRight />
              </span>
            </span>
          </div>
          <div
            className={`sidebar__section-body ${!sections.status ? 'collapsed' : ''}`}
            style={{ maxHeight: sections.status ? '300px' : '0' }}
          >
            {SERVICES.map(svc => {
              const status = getServiceStatus(svc.id)
              return (
                <div className="status-row" key={svc.id}>
                  <span className="status-row__label">{svc.label}</span>
                  <span className={`status-badge ${status}`}>
                    {status === 'online' && <VscCheck style={{ fontSize: 9 }} />}
                    {status === 'offline' && <VscClose style={{ fontSize: 9 }} />}
                    {status}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Session History */}
        <div className="sidebar__section">
          <div className="sidebar__section-header" onClick={() => toggleSection('history')}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <VscHistory style={{ fontSize: 12 }} />
              <span>History</span>
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {episodes.length > 0 && (
                <span style={{
                  fontSize: 9,
                  background: 'var(--bg-glass)',
                  padding: '1px 5px',
                  borderRadius: 8,
                  color: 'var(--text-dim)',
                }}>
                  {episodes.length}
                </span>
              )}
              <span className={`chevron ${sections.history ? 'open' : ''}`}>
                <VscChevronRight />
              </span>
            </span>
          </div>
          <div
            className={`sidebar__section-body ${!sections.history ? 'collapsed' : ''}`}
            style={{ maxHeight: sections.history ? '300px' : '0', overflowY: 'auto' }}
          >
            {episodes.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-dim)', padding: '8px 0' }}>
                No sessions yet
              </div>
            ) : (
              episodes.slice(0, 20).map((ep, i) => (
                <div className="episode-item" key={ep.id || i}>
                  <span className="episode-item__dot" />
                  <span className="episode-item__text">
                    {ep.title || ep.summary || `Session ${i + 1}`}
                  </span>
                  <span className="episode-item__time">
                    {formatTime(ep.timestamp || ep.created_at)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </aside>
  )
}
