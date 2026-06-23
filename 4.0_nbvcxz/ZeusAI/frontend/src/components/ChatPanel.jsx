import { useState, useEffect, useRef, useCallback, useMemo, memo } from 'react'
import {
  VscSend, VscChevronDown, VscChevronRight, VscCheck,
  VscError, VscWarning, VscTools, VscAccount, VscRobot,
} from 'react-icons/vsc'

/* ---- Simple Markdown Renderer ---- */
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // Line breaks (double newline → paragraph)
    .replace(/\n\n/g, '</p><p>')
    // Single newline → <br>
    .replace(/\n/g, '<br/>')

  return '<p>' + html + '</p>'
}

/* ---- Message Components (memoized) ---- */
const ThinkingMessage = memo(function ThinkingMessage({ content }) {
  return (
    <div className="thinking-indicator">
      <div className="thinking-dots">
        <span /><span /><span />
      </div>
      <span>{content || 'Thinking...'}</span>
    </div>
  )
})

const ToolCallBadge = memo(function ToolCallBadge({ tool, status }) {
  return (
    <div className={`tool-call-badge ${status}`}>
      <VscTools style={{ fontSize: 12 }} />
      <span>{tool}</span>
      {status === 'executing' && <div className="tool-call-spinner" />}
      {status === 'completed' && <VscCheck style={{ fontSize: 11 }} />}
      {status === 'failed' && <VscError style={{ fontSize: 11 }} />}
    </div>
  )
})

const ToolResultCard = memo(function ToolResultCard({ tool, content, success }) {
  const [expanded, setExpanded] = useState(false)
  const displayContent = typeof content === 'object'
    ? JSON.stringify(content, null, 2)
    : String(content || '')

  return (
    <div className="tool-result-card">
      <div className="tool-result-header" onClick={() => setExpanded(!expanded)}>
        {expanded ? <VscChevronDown style={{ fontSize: 10 }} /> : <VscChevronRight style={{ fontSize: 10 }} />}
        <span style={{ color: success ? 'var(--accent-green)' : 'var(--accent-red)' }}>
          {success ? <VscCheck style={{ fontSize: 10 }} /> : <VscError style={{ fontSize: 10 }} />}
        </span>
        <span>Result: {tool}</span>
        {!expanded && displayContent && (
          <span style={{
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            color: 'var(--text-dim)',
            marginLeft: 8,
          }}>
            {displayContent.slice(0, 60)}
          </span>
        )}
      </div>
      {expanded && (
        <div className="tool-result-body">
          {displayContent || 'No output'}
        </div>
      )}
    </div>
  )
})

const ApprovalDialog = memo(function ApprovalDialog({ message, onApprove, onReject }) {
  return (
    <div className="approval-dialog">
      <div className="approval-dialog__title">
        <VscWarning />
        Approval Required
      </div>
      <div className="approval-dialog__content">
        {message.command || message.content}
      </div>
      <div className="approval-dialog__actions">
        <button className="btn btn-sm btn-success" onClick={() => onApprove(message)}>
          <VscCheck /> Approve
        </button>
        <button className="btn btn-sm btn-danger" onClick={() => onReject(message)}>
          <VscError /> Reject
        </button>
      </div>
    </div>
  )
})

const ImageMessage = memo(function ImageMessage({ content, format }) {
  const src = content.startsWith('data:')
    ? content
    : `data:image/${format || 'png'};base64,${content}`
  return (
    <img
      src={src}
      alt="Agent output"
      style={{ maxWidth: '100%', borderRadius: 8, marginTop: 6 }}
    />
  )
})

const AgentSwitchBanner = memo(function AgentSwitchBanner({ agent }) {
  const colors = {
    planner: 'var(--accent-cyan)',
    coder: 'var(--accent-violet)',
    researcher: 'var(--accent-amber)',
    validator: 'var(--accent-green)',
  }
  const agentLower = (agent || '').toLowerCase()
  const color = colors[agentLower] || 'var(--accent-cyan)'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      padding: '6px 0',
      animation: 'fadeIn 0.3s ease',
    }}>
      <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
      <span style={{
        fontSize: 10,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: 1,
        color,
        padding: '3px 12px',
        borderRadius: 10,
        background: `${color}15`,
        border: `1px solid ${color}30`,
      }}>
        ▸ {agent}
      </span>
      <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
    </div>
  )
})

const ErrorMessage = memo(function ErrorMessage({ content }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 8,
      padding: '8px 12px',
      background: 'rgba(248, 113, 113, 0.08)',
      border: '1px solid rgba(248, 113, 113, 0.2)',
      borderRadius: 'var(--radius-sm)',
      fontSize: 12,
      color: 'var(--accent-red)',
      animation: 'fadeIn 0.3s ease',
    }}>
      <VscError style={{ marginTop: 2, flexShrink: 0 }} />
      <span>{content}</span>
    </div>
  )
})

const ChatBubble = memo(function ChatBubble({ msg }) {
  const isUser = msg.role === 'user'
  const renderedMarkdown = useMemo(() => renderMarkdown(msg.content), [msg.content])

  return (
    <div className={`chat-message ${msg.role}`}>
      <div className={`chat-avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
        {isUser ? <VscAccount /> : <VscRobot />}
      </div>
      <div className="chat-bubble">
        {msg.type === 'image' ? (
          <ImageMessage content={msg.content} format={msg.format} />
        ) : (
          <>
            <div dangerouslySetInnerHTML={{ __html: renderedMarkdown }} />
            {msg.streaming && <span className="typing-cursor" />}
          </>
        )}
      </div>
    </div>
  )
})

/* ---- Main Chat Panel ---- */
export default function ChatPanel({ messages, connected, sendMessage }) {
  const [input, setInput] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  // Auto-scroll
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || !connected) return
    sendMessage('user_message', { content: trimmed })
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, connected, sendMessage])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleApprove = (msg) => {
    sendMessage('approve', { id: msg.id, approved: true })
  }

  const handleReject = (msg) => {
    sendMessage('approve', { id: msg.id, approved: false })
  }

  const renderMessage = (msg, idx) => {
    const key = msg.id || `msg-${idx}`
    // System messages
    if (msg.role === 'system') {
      switch (msg.type) {
        case 'thinking':
          return <ThinkingMessage key={key} content={msg.content} />
        case 'tool_call':
          return <ToolCallBadge key={key} tool={msg.tool} status={msg.status} />
        case 'tool_result':
          return (
            <ToolResultCard
              key={key}
              tool={msg.tool}
              content={msg.content}
              success={msg.success}
            />
          )
        case 'agent_switch':
          return <AgentSwitchBanner key={key} agent={msg.agent} />
        case 'error':
          return <ErrorMessage key={key} content={msg.content} />
        case 'approval_needed':
          return (
            <ApprovalDialog
              key={key}
              message={msg}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          )
        case 'stdout':
          return null // Rendered in terminal
        default:
          return null
      }
    }

    // User / Assistant messages → memoized ChatBubble
    return <ChatBubble key={key} msg={msg} />
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            color: 'var(--text-dim)',
          }}>
            <div style={{ fontSize: 48, opacity: 0.15 }}>🚀</div>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-muted)' }}>
              ZeusAI Agent
            </div>
            <div style={{ fontSize: 12, maxWidth: 300, textAlign: 'center', lineHeight: 1.6 }}>
              Start a conversation to plan, code, research, or validate.
              The agent will autonomously use tools and switch between specialized modes.
            </div>
          </div>
        ) : (
          messages
            .filter(m => m.type !== 'stdout')
            .map((msg, idx) => renderMessage(msg, idx))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder={connected ? 'Ask the agent anything...' : 'Connecting to backend...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={() => setIsComposing(false)}
            disabled={!connected}
            rows={1}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!connected || !input.trim()}
            title="Send message (Enter)"
          >
            <VscSend />
          </button>
        </div>
      </div>
    </div>
  )
}