import { useEffect, useRef, useState } from 'react'
import {
  generateSmartAnswer,
  idpStarterPrompts,
  noDocStarterPrompts
} from './aiEngine'
import './AIChatAgent.css'

// Helper to format timestamps (e.g. "04:30 PM")
function getTimeString() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/**
 * Strict validation helpers
 */
function isGibberish(str) {
  if (!str) return true
  const lower = str.toLowerCase().trim()
  if (lower.length > 25) return true
  if (/(.)\1{3,}/.test(lower)) return true

  const mashPatterns = [
    'asdf', 'hjkl', 'qwerty', 'zxcv', 'qazwsx', 'edcrfv',
    '12345', '67890', 'testtest', 'fakefake', 'dummy'
  ]
  if (mashPatterns.some(p => lower.includes(p))) return true
  if (/[bcdfghjklmnpqrstvwxyz]{6,}/i.test(lower)) return true
  if (/[aeiouy]{6,}/i.test(lower)) return true
  return false
}

function validateEmailStrict(email) {
  if (!email || !email.trim()) return 'Email is required'
  const trimmed = email.trim().toLowerCase()
  const emailRegex = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/
  if (!emailRegex.test(trimmed)) {
    return 'Please enter a valid email address'
  }
  const [username, domain] = trimmed.split('@')
  if (!username || !domain || username.length < 2 || isGibberish(username)) {
    return 'Please enter a valid email address'
  }
  const domainParts = domain.split('.')
  if (domainParts.length < 2) return 'Please enter a valid email domain'
  const tld = domainParts[domainParts.length - 1]
  if (tld.length < 2 || tld.length > 10 || !/^[a-zA-Z]+$/.test(tld)) {
    return 'Please enter a valid email domain (.com, .org, etc.)'
  }
  return null
}

function validateNameStrict(name) {
  if (!name || !name.trim()) return 'Full Name is required'
  const trimmed = name.trim()
  if (trimmed.length < 2 || trimmed.length > 40) {
    return 'Name must be between 2 and 40 characters'
  }
  if (!/^[a-zA-Z\s.'-]+$/.test(trimmed) || isGibberish(trimmed)) {
    return 'Please enter a valid name'
  }
  return null
}

/**
 * Markdown parser for formatting IDP responses inside AI response bubbles
 */
function FormattedMessage({ text }) {
  if (!text) return null
  const lines = text.split('\n')

  // Check for table blocks
  const elements = []
  let tableBuffer = []

  const flushTable = (key) => {
    if (tableBuffer.length > 0) {
      elements.push(
        <div key={`table-${key}`} className="reeva-msg-table-wrap">
          <table className="reeva-msg-table">
            <tbody>
              {tableBuffer.map((tRow, rIdx) => {
                const cells = tRow.split('|').map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
                const isHeader = rIdx === 0
                const isDivider = tRow.includes('---')
                if (isDivider) return null
                return (
                  <tr key={rIdx} className={isHeader ? 'reeva-table-head' : ''}>
                    {cells.map((cell, cIdx) => (
                      <td key={cIdx}>{renderInline(cell)}</td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )
      tableBuffer = []
    }
  }

  lines.forEach((line, idx) => {
    const trimmed = line.trim()
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      tableBuffer.push(trimmed)
      return
    }
    flushTable(idx)

    if (!trimmed) {
      elements.push(<div key={idx} style={{ height: '5px' }} />)
      return
    }

    if (trimmed.startsWith('• ') || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const content = trimmed.substring(2)
      elements.push(
        <div key={idx} style={{ display: 'flex', gap: '6px', margin: '2px 0' }}>
          <span style={{ color: '#0099e6', fontWeight: 'bold' }}>•</span>
          <span>{renderInline(content)}</span>
        </div>
      )
      return
    }

    if (trimmed.startsWith('> ')) {
      elements.push(
        <blockquote key={idx} style={{ borderLeft: '3px solid #0099e6', paddingLeft: '8px', margin: '4px 0', color: '#475569', fontStyle: 'italic' }}>
          {renderInline(trimmed.substring(2))}
        </blockquote>
      )
      return
    }

    elements.push(<div key={idx}>{renderInline(line)}</div>)
  })

  flushTable('final')
  return <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>{elements}</div>
}

function renderInline(str) {
  if (!str) return str
  const regex = /(\[.*?\]\(.*?\)|\*\*.*?\*\*|`.*?`|\*.*?\*)/g
  const parts = str.split(regex)

  return parts.map((part, i) => {
    if (part.startsWith('[') && part.includes('](') && part.endsWith(')')) {
      const match = part.match(/^\[(.*?)\]\((.*?)\)$/)
      if (match) {
        return (
          <a
            key={i}
            href={match[2]}
            target="_blank"
            rel="noreferrer"
            style={{ color: '#0099e6', fontWeight: '600', textDecoration: 'underline' }}
          >
            {match[1]}
          </a>
        )
      }
    }

    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }

    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code key={i} style={{ background: '#f1f5f9', padding: '1px 5px', borderRadius: '4px', color: '#0f172a', fontSize: '0.9em', fontFamily: 'monospace' }}>
          {part.slice(1, -1)}
        </code>
      )
    }

    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      return <em key={i}>{part.slice(1, -1)}</em>
    }

    return part
  })
}

/**
 * AIChatAgent Component
 * 
 * @param {object|string} documentData - Extracted document text / markdown / JSON
 * @param {string} documentName - Filename of currently active document
 * @param {string} apiKey - Optional Gemini API key
 * @param {string} userName - Name of logged in user (defaults to "Shravan")
 */
export default function AIChatAgent({
  documentData = null,
  documentName = '',
  apiKey = '',
  userName = 'Shravan'
}) {
  const [open, setOpen] = useState(false)
  // Screen flow: 'welcome' | 'form' | 'chat'
  const [screen, setScreen] = useState('welcome')

  // User form data
  const [userData, setUserData] = useState({ email: '', name: userName || 'Shravan', message: '' })
  const [formErrors, setFormErrors] = useState({})

  // Chat message state
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)

  // Voice & Audio conversation states
  const [isListening, setIsListening] = useState(false)
  const [autoSpeak, setAutoSpeak] = useState(true)
  const [speakingIndex, setSpeakingIndex] = useState(null)

  const [showCallModal, setShowCallModal] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)

  // Dynamic starter suggestions based on document state
  const activePrompts = documentData ? idpStarterPrompts : noDocStarterPrompts
  const [currentSuggestions, setCurrentSuggestions] = useState(activePrompts.map(p => p.label))

  const messagesEndRef = useRef(null)
  const recognitionRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    if (screen === 'chat') {
      scrollToBottom()
    }
  }, [screen, messages, isTyping])

  useEffect(() => {
    const prompts = documentData ? idpStarterPrompts : noDocStarterPrompts
    setCurrentSuggestions(prompts.map(p => p.label))
  }, [documentData, documentName])

  // Stop speech when closing or changing screens
  useEffect(() => {
    return () => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop()
        } catch {
          // ignore
        }
      }
    }
  }, [screen, open])

  // Clean Speech Text-to-Speech Output Function
  const speakResponse = (text, msgId) => {
    if (!('speechSynthesis' in window)) {
      console.warn('Speech synthesis not supported in this browser.')
      return
    }

    if (speakingIndex === msgId) {
      window.speechSynthesis.cancel()
      setSpeakingIndex(null)
      return
    }

    window.speechSynthesis.cancel()

    // Clean markdown and symbols for smooth speech
    const cleanSpeech = (text || '')
      .replace(/\[(.*?)\]\(.*?\)/g, '$1')
      .replace(/[*#_>`•|]/g, '')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/\n+/g, ' ')
      .trim()

    if (!cleanSpeech) return

    const utterance = new SpeechSynthesisUtterance(cleanSpeech)
    utterance.rate = 1.0
    utterance.pitch = 1.0
    utterance.lang = 'en-US'

    utterance.onstart = () => {
      setSpeakingIndex(msgId)
    }
    utterance.onend = () => {
      setSpeakingIndex(null)
    }
    utterance.onerror = () => {
      setSpeakingIndex(null)
    }

    setSpeakingIndex(msgId)
    window.speechSynthesis.speak(utterance)
  }

  const handleEmailChange = (val) => {
    setUserData(prev => ({ ...prev, email: val }))
    if (formErrors.email) {
      const err = validateEmailStrict(val)
      if (!err) {
        setFormErrors(prev => {
          const updated = { ...prev }
          delete updated.email
          return updated
        })
      }
    }
  }

  const handleNameChange = (val) => {
    setUserData(prev => ({ ...prev, name: val }))
    if (formErrors.name) {
      const err = validateNameStrict(val)
      if (!err) {
        setFormErrors(prev => {
          const updated = { ...prev }
          delete updated.name
          return updated
        })
      }
    }
  }

  // Handle Form Submission (Welcome / Form -> Chat)
  const handleStartConversation = async (e) => {
    if (e) e.preventDefault()

    const emailErr = userData.email ? validateEmailStrict(userData.email) : null
    const nameErr = validateNameStrict(userData.name || userName || 'User')

    const errors = {}
    if (emailErr) errors.email = emailErr
    if (nameErr) errors.name = nameErr

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    setFormErrors({})
    const displayName = (userData.name || userName || 'Shravan').trim()

    // Personalized greeting matching Image 2
    const initialGreeting = {
      id: 1,
      role: 'ai',
      text: `Hi ${displayName}! 👋\n\nI’m Reeva AI. How can I help you today?`,
      time: getTimeString(),
      senderName: 'Reeva AI'
    }

    const initMsgs = [initialGreeting]

    if (userData.message && userData.message.trim()) {
      const userFirstMsg = {
        id: 2,
        role: 'user',
        text: userData.message.trim(),
        time: getTimeString()
      }
      initMsgs.push(userFirstMsg)

      setMessages(initMsgs)
      setScreen('chat')
      setIsTyping(true)

      const answer = await generateSmartAnswer(
        userData.message.trim(),
        apiKey,
        documentData,
        { documentName }
      )

      const aiReply = {
        id: 3,
        role: 'ai',
        text: answer.text,
        time: getTimeString(),
        senderName: 'Reeva AI',
        actionLinks: answer.actionLinks || [],
        suggestions: answer.suggestions || []
      }
      setMessages([...initMsgs, aiReply])
      setIsTyping(false)

      if (autoSpeak) {
        setTimeout(() => speakResponse(answer.text, 3), 300)
      }
    } else {
      setMessages(initMsgs)
      setScreen('chat')
      if (autoSpeak) {
        setTimeout(() => speakResponse(initialGreeting.text, 1), 300)
      }
    }
  }

  // Send message in conversation
  const handleSend = async (customQuery) => {
    const query = (customQuery || input).trim()
    if (!query || isTyping) return

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
      setSpeakingIndex(null)
    }

    const userMsg = {
      id: Date.now(),
      role: 'user',
      text: query,
      time: getTimeString()
    }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)
    setShowSuggestions(false)

    try {
      const replyData = await generateSmartAnswer(
        query,
        apiKey,
        documentData,
        { documentName }
      )
      const newAiId = Date.now() + 1

      const aiMsg = {
        id: newAiId,
        role: 'ai',
        text: replyData.text,
        time: getTimeString(),
        senderName: 'Reeva AI',
        suggestions: replyData.suggestions || [],
        actionLinks: replyData.actionLinks || []
      }

      setMessages(prev => [...prev, aiMsg])
      if (replyData.suggestions && replyData.suggestions.length > 0) {
        setCurrentSuggestions(replyData.suggestions)
      }

      if (autoSpeak) {
        setTimeout(() => speakResponse(replyData.text, newAiId), 200)
      }
    } catch (err) {
      console.error(err)
      const fallbackId = Date.now() + 1
      const fallbackMsg = {
        id: fallbackId,
        role: 'ai',
        text: "I encountered an issue processing your request. Please check if your document is loaded and try again.",
        time: getTimeString(),
        senderName: 'Reeva AI'
      }
      setMessages(prev => [...prev, fallbackMsg])
      if (autoSpeak) {
        setTimeout(() => speakResponse(fallbackMsg.text, fallbackId), 200)
      }
    } finally {
      setIsTyping(false)
    }
  }

  // Robust Voice Input (Web Speech API)
  const toggleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Voice speech recognition is not supported in this browser. Please try Google Chrome or Microsoft Edge.')
      return
    }

    if (isListening) {
      try {
        recognitionRef.current?.stop()
      } catch {
        // ignore
      }
      setIsListening(false)
      return
    }

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
      setSpeakingIndex(null)
    }

    try {
      const rec = new SpeechRecognition()
      recognitionRef.current = rec
      rec.lang = 'en-US'
      rec.continuous = false
      rec.interimResults = false

      rec.onstart = () => {
        setIsListening(true)
      }

      rec.onresult = (e) => {
        setIsListening(false)
        if (e.results && e.results[0] && e.results[0][0]) {
          const transcript = e.results[0][0].transcript
          setInput(transcript)
          handleSend(transcript)
        }
      }

      rec.onerror = (e) => {
        console.warn('Voice recognition error:', e.error)
        setIsListening(false)
        if (e.error === 'not-allowed') {
          alert('Microphone access was denied. Please allow microphone permissions in your browser.')
        }
      }

      rec.onend = () => {
        setIsListening(false)
      }

      rec.start()
    } catch (err) {
      console.error('Failed to start speech recognition:', err)
      setIsListening(false)
    }
  }

  // End conversation
  const handleEndConversation = () => {
    if (window.confirm('End this conversation and return to the main screen?')) {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel()
        setSpeakingIndex(null)
      }
      setMessages([])
      setUserData({ email: '', name: userName || 'Shravan', message: '' })
      setFormErrors({})
      setScreen('welcome')
    }
  }

  return (
    <div className="reeva-ai-widget">
      {/* AI Window */}
      {open && (
        <div className="reeva-ai-window">
          {/* ================================================================
              SCREEN 1: WELCOME SCREEN (Image 1)
              ================================================================ */}
          {screen === 'welcome' && (
            <div className="reeva-screen-welcome">
              <div className="reeva-welcome-top">
                <h1>Reeva Dev</h1>
                <p>Intelligent Document Processing AI</p>
                {documentName && (
                  <div className="reeva-doc-status-badge">
                    📄 Active File: <b>{documentName}</b>
                  </div>
                )}
              </div>

              <div className="reeva-welcome-body">
                {/* "We're here to help" card */}
                <div className="reeva-help-card">
                  <h3>We're here to help</h3>
                  <p>Typically replies in a few seconds</p>
                  <button
                    className="reeva-start-conv-link"
                    onClick={() => {
                      setFormErrors({})
                      setScreen('form')
                    }}
                  >
                    Start Conversation <span>&gt;</span>
                  </button>
                </div>

                {/* Quick Topics */}
                <div className="reeva-welcome-pills">
                  {activePrompts.slice(0, 4).map((p, i) => (
                    <button
                      key={i}
                      className="reeva-welcome-pill"
                      onClick={() => {
                        setUserData(prev => ({ ...prev, message: p.query }))
                        setFormErrors({})
                        setScreen('form')
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="reeva-ai-powered">Powered by Reeva Dev</div>
            </div>
          )}

          {/* ================================================================
              SCREEN 2: PRE-CHAT FORM
              ================================================================ */}
          {screen === 'form' && (
            <div className="reeva-screen-form">
              <div className="reeva-nav-header">
                <div className="reeva-nav-header-left">
                  <button
                    className="reeva-back-btn"
                    onClick={() => setScreen('welcome')}
                    aria-label="Back to welcome"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="15 18 9 12 15 6" />
                    </svg>
                  </button>
                  <div className="reeva-nav-header-titles">
                    <h2>Reeva Dev</h2>
                    <p>Typically replies in a few minutes</p>
                  </div>
                </div>
              </div>

              <form className="reeva-form-scroll" onSubmit={handleStartConversation}>
                {/* Email Field */}
                <div className="reeva-form-group">
                  <label className={formErrors.email ? 'has-error' : ''}>
                    Email Id (Optional)
                  </label>
                  <input
                    type="email"
                    className={`reeva-form-input ${formErrors.email ? 'has-error' : ''}`}
                    placeholder="Enter your email address"
                    value={userData.email}
                    onChange={(e) => handleEmailChange(e.target.value)}
                  />
                  {formErrors.email && <span className="reeva-field-error">{formErrors.email}</span>}
                </div>

                {/* Full Name Field */}
                <div className="reeva-form-group">
                  <label className={formErrors.name ? 'has-error' : ''}>
                    Full Name
                  </label>
                  <input
                    type="text"
                    className={`reeva-form-input ${formErrors.name ? 'has-error' : ''}`}
                    placeholder="Enter your name"
                    value={userData.name}
                    onChange={(e) => handleNameChange(e.target.value)}
                  />
                  {formErrors.name && <span className="reeva-field-error">{formErrors.name}</span>}
                </div>

                {/* Message Field */}
                <div className="reeva-form-group">
                  <label>Ask Question about Document</label>
                  <textarea
                    className="reeva-form-textarea"
                    placeholder="Ask about invoice total, date, vendor, line items, or fraud checks..."
                    value={userData.message}
                    onChange={(e) => setUserData({ ...userData, message: e.target.value })}
                  />
                </div>

                <button type="submit" className="reeva-submit-btn">
                  Start Conversation
                </button>
              </form>

              <div className="reeva-ai-powered">Powered by Reeva Dev</div>
            </div>
          )}

          {/* ================================================================
              SCREEN 3: CONVERSATION INTERFACE (Image 2)
              ================================================================ */}
          {screen === 'chat' && (
            <div className="reeva-screen-chat">
              {/* Header with back button, Voice Readout toggle & exit icon */}
              <div className="reeva-nav-header">
                <div className="reeva-nav-header-left">
                  <button
                    className="reeva-back-btn"
                    onClick={() => setScreen('welcome')}
                    aria-label="Back to welcome"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="15 18 9 12 15 6" />
                    </svg>
                  </button>
                  <div className="reeva-nav-header-titles">
                    <h2>Reeva Dev</h2>
                    <p>Typically replies in a few minutes</p>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {/* Voice Conversation Auto-speak Toggle */}
                  <button
                    className={`reeva-voice-toggle-btn ${autoSpeak ? 'is-active' : ''}`}
                    title={autoSpeak ? 'Voice Audio: ON (Click to mute)' : 'Voice Audio: OFF (Click to unmute)'}
                    onClick={() => {
                      if (autoSpeak && 'speechSynthesis' in window) {
                        window.speechSynthesis.cancel()
                        setSpeakingIndex(null)
                      }
                      setAutoSpeak(!autoSpeak)
                    }}
                  >
                    {autoSpeak ? '🔊' : '🔇'}
                  </button>

                  {/* End Conversation Icon */}
                  <button
                    className="reeva-end-chat-btn"
                    title="End Conversation"
                    onClick={handleEndConversation}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                      <polyline points="16 17 21 12 16 7" />
                      <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Active document banner */}
              {documentName && (
                <div className="reeva-chat-doc-banner">
                  <span>📄 Active Document: <strong>{documentName}</strong></span>
                </div>
              )}

              {/* Chat Message Scroll */}
              <div className="reeva-chat-scroll">
                {/* Date Divider (--- Today ---) */}
                <div className="reeva-date-divider">
                  <span className="reeva-date-line" />
                  <span className="reeva-date-label">Today</span>
                  <span className="reeva-date-line" />
                </div>

                {/* Message Rows */}
                {messages.map((msg) => {
                  if (msg.role === 'user') {
                    return (
                      <div key={msg.id} className="reeva-msg-row-user">
                        <div className="reeva-user-bubble">{msg.text}</div>
                      </div>
                    )
                  }

                  return (
                    <div key={msg.id} className="reeva-msg-row-ai">
                      {/* Avatar 'R' circle from Image 2 */}
                      <div className="reeva-ai-avatar-circle">R</div>

                      <div className="reeva-ai-bubble-wrap">
                        <div className="reeva-ai-bubble">
                          <FormattedMessage text={msg.text} />
                        </div>

                        {/* Sub-label with Speaker Audio button matching Image 2 */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 4px' }}>
                          <span className="reeva-ai-sender-name">{msg.senderName || 'Reeva AI'}</span>
                          <button
                            className="reeva-msg-speaker-btn"
                            title={speakingIndex === msg.id ? 'Stop listening' : 'Listen to this response'}
                            onClick={() => speakResponse(msg.text, msg.id)}
                          >
                            {speakingIndex === msg.id ? '⏹️ Stop' : '🔊 Listen'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}

                {/* Typing Indicator */}
                {isTyping && (
                  <div className="reeva-msg-row-ai">
                    <div className="reeva-ai-avatar-circle">R</div>
                    <div className="reeva-ai-bubble-wrap">
                      <div className="reeva-ai-bubble" style={{ padding: '10px 14px' }}>
                        <span style={{ fontSize: '12px', color: '#64748b' }}>Reeva AI is analyzing document...</span>
                      </div>
                      <span className="reeva-ai-sender-name">Reeva AI</span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Suggestions Chips Bar */}
              {showSuggestions && (
                <div className="reeva-chat-suggestions">
                  {currentSuggestions.map((item, idx) => (
                    <button
                      key={idx}
                      className="reeva-suggestion-chip"
                      onClick={() => handleSend(typeof item === 'string' ? item : item.label)}
                    >
                      {typeof item === 'string' ? item : item.label}
                    </button>
                  ))}
                </div>
              )}

              {/* Contact / Phone Modal Popup */}
              {showCallModal && (
                <div className="reeva-call-modal">
                  <h4>📞 Contact Reeva Dev Support</h4>
                  <div className="reeva-call-options">
                    <a href="tel:+918320524590" className="reeva-call-link">
                      <span>India Support</span>
                      <b>+91 83205 24590</b>
                    </a>
                    <a href="tel:+18458451340" className="reeva-call-link">
                      <span>US Office</span>
                      <b>+1 845 845 1340</b>
                    </a>
                  </div>
                  <button className="reeva-call-close" onClick={() => setShowCallModal(false)}>
                    Close
                  </button>
                </div>
              )}

              {/* Chat Input Bar matching Image 2 */}
              <div className="reeva-chat-input-bar">
                <div className="reeva-input-container">
                  <input
                    type="text"
                    className="reeva-chat-input"
                    placeholder={isListening ? "Listening... speak now" : "chat with us"}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  />

                  <div className="reeva-input-actions">
                    {/* Paperclip icon */}
                    <button
                      className="reeva-icon-btn"
                      title="Quick Document Summary"
                      onClick={() => handleSend('Please provide an overview and key field summary of this document.')}
                    >
                      📎
                    </button>

                    {/* Smiley / Suggestions icon */}
                    <button
                      className="reeva-icon-btn"
                      title="Toggle Suggested Topics"
                      onClick={() => setShowSuggestions(!showSuggestions)}
                    >
                      😊
                    </button>

                    {/* Phone / Call icon */}
                    <button
                      className="reeva-icon-btn"
                      title="Call Reeva Dev"
                      onClick={() => setShowCallModal(!showCallModal)}
                    >
                      📞
                    </button>

                    {/* Microphone Voice Button */}
                    <button
                      className={`reeva-icon-btn reeva-mic-btn ${isListening ? 'is-listening' : ''}`}
                      title={isListening ? 'Stop listening' : 'Voice Input (Speak into mic)'}
                      onClick={toggleVoiceInput}
                    >
                      {isListening ? '🛑' : '🎙️'}
                    </button>

                    {/* Send button when input has text */}
                    {input.trim() && (
                      <button
                        className="reeva-send-icon-btn"
                        onClick={() => handleSend()}
                        title="Send Message"
                      >
                        ➤
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <div className="reeva-ai-powered">Powered by Reeva Dev</div>
            </div>
          )}
        </div>
      )}

      {/* Floating Launcher Button matching Image 1 */}
      <div className="reeva-ai-launcher-wrapper">
        {/* Rotating Cosmic Gradient Ring */}
        <div className={`reeva-ai-cosmic-ring ${open ? 'is-open' : ''}`} />

        {/* Pulsating Ambient Light Aura */}
        <div className="reeva-ai-ambient-glow" />

        {/* Floating Interactive Button */}
        <button
          className={`reeva-ai-launcher ${open ? 'is-open' : ''}`}
          onClick={() => setOpen(!open)}
          aria-label="Toggle Reeva AI"
        >
          {open ? (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          ) : (
            <div className="reeva-launcher-bubble-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="#ffffff">
                <path d="M4.5 3.5C3.12 3.5 2 4.62 2 6v8.5C2 15.88 3.12 17 4.5 17H6.5v3.25c0 .65.78.98 1.25.53L11.2 17H19.5c1.38 0 2.5-1.12 2.5-2.5V6c0-1.38-1.12-2.5-2.5-2.5H4.5z" />
              </svg>
            </div>
          )}
        </button>
      </div>
    </div>
  )
}
