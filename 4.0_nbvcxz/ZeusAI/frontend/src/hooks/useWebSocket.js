import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = 'ws://localhost:8000/ws/agent'
const RECONNECT_MAX = 30000

export default function useWebSocket() {
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState([])
  const [lastEvent, setLastEvent] = useState(null)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(1000)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        if (!mountedRef.current) return
        console.log('[WS] Connected')
        setConnected(true)
        reconnectDelayRef.current = 1000
      }

      ws.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const data = JSON.parse(event.data)
          setLastEvent(data)

          switch (data.type) {
            case 'text_chunk':
              setMessages(prev => {
                const last = prev[prev.length - 1]
                if (last && last.role === 'assistant' && last.streaming) {
                  const updated = [...prev]
                  updated[updated.length - 1] = {
                    ...last,
                    content: last.content + (data.content || data.chunk || ''),
                  }
                  return updated
                }
                return [...prev, {
                  id: Date.now(),
                  role: 'assistant',
                  content: data.content || data.chunk || '',
                  streaming: true,
                  timestamp: new Date().toISOString(),
                }]
              })
              break

            case 'thinking':
              setMessages(prev => [...prev, {
                id: Date.now(),
                role: 'system',
                type: 'thinking',
                content: data.content || 'Thinking...',
                timestamp: new Date().toISOString(),
              }])
              break

            case 'tool_call':
              setMessages(prev => [...prev, {
                id: data.id || Date.now(),
                role: 'system',
                type: 'tool_call',
                tool: data.tool || data.name || 'unknown',
                args: data.args || data.arguments || {},
                status: 'executing',
                timestamp: new Date().toISOString(),
              }])
              break

            case 'tool_result':
              setMessages(prev => {
                const updated = [...prev]
                const idx = updated.findLastIndex(
                  m => m.type === 'tool_call' && m.status === 'executing'
                )
                if (idx >= 0) {
                  updated[idx] = {
                    ...updated[idx],
                    status: data.success !== false ? 'completed' : 'failed',
                    result: data.content || data.result || '',
                  }
                }
                return [...updated, {
                  id: Date.now(),
                  role: 'system',
                  type: 'tool_result',
                  tool: data.tool || data.name || '',
                  content: data.content || data.result || '',
                  success: data.success !== false,
                  timestamp: new Date().toISOString(),
                }]
              })
              break

            case 'agent_switch':
              setMessages(prev => [...prev, {
                id: Date.now(),
                role: 'system',
                type: 'agent_switch',
                agent: data.agent || data.name || '',
                content: data.content || `Switched to ${data.agent || data.name}`,
                timestamp: new Date().toISOString(),
              }])
              break

            case 'stdout_line':
              setMessages(prev => [...prev, {
                id: Date.now(),
                role: 'system',
                type: 'stdout',
                content: data.content || data.line || '',
                timestamp: new Date().toISOString(),
              }])
              break

            case 'image':
              setMessages(prev => [...prev, {
                id: Date.now(),
                role: 'assistant',
                type: 'image',
                content: data.content || data.data || '',
                format: data.format || 'png',
                timestamp: new Date().toISOString(),
              }])
              break

            case 'final':
              setMessages(prev => {
                const updated = [...prev]
                const lastStreaming = updated.findLastIndex(
                  m => m.role === 'assistant' && m.streaming
                )
                if (lastStreaming >= 0) {
                  updated[lastStreaming] = {
                    ...updated[lastStreaming],
                    streaming: false,
                    content: data.content || updated[lastStreaming].content,
                  }
                }
                return updated
              })
              break

            case 'error':
              setMessages(prev => [...prev, {
                id: Date.now(),
                role: 'system',
                type: 'error',
                content: data.content || data.message || 'An error occurred',
                timestamp: new Date().toISOString(),
              }])
              break

            case 'approval_needed':
              setMessages(prev => [...prev, {
                id: data.id || Date.now(),
                role: 'system',
                type: 'approval_needed',
                content: data.content || data.description || '',
                command: data.command || '',
                timestamp: new Date().toISOString(),
              }])
              break

            default:
              console.log('[WS] Unknown event:', data.type, data)
          }
        } catch (err) {
          console.error('[WS] Parse error:', err)
        }
      }

      ws.onclose = (event) => {
        if (!mountedRef.current) return
        console.log('[WS] Disconnected:', event.code, event.reason)
        setConnected(false)
        wsRef.current = null

        // Auto-reconnect with exponential backoff
        const delay = reconnectDelayRef.current
        console.log(`[WS] Reconnecting in ${delay}ms...`)
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(delay * 2, RECONNECT_MAX)
          connect()
        }, delay)
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }

      wsRef.current = ws
    } catch (err) {
      console.error('[WS] Connection failed:', err)
      const delay = reconnectDelayRef.current
      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectDelayRef.current = Math.min(delay * 2, RECONNECT_MAX)
        connect()
      }, delay)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting')
        wsRef.current = null
      }
    }
  }, [connect])

  const sendMessage = useCallback((type, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const msg = JSON.stringify({ type, ...payload })
      wsRef.current.send(msg)

      if (type === 'user_message') {
        // Finalize any streaming message
        setMessages(prev => {
          const updated = prev.map(m =>
            m.streaming ? { ...m, streaming: false } : m
          )
          return [...updated, {
            id: Date.now(),
            role: 'user',
            content: payload.content || payload.message || '',
            timestamp: new Date().toISOString(),
          }]
        })
      }

      return true
    }
    return false
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return {
    connected,
    messages,
    lastEvent,
    sendMessage,
    clearMessages,
    setMessages,
  }
}
