import { useState, useEffect, useCallback, useRef } from 'react'
import Editor from '@monaco-editor/react'
import {
  VscClose, VscSave, VscFile, VscCode,
} from 'react-icons/vsc'

const LANG_MAP = {
  js: 'javascript',
  jsx: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  py: 'python',
  rb: 'ruby',
  rs: 'rust',
  go: 'go',
  java: 'java',
  cpp: 'cpp',
  c: 'c',
  cs: 'csharp',
  php: 'php',
  html: 'html',
  htm: 'html',
  css: 'css',
  scss: 'scss',
  less: 'less',
  json: 'json',
  xml: 'xml',
  yaml: 'yaml',
  yml: 'yaml',
  toml: 'toml',
  md: 'markdown',
  markdown: 'markdown',
  sql: 'sql',
  sh: 'shell',
  bash: 'shell',
  zsh: 'shell',
  ps1: 'powershell',
  bat: 'bat',
  dockerfile: 'dockerfile',
  Dockerfile: 'dockerfile',
  makefile: 'makefile',
  Makefile: 'makefile',
  graphql: 'graphql',
  svg: 'xml',
  txt: 'plaintext',
  log: 'plaintext',
  env: 'plaintext',
  gitignore: 'plaintext',
}

function getLanguage(filename) {
  if (!filename) return 'plaintext'
  const parts = filename.split('.')
  if (parts.length < 2) {
    // Check for special filenames
    const base = filename.split('/').pop()
    if (LANG_MAP[base]) return LANG_MAP[base]
    return 'plaintext'
  }
  const ext = parts.pop().toLowerCase()
  return LANG_MAP[ext] || 'plaintext'
}

export default function CodeEditor({ openFiles, activeFile, onFileSelect, onFileClose, onFileSave }) {
  const [fileContents, setFileContents] = useState({})
  const [modified, setModified] = useState({})
  const [saving, setSaving] = useState(false)
  const editorRef = useRef(null)

  // Load file content when a file is opened
  useEffect(() => {
    if (!activeFile) return
    if (fileContents[activeFile] !== undefined) return

    const loadFile = async () => {
      try {
        const res = await fetch(`/api/files/${encodeURIComponent(activeFile)}`)
        if (res.ok) {
          const data = await res.json()
          setFileContents(prev => ({
            ...prev,
            [activeFile]: data.content || '',
          }))
        } else {
          setFileContents(prev => ({
            ...prev,
            [activeFile]: `// Error loading file: ${res.status}`,
          }))
        }
      } catch (err) {
        setFileContents(prev => ({
          ...prev,
          [activeFile]: `// Error loading file: ${err.message}`,
        }))
      }
    }
    loadFile()
  }, [activeFile, fileContents])

  const handleEditorChange = useCallback((value) => {
    if (!activeFile) return
    setFileContents(prev => ({ ...prev, [activeFile]: value || '' }))
    setModified(prev => ({ ...prev, [activeFile]: true }))
  }, [activeFile])

  const handleSave = useCallback(async () => {
    if (!activeFile || !modified[activeFile]) return
    setSaving(true)
    try {
      const res = await fetch('/api/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: activeFile,
          content: fileContents[activeFile] || '',
        }),
      })
      if (res.ok) {
        setModified(prev => ({ ...prev, [activeFile]: false }))
      }
    } catch (err) {
      console.error('Save failed:', err)
    }
    setSaving(false)
    if (onFileSave) onFileSave(activeFile)
  }, [activeFile, modified, fileContents, onFileSave])

  // Ctrl+S keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave])

  const handleEditorMount = (editor) => {
    editorRef.current = editor
  }

  const handleCloseTab = (filename, e) => {
    e.stopPropagation()
    onFileClose(filename)
    // Clean up stored content
    setFileContents(prev => {
      const next = { ...prev }
      delete next[filename]
      return next
    })
    setModified(prev => {
      const next = { ...prev }
      delete next[filename]
      return next
    })
  }

  if (!openFiles || openFiles.length === 0) {
    return (
      <div className="code-editor-panel">
        <div className="code-editor__empty">
          <VscCode className="code-editor__empty-icon" />
          <span className="code-editor__empty-text">
            Select a file from the tree to edit
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            Ctrl+S to save • Syntax highlighting • Auto-detect language
          </span>
        </div>
      </div>
    )
  }

  const currentContent = fileContents[activeFile] ?? ''
  const currentLang = getLanguage(activeFile)

  return (
    <div className="code-editor-panel">
      {/* Tabs */}
      <div className="code-editor__tabs">
        {openFiles.map(file => (
          <div
            key={file}
            className={`code-editor__tab ${file === activeFile ? 'active' : ''}`}
            onClick={() => onFileSelect(file)}
          >
            <VscFile style={{ fontSize: 12, flexShrink: 0 }} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {file.split('/').pop()}
            </span>
            {modified[file] && (
              <span style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--accent-amber)',
                flexShrink: 0,
              }} />
            )}
            <button
              className="code-editor__tab-close"
              onClick={(e) => handleCloseTab(file, e)}
              title="Close"
            >
              <VscClose />
            </button>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="code-editor__toolbar">
        <span style={{
          fontSize: 10,
          color: 'var(--text-dim)',
          fontFamily: "'JetBrains Mono', monospace",
          flex: 1,
        }}>
          {activeFile} — {currentLang}
        </span>
        <button
          className="btn btn-sm btn-ghost"
          onClick={handleSave}
          disabled={!modified[activeFile] || saving}
          style={{ gap: 4 }}
        >
          <VscSave style={{ fontSize: 12 }} />
          {saving ? 'Saving...' : 'Save'}
        </button>
      </div>

      {/* Editor */}
      <div className="code-editor__body">
        <Editor
          height="100%"
          language={currentLang}
          value={currentContent}
          theme="vs-dark"
          onChange={handleEditorChange}
          onMount={handleEditorMount}
          options={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 14,
            lineHeight: 22,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            padding: { top: 12, bottom: 12 },
            renderLineHighlight: 'gutter',
            cursorBlinking: 'smooth',
            cursorSmoothCaretAnimation: 'on',
            smoothScrolling: true,
            bracketPairColorization: { enabled: true },
            formatOnPaste: true,
            tabSize: 2,
            wordWrap: 'on',
            automaticLayout: true,
          }}
          loading={
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-dim)',
              fontSize: 12,
            }}>
              Loading editor...
            </div>
          }
        />
      </div>
    </div>
  )
}
