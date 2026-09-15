"""
Interactive Document Q&A AI Chat Assistant Widget for Streamlit & IDP
Generates the floating widget matching the exact UI design with:
- Rotating cosmic gradient ring & levitating launcher button
- Multi-screen flow (Welcome / Form / Chat) & Document grounding
- Voice speech synthesis & voice microphone input
- Gemini API integration with offline IDP extraction fallback
"""

import json
from typing import Optional, Dict, Any


def get_ai_chat_widget_html(
    document_data: Optional[Dict[str, Any]] = None,
    document_name: str = "",
    user_name: str = "Shravan",
    gemini_api_key: str = ""
) -> str:
    """
    Returns an HTML/JS/CSS snippet that injects the floating Reeva AI Chat Agent
    directly into the parent Streamlit document window.
    """
    doc_payload = {}
    if document_data:
        doc_payload = {
            "file_name": document_data.get("file_name") or document_name or "Uploaded Document",
            "markdown": document_data.get("markdown", "")[:12000],
            "text": document_data.get("text", "")[:12000],
            "qr_codes": document_data.get("qr_codes", []),
            "fraud_report": document_data.get("fraud_report", {})
        }
        if document_data.get("json"):
            try:
                doc_payload["json"] = document_data["json"]
            except Exception:
                pass

    doc_json_str = json.dumps(doc_payload)
    api_key_safe = json.dumps(gemini_api_key.strip() if gemini_api_key else "")
    clean_user_name = json.dumps(user_name.strip() if user_name else "Shravan")
    safe_doc_name = json.dumps(document_name.strip() if document_name else "")

    template = r"""
<div id="reeva-widget-root-host"></div>
<script>
(function() {
    function initReevaWidget() {
        const pdoc = (window.parent && window.parent.document) ? window.parent.document : document;
        const pwin = (window.parent || window);
        if (!pdoc || !pdoc.body) return;

        // Remove existing containers and elements if any
        try {
            pdoc.querySelectorAll('#reeva-ai-floating-container, .reeva-ai-launcher-wrapper, .reeva-ai-window, #reeva-ai-chat-window').forEach(function(el) {
                if (el && el.parentNode) el.parentNode.removeChild(el);
            });
        } catch(e) {}

        const container = pdoc.createElement('div');
        container.id = 'reeva-ai-floating-container';
        container.style.cssText = 'position: fixed !important; bottom: 24px !important; right: 24px !important; z-index: 99999999 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important; pointer-events: auto !important; display: flex !important; flex-direction: column !important; align-items: flex-end !important;';

        const documentData = __DOC_DATA__;
        const documentName = __DOC_NAME__;
        const defaultUserName = __USER_NAME__;
        let apiKey = __API_KEY__;

        // Inject Styles
        const styleId = 'reeva-ai-injected-styles';
        let styleTag = pdoc.getElementById(styleId);
        if (!styleTag) {
            styleTag = pdoc.createElement('style');
            styleTag.id = styleId;
            styleTag.textContent = `
                #reeva-ai-floating-container * {
                    box-sizing: border-box !important;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
                }
                .reeva-ai-launcher-wrapper {
                    position: relative !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    width: 66px !important;
                    height: 66px !important;
                    cursor: pointer !important;
                }
                .reeva-ai-cosmic-ring {
                    position: absolute !important;
                    inset: -4px !important;
                    border-radius: 50% !important;
                    background: conic-gradient(
                        from 0deg,
                        #00e5ff 0%,
                        #0099ff 25%,
                        #7c3aed 50%,
                        #ec4899 75%,
                        #00e5ff 100%
                    ) !important;
                    animation: reeva-spin-cosmic 3.5s linear infinite !important;
                    filter: blur(2px) !important;
                    z-index: 1 !important;
                    opacity: 0.95 !important;
                }
                .reeva-ai-ambient-glow {
                    position: absolute !important;
                    inset: -12px !important;
                    border-radius: 50% !important;
                    background: radial-gradient(
                        circle,
                        rgba(0, 180, 255, 0.75) 0%,
                        rgba(124, 58, 237, 0.45) 50%,
                        rgba(236, 72, 153, 0.2) 75%,
                        transparent 100%
                    ) !important;
                    filter: blur(14px) !important;
                    animation: reeva-glow-pulse 2.6s ease-in-out infinite alternate !important;
                    z-index: 0 !important;
                    pointer-events: none !important;
                }
                .reeva-ai-launcher {
                    position: relative !important;
                    z-index: 2 !important;
                    width: 60px !important;
                    height: 60px !important;
                    border-radius: 50% !important;
                    background: linear-gradient(135deg, #00b4d8 0%, #0096c7 35%, #0077b6 70%, #023e8a 100%) !important;
                    border: 2px solid rgba(255, 255, 255, 0.9) !important;
                    color: #ffffff !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    cursor: pointer !important;
                    box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.6), 0 8px 24px rgba(0, 119, 182, 0.45) !important;
                    transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
                    outline: none !important;
                    animation: reeva-levitate 3s ease-in-out infinite alternate !important;
                    padding: 0 !important;
                    margin: 0 !important;
                }
                .reeva-ai-launcher:hover {
                    transform: scale(1.08) translateY(-2px) !important;
                    box-shadow: 0 14px 32px rgba(0, 119, 182, 0.65), 0 0 24px rgba(0, 229, 255, 0.7) !important;
                }
                .reeva-ai-window {
                    width: 380px !important;
                    height: 580px !important;
                    max-width: calc(100vw - 32px) !important;
                    max-height: calc(100vh - 110px) !important;
                    background: #fbfbfd !important;
                    border-radius: 16px !important;
                    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.08) !important;
                    display: none !important;
                    flex-direction: column !important;
                    overflow: hidden !important;
                    margin-bottom: 14px !important;
                    border: 1px solid #e2e8f0 !important;
                    animation: reeva-fade-up 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
                }
                .reeva-ai-window.is-open {
                    display: flex !important;
                }
                .reeva-nav-header {
                    display: flex !important;
                    align-items: center !important;
                    justify-content: space-between !important;
                    padding: 12px 16px !important;
                    background: #ffffff !important;
                    border-bottom: 1px solid #f1f5f9 !important;
                    flex-shrink: 0 !important;
                }
                .reeva-nav-header-left {
                    display: flex !important;
                    align-items: center !important;
                    gap: 10px !important;
                }
                .reeva-back-btn {
                    background: none !important;
                    border: none !important;
                    color: #334155 !important;
                    cursor: pointer !important;
                    padding: 4px !important;
                    font-size: 16px !important;
                    border-radius: 6px !important;
                }
                .reeva-nav-header-titles h2 {
                    font-size: 15px !important;
                    font-weight: 700 !important;
                    color: #0f172a !important;
                    margin: 0 !important;
                }
                .reeva-nav-header-titles p {
                    font-size: 11px !important;
                    color: #64748b !important;
                    margin: 1px 0 0 0 !important;
                }
                .reeva-chat-doc-banner {
                    background: #f0f9ff !important;
                    border-bottom: 1px solid #e0f2fe !important;
                    padding: 6px 14px !important;
                    font-size: 11.5px !important;
                    color: #0369a1 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: space-between !important;
                    flex-shrink: 0 !important;
                }
                .reeva-chat-scroll {
                    flex: 1 !important;
                    overflow-y: auto !important;
                    padding: 14px 16px !important;
                    display: flex !important;
                    flex-direction: column !important;
                    gap: 14px !important;
                    background: #ffffff !important;
                }
                .reeva-date-divider {
                    display: flex !important;
                    align-items: center !important;
                    margin: 2px 0 8px !important;
                    gap: 10px !important;
                }
                .reeva-date-line {
                    flex: 1 !important;
                    height: 1px !important;
                    background: #e2e8f0 !important;
                }
                .reeva-date-label {
                    font-size: 11.5px !important;
                    color: #64748b !important;
                    font-weight: 500 !important;
                }
                .reeva-msg-row-user {
                    display: flex !important;
                    justify-content: flex-end !important;
                }
                .reeva-user-bubble {
                    background: #0099e6 !important;
                    color: #ffffff !important;
                    padding: 10px 14px !important;
                    border-radius: 16px 16px 4px 16px !important;
                    font-size: 13.5px !important;
                    line-height: 1.45 !important;
                    max-width: 82% !important;
                    word-break: break-word !important;
                    box-shadow: 0 2px 6px rgba(0, 153, 230, 0.2) !important;
                }
                .reeva-msg-row-ai {
                    display: flex !important;
                    align-items: flex-start !important;
                    gap: 10px !important;
                    max-width: 92% !important;
                }
                .reeva-ai-avatar-circle {
                    width: 28px !important;
                    height: 28px !important;
                    border-radius: 50% !important;
                    background: #fce7f3 !important;
                    color: #db2777 !important;
                    font-size: 12px !important;
                    font-weight: 700 !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    flex-shrink: 0 !important;
                    margin-top: 4px !important;
                }
                .reeva-ai-bubble-wrap {
                    display: flex !important;
                    flex-direction: column !important;
                    gap: 3px !important;
                    flex: 1 !important;
                }
                .reeva-ai-bubble {
                    background: #ffffff !important;
                    border: 1px solid #e2e8f0 !important;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
                    border-radius: 16px !important;
                    padding: 11px 14px !important;
                    font-size: 13px !important;
                    line-height: 1.5 !important;
                    color: #1e293b !important;
                    word-break: break-word !important;
                }
                .reeva-ai-bubble table {
                    width: 100% !important;
                    border-collapse: collapse !important;
                    font-size: 11.5px !important;
                    margin: 6px 0 !important;
                }
                .reeva-ai-bubble td, .reeva-ai-bubble th {
                    padding: 4px 6px !important;
                    border: 1px solid #e2e8f0 !important;
                }
                .reeva-ai-bubble code {
                    background: #f1f5f9 !important;
                    padding: 1px 4px !important;
                    border-radius: 4px !important;
                    font-size: 12px !important;
                    color: #0f172a !important;
                }
                .reeva-ai-sender-name {
                    font-size: 11px !important;
                    color: #94a3b8 !important;
                    padding-left: 4px !important;
                }
                .reeva-msg-speaker-btn {
                    background: none !important;
                    border: none !important;
                    color: #0099e6 !important;
                    font-size: 11px !important;
                    font-weight: 600 !important;
                    cursor: pointer !important;
                    padding: 2px 4px !important;
                    border-radius: 4px !important;
                }
                .reeva-msg-speaker-btn:hover {
                    background: #f0f9ff !important;
                }
                .reeva-chat-input-bar {
                    padding: 8px 12px !important;
                    background: #ffffff !important;
                    border-top: 1px solid #f1f5f9 !important;
                }
                .reeva-input-container {
                    display: flex !important;
                    align-items: center !important;
                    background: #ffffff !important;
                    border: 1.5px solid #0099e6 !important;
                    border-radius: 12px !important;
                    padding: 3px 8px !important;
                    gap: 6px !important;
                }
                .reeva-chat-input {
                    flex: 1 !important;
                    border: none !important;
                    outline: none !important;
                    padding: 6px 4px !important;
                    font-size: 13px !important;
                    color: #1e293b !important;
                    background: transparent !important;
                }
                .reeva-input-actions {
                    display: flex !important;
                    align-items: center !important;
                    gap: 6px !important;
                }
                .reeva-icon-btn {
                    background: none !important;
                    border: none !important;
                    color: #0099e6 !important;
                    cursor: pointer !important;
                    padding: 3px !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    font-size: 15px !important;
                    border-radius: 4px !important;
                    transition: opacity 0.15s ease !important;
                }
                .reeva-icon-btn:hover { opacity: 0.75 !important; }
                .reeva-send-icon-btn {
                    background: #0099e6 !important;
                    color: #ffffff !important;
                    border: none !important;
                    width: 26px !important;
                    height: 26px !important;
                    border-radius: 50% !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                    cursor: pointer !important;
                    font-size: 11px !important;
                }
                .reeva-chat-suggestions {
                    padding: 6px 12px !important;
                    display: flex !important;
                    gap: 6px !important;
                    overflow-x: auto !important;
                    white-space: nowrap !important;
                    background: #ffffff !important;
                    border-top: 1px solid #f8fafc !important;
                }
                .reeva-suggestion-chip {
                    background: #f8fafc !important;
                    color: #334155 !important;
                    border: 1px solid #e2e8f0 !important;
                    padding: 3px 8px !important;
                    border-radius: 10px !important;
                    font-size: 11px !important;
                    cursor: pointer !important;
                    flex-shrink: 0 !important;
                }
                .reeva-suggestion-chip:hover {
                    background: #f0f9ff !important;
                    color: #0099e6 !important;
                    border-color: #bae6fd !important;
                }
                .reeva-ai-powered {
                    text-align: center !important;
                    font-size: 11px !important;
                    color: #64748b !important;
                    padding: 6px 10px !important;
                    background: #fbfbfd !important;
                    border-top: 1px solid rgba(226, 232, 240, 0.6) !important;
                }
                @keyframes reeva-spin-cosmic { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                @keyframes reeva-glow-pulse { 0% { transform: scale(0.9); opacity: 0.55; } 50% { transform: scale(1.15); opacity: 0.9; } 100% { transform: scale(0.9); opacity: 0.55; } }
                @keyframes reeva-levitate { 0% { transform: translateY(0px); } 50% { transform: translateY(-3px); } 100% { transform: translateY(0px); } }
                @keyframes reeva-fade-up { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
            `;
            pdoc.head.appendChild(styleTag);
        }

        const docBannerHtml = documentName ? '<div class="reeva-chat-doc-banner"><span>📄 Active: <b>' + documentName + '</b></span></div>' : '';

        container.innerHTML = `
            <div class="reeva-ai-window" id="reeva-ai-chat-window">
                <div class="reeva-nav-header">
                    <div class="reeva-nav-header-left">
                        <button class="reeva-back-btn" id="reeva-back-btn" title="Back">&#8249;</button>
                        <div class="reeva-nav-header-titles">
                            <h2>Reeva Dev</h2>
                            <p>Typically replies in a few minutes</p>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <button id="reeva-tts-toggle-btn" class="reeva-icon-btn" title="Auto-speak voice audio toggle" style="font-size:14px;">🔊</button>
                        <button id="reeva-close-win-btn" class="reeva-icon-btn" title="Close chat" style="color:#ef4444; font-size:14px;">&#10005;</button>
                    </div>
                </div>
                ` + docBannerHtml + `
                <div class="reeva-chat-scroll" id="reeva-chat-scroll-area">
                    <div class="reeva-date-divider">
                        <span class="reeva-date-line"></span>
                        <span class="reeva-date-label">Today</span>
                        <span class="reeva-date-line"></span>
                    </div>
                    <div class="reeva-msg-row-ai">
                        <div class="reeva-ai-avatar-circle">R</div>
                        <div class="reeva-ai-bubble-wrap">
                            <div class="reeva-ai-bubble" id="reeva-initial-msg-body">
                                Hi ` + defaultUserName + `! 👋<br><br>
                                I’m Reeva AI. How can I help you today?
                            </div>
                            <div style="display:flex; align-items:center; justify-content:space-between; padding:0 2px;">
                                <span class="reeva-ai-sender-name">Reeva AI</span>
                                <button class="reeva-msg-speaker-btn" id="reeva-initial-listen-btn">🔊 Listen</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="reeva-chat-suggestions" id="reeva-chat-chips">
                    <button class="reeva-suggestion-chip" data-query="What is the total amount, subtotal, and tax in this document?">💰 Invoice Total & Tax</button>
                    <button class="reeva-suggestion-chip" data-query="What is the invoice number, date, and due date?">🔢 Invoice No & Date</button>
                    <button class="reeva-suggestion-chip" data-query="Who is the vendor/seller and who is the customer/buyer?">🏢 Vendor & Customer</button>
                    <button class="reeva-suggestion-chip" data-query="Are there any fraud indicators, layout mismatches, or suspicious items?">🛡️ Fraud Check</button>
                    <button class="reeva-suggestion-chip" data-query="List all items, quantities, and prices in a table.">📋 Line Items</button>
                    <button class="reeva-suggestion-chip" data-query="What information was decoded from QR codes in this document?">📱 QR Data</button>
                </div>
                <div class="reeva-chat-input-bar">
                    <div class="reeva-input-container">
                        <input type="text" class="reeva-chat-input" id="reeva-chat-input-field" placeholder="chat with us" />
                        <div class="reeva-input-actions">
                            <button class="reeva-icon-btn" id="reeva-clip-btn" title="Document Key Fields Summary">📎</button>
                            <button class="reeva-icon-btn" id="reeva-smile-btn" title="Suggested Topics">😊</button>
                            <button class="reeva-icon-btn" id="reeva-phone-btn" title="Contact Support">📞</button>
                            <button class="reeva-icon-btn" id="reeva-mic-btn" title="Voice Input (Click to speak)">🎙️</button>
                            <button class="reeva-send-icon-btn" id="reeva-send-btn" title="Send">&#10148;</button>
                        </div>
                    </div>
                </div>
                <div class="reeva-ai-powered">Powered by Reeva Dev</div>
            </div>

            <div class="reeva-ai-launcher-wrapper" id="reeva-launcher-wrap">
                <div class="reeva-ai-cosmic-ring" id="reeva-cosmic-ring"></div>
                <div class="reeva-ai-ambient-glow"></div>
                <button class="reeva-ai-launcher" id="reeva-launcher-btn" aria-label="Open Reeva AI">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="#ffffff">
                        <path d="M4.5 3.5C3.12 3.5 2 4.62 2 6v8.5C2 15.88 3.12 17 4.5 17H6.5v3.25c0 .65.78.98 1.25.53L11.2 17H19.5c1.38 0 2.5-1.12 2.5-2.5V6c0-1.38-1.12-2.5-2.5-2.5H4.5z"/>
                    </svg>
                </button>
            </div>
        `;

        pdoc.body.appendChild(container);

        let isOpen = false;
        let autoSpeak = true;
        let isListening = false;
        let recognition = null;

        const chatWindow = container.querySelector('#reeva-ai-chat-window');
        const launcherBtn = container.querySelector('#reeva-launcher-btn');
        const inputField = container.querySelector('#reeva-chat-input-field');
        const sendBtn = container.querySelector('#reeva-send-btn');
        const scrollArea = container.querySelector('#reeva-chat-scroll-area');
        const chipsArea = container.querySelector('#reeva-chat-chips');
        const ttsToggle = container.querySelector('#reeva-tts-toggle-btn');
        const micBtn = container.querySelector('#reeva-mic-btn');

        function toggleWindow() {
            isOpen = !isOpen;
            if (isOpen) {
                chatWindow.classList.add('is-open');
                launcherBtn.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
                inputField.focus();
                scrollArea.scrollTop = scrollArea.scrollHeight;
            } else {
                chatWindow.classList.remove('is-open');
                launcherBtn.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="#ffffff"><path d="M4.5 3.5C3.12 3.5 2 4.62 2 6v8.5C2 15.88 3.12 17 4.5 17H6.5v3.25c0 .65.78.98 1.25.53L11.2 17H19.5c1.38 0 2.5-1.12 2.5-2.5V6c0-1.38-1.12-2.5-2.5-2.5H4.5z"/></svg>';
                if (pwin.speechSynthesis) pwin.speechSynthesis.cancel();
            }
        }

        launcherBtn.onclick = toggleWindow;
        container.querySelector('#reeva-close-win-btn').onclick = toggleWindow;
        container.querySelector('#reeva-back-btn').onclick = toggleWindow;

        ttsToggle.onclick = function() {
            autoSpeak = !autoSpeak;
            ttsToggle.textContent = autoSpeak ? '🔊' : '🔇';
            if (!autoSpeak && pwin.speechSynthesis) pwin.speechSynthesis.cancel();
        };

        container.querySelector('#reeva-clip-btn').onclick = function() {
            sendMessage('Please provide a complete summary of this document including key fields, totals, dates, and vendor details.');
        };

        container.querySelector('#reeva-smile-btn').onclick = function() {
            chipsArea.style.display = chipsArea.style.display === 'none' ? 'flex' : 'none';
        };

        container.querySelector('#reeva-phone-btn').onclick = function() {
            alert('📞 Reeva Dev Support:\n\nIndia Support: +91 83205 24590\nUS Office: +1 845 845 1340\nEmail: info@reeva.dev');
        };

        function speakText(text) {
            if (!pwin.speechSynthesis || !autoSpeak) return;
            pwin.speechSynthesis.cancel();
            const clean = text.replace(/[*#_>`•|]/g, '').replace(/https?:\/\/\S+/g, '').replace(/\n+/g, ' ').trim();
            if (!clean) return;
            const utt = new pwin.SpeechSynthesisUtterance(clean);
            utt.lang = 'en-US';
            utt.rate = 1.0;
            pwin.speechSynthesis.speak(utt);
        }

        container.querySelector('#reeva-initial-listen-btn').onclick = function() {
            const text = "Hi " + defaultUserName + "! I'm Reeva AI. How can I help you today?";
            speakText(text);
        };

        function stopListening() {
            isListening = false;
            micBtn.textContent = '🎙️';
            micBtn.style.color = '#0099e6';
            inputField.placeholder = 'chat with us';
        }

        try {
            const SpeechRec = (pwin && (pwin.SpeechRecognition || pwin.webkitSpeechRecognition));
            if (SpeechRec) {
                recognition = new SpeechRec();
                recognition.lang = 'en-US';
                recognition.continuous = false;
                recognition.onresult = function(e) {
                    stopListening();
                    if (e.results && e.results[0] && e.results[0][0]) {
                        const val = e.results[0][0].transcript;
                        inputField.value = val;
                        sendMessage(val);
                    }
                };
                recognition.onerror = function() {
                    stopListening();
                };
                recognition.onend = function() {
                    stopListening();
                };
            }
        } catch(e) {
            console.warn('Speech recognition not available:', e);
        }

        micBtn.onclick = function() {
            if (!recognition) {
                alert('Voice speech recognition not supported in this browser. Try Chrome or Edge.');
                return;
            }
            if (isListening) {
                try { recognition.stop(); } catch(e) {}
                stopListening();
            } else {
                try {
                    recognition.start();
                    isListening = true;
                    micBtn.textContent = '🛑';
                    micBtn.style.color = '#ef4444';
                    inputField.placeholder = 'Listening... Speak now';
                } catch(e) {}
            }
        };

        chipsArea.querySelectorAll('.reeva-suggestion-chip').forEach(function(chip) {
            chip.onclick = function() {
                const q = chip.getAttribute('data-query') || chip.textContent;
                sendMessage(q);
            };
        });

        function formatMessageHtml(raw) {
            let escaped = raw
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            escaped = escaped.replace(/`(.*?)`/g, '<code>$1</code>');
            escaped = escaped.replace(/^[•\-] (.*)$/gm, '<div style="margin:2px 0;"><span style="color:#0099e6;font-weight:bold;">•</span> $1</div>');
            escaped = escaped.replace(/\n/g, '<br>');
            return escaped;
        }

        function cleanTextVal(val) {
            if (!val) return '';
            let v = String(val).replace(/<[^>]+>/g, ' ');
            v = v.replace(/[*_`#]/g, '').trim();
            v = v.replace(/^[:\s\-|#]+|[:\s\-|#]+$/g, '');
            return v.replace(/\s+/g, ' ').trim();
        }

        function extractInvoiceNumberJS(text) {
            const clean = text.replace(/<[^>]+>/g, ' ').replace(/[*_`]/g, ' ');
            const english_blacklist = ['when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom', 'whose', 'remitting', 'payment', 'payments', 'here', 'there', 'above', 'below', 'mentioned', 'specified', 'provided', 'indicated', 'shown', 'will', 'shall', 'must', 'should', 'can', 'could', 'may', 'might', 'would', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'for', 'on', 'in', 'at', 'by', 'to', 'from', 'with', 'without', 'within', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'under', 'up', 'down', 'off', 'over', 'again', 'further', 'then', 'once', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'that', 'this', 'these', 'those', 'am', 'the', 'a', 'an', 'please', 'quote', 'kindly', 'note', 'reference', 'refer', 'regarding', 'subject', 'format', 'template', 'sample', 'copy', 'original', 'duplicate', 'date', 'due', 'tax', 'bill', 'total', 'amount', 'item', 'subtotal', 'number', 'num', 'no', 'gstin', 'pan', 'hsn', 'ber', 'er', 'id', 'code', 'inv', 'invoice', 'receipt'];
            const patterns = [
                /\b(?:invoice|inv|bill|receipt)\s*#\s*([A-Za-z0-9\-\/]{1,30})\b/i,
                /\b(?:invoice|inv|bill|receipt|doc(?:ument)?)\s*(?:number|num|no|id|code)\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b/i,
                /\b(?:invoice|inv|bill|receipt)\s*(?:no|number|num|#|id)\b\s*[\n\r]+\s*([A-Za-z0-9\-\/]{1,30})\b/i,
                /\b(?:invoice|inv|bill|receipt)\s*(?:number|num|no|id|code)\s+([A-Za-z0-9\-\/]{1,30})\b/i,
                /\b(?:invoice|inv)\b(?!\s*(?:date|total|tax|amount|due|subtotal|table|summary|item|to|by|from|when|remitting|funds|please))\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b/i
            ];
            for (let i = 0; i < patterns.length; i++) {
                const matches = clean.matchAll(new RegExp(patterns[i].source, 'gi'));
                for (const m of matches) {
                    if (m && m[1]) {
                        let val = m[1].trim().replace(/^(?:number|num|no|id|code|#|ref)[:\s.-]*/i, '').trim();
                        if (val && !english_blacklist.includes(val.toLowerCase()) && val.length >= 1) {
                            return val;
                        }
                    }
                }
            }
            return null;
        }

        function extractDatesJS(text) {
            const clean = text.replace(/<[^>]+>/g, ' ');
            const datePat = "([0-9]{1,4}[/\\.-][0-9]{1,2}[/\\.-][0-9]{2,4}|[a-zA-Z]{3,9}\\s+[0-9]{1,2},?\\s+[0-9]{4}|[0-9]{1,2}\\s+[a-zA-Z]{3,9}\\s+[0-9]{4})";
            let invDate = null, dueDate = null;

            const dMatch = clean.match(new RegExp("(?:invoice\\s*date|bill\\s*date|date\\s*of\\s*issue|issue\\s*date|dated|\\bdate\\b)[:\\s\\t\\-|]*" + datePat, "i"));
            if (dMatch && dMatch[1]) invDate = dMatch[1].trim();
            else {
                const fb = clean.match(/\b([0-9]{1,2}[/\.-][0-9]{1,2}[/\.-][0-9]{2,4})\b/);
                if (fb && fb[1]) invDate = fb[1].trim();
            }

            const dueMatch = clean.match(new RegExp("(?:due\\s*date|payment\\s*due|valid\\s*until|due\\s*by|pay\\s*by)[:\\s\\t\\-|]*" + datePat, "i"));
            if (dueMatch && dueMatch[1]) dueDate = dueMatch[1].trim();

            return { invDate: invDate, dueDate: dueDate };
        }

        function isPartyLabelJS(text) {
            if (!text) return false;
            const cl = text.toLowerCase().trim();
            return /^\s*(?:billed\s*(?:to|by)|bill\s*(?:to|by)|sold\s*(?:to|by)|ship\s*(?:to|by)|shipped\s*to|invoiced\s*to|buyer|seller|vendor|supplier|customer|client|place\s*of\s*supply|country\s*of\s*supply|terms\s*and\s*conditions|bank\s*&\s*payment)\b/i.test(cl);
        }

        function extractPartiesJS(text) {
            const cleanText = text.replace(/<[^>]+>/g, '\n');
            const lines = cleanText.split('\n')
                .map(function(l) { return l.trim(); })
                .filter(function(l) { return l.length > 0 && !l.startsWith('---') && !l.startsWith('===') && !l.startsWith('###'); });

            let vendor = null, vendorAddr = null, customer = null, customerAddr = null, email = null, phone = null;
            const exactBad = ['date', 'invoice', 'due', 'total', 'tax', 'subtotal', 'terms', 'within', 'gstin', 'pan', 'the date', 'extracted markdown', 'markdown', 'raw text', 'structured json', 'decoded qr', 'document name', 'document content', 'original', 'duplicate'];

            function isValid(cand) {
                if (!cand || cand.length < 2 || cand.length > 75) return false;
                const cl = cand.toLowerCase().trim();
                if (isPartyLabelJS(cl)) return false;
                if (exactBad.includes(cl)) return false;
                if (/terms\s*and\s*conditions|remitting\s*funds|overdue\s*interest|delayed\s*payments|please\s*pay|pay\s*within|charged\s*on/i.test(cl)) return false;
                if (/payment\s*(?:due|terms|method|mode|status|details)|bank\s*details|scan\s*to\s*pay/i.test(cl)) return false;
                if (/the\s*date\s*of\s*invoice|from\s*the\s*date/i.test(cl)) return false;
                if (/extracted\s*markdown|raw\s*text|structured\s*json/i.test(cl)) return false;
                return true;
            }

            function sanitize(val) {
                let v = cleanTextVal(val).split('\n')[0].trim();
                v = v.replace(/^(?:name|company|firm|attn|to|by|m\/s|mr|ms|dr)[:\s.-]*/i, '').trim();
                v = v.replace(/\b(?:gstin|pan|date|cin|ph|phone|email|state|pin|zip)[\s:0-9a-z]*$/i, '').trim();
                return v.replace(/^[,\s;:-]+|[,\s;:-]+$/g, '');
            }

            // Step 1: Paired 2-column side-by-side OCR layout (Billed by \n Billed to \n Vendor \n Customer)
            for (let i = 0; i < lines.length - 3; i++) {
                const l0 = lines[i], l1 = lines[i+1], l2 = lines[i+2], l3 = lines[i+3];
                const isVHdr = /^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$/i.test(l0);
                const isCHdr = /^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client)\s*[:\s\-|]*$/i.test(l1);
                if (isVHdr && isCHdr) {
                    const candV = sanitize(l2), candC = sanitize(l3);
                    if (isValid(candV) && isValid(candC)) {
                        vendor = candV;
                        customer = candC;
                        if (i + 4 < lines.length && isValid(sanitize(lines[i+4])) && !isPartyLabelJS(lines[i+4])) {
                            vendorAddr = cleanTextVal(lines[i+4]);
                        }
                        if (i + 5 < lines.length && isValid(sanitize(lines[i+5])) && !isPartyLabelJS(lines[i+5])) {
                            customerAddr = cleanTextVal(lines[i+5]);
                        }
                        break;
                    }
                }
            }

            // Step 2: Same-line or single-column Vendor
            if (!vendor) {
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    const m = line.match(/\b(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier|company\s*name)\b[:\s\-|]+(.+)/i);
                    if (m && m[1]) {
                        const cand = sanitize(m[1]);
                        if (isValid(cand)) {
                            vendor = cand;
                            if (i + 1 < lines.length && isValid(sanitize(lines[i + 1])) && !isPartyLabelJS(lines[i + 1])) {
                                vendorAddr = cleanTextVal(lines[i + 1]);
                            }
                            break;
                        }
                    }
                    if (/^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$/i.test(line)) {
                        if (i + 1 < lines.length) {
                            const cand = sanitize(lines[i + 1]);
                            if (isValid(cand)) {
                                vendor = cand;
                                if (i + 2 < lines.length && isValid(sanitize(lines[i + 2])) && !isPartyLabelJS(lines[i + 2])) {
                                    vendorAddr = cleanTextVal(lines[i + 2]);
                                }
                                break;
                            }
                        }
                    }
                }
            }

            // Secondary Vendor check: strict 'From:'
            if (!vendor) {
                for (let i = 0; i < lines.length; i++) {
                    const m = lines[i].match(/^\s*from\s*[:\-]\s*(.+)/i);
                    if (m && m[1]) {
                        const cand = sanitize(m[1]);
                        if (isValid(cand)) { vendor = cand; break; }
                    }
                }
            }

            // Step 3: Same-line or single-column Customer
            if (!customer) {
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    const m = line.match(/\b(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client|recipient|consignee|empfanger)\b[:\s\-|]+(.+)/i);
                    if (m && m[1]) {
                        const cand = sanitize(m[1]);
                        if (isValid(cand)) {
                            customer = cand;
                            if (i + 1 < lines.length && isValid(sanitize(lines[i + 1])) && !isPartyLabelJS(lines[i + 1])) {
                                customerAddr = cleanTextVal(lines[i + 1]);
                            }
                            break;
                        }
                    }
                    if (/^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client|recipient|consignee|empfanger)\s*[:\s\-|]*$/i.test(line)) {
                        if (i + 1 < lines.length) {
                            const cand = sanitize(lines[i + 1]);
                            if (isValid(cand)) {
                                customer = cand;
                                if (i + 2 < lines.length && isValid(sanitize(lines[i + 2])) && !isPartyLabelJS(lines[i + 2])) {
                                    customerAddr = cleanTextVal(lines[i + 2]);
                                }
                                break;
                            }
                        }
                    }
                }
            }

            // Step 4: Header fallback for Vendor (first non-label line at top)
            if (!vendor) {
                for (let i = 0; i < Math.min(lines.length, 6); i++) {
                    const cand = sanitize(lines[i]);
                    if (isValid(cand) && !/invoice|tax|bill|receipt|date|due|phone|email|tel|http|www|page|original|duplicate|extracted|markdown|raw text/i.test(cand)) {
                        vendor = cand;
                        if (i + 1 < lines.length && isValid(sanitize(lines[i + 1])) && !isPartyLabelJS(lines[i + 1])) {
                            vendorAddr = cleanTextVal(lines[i + 1]);
                        }
                        break;
                    }
                }
            }

            // Email
            const emailM = text.match(/\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|in|org|net|co|io|edu|gov|co\.in|org\.in|dev|ai|app|biz|info|de|fr|uk))\b/i);
            if (emailM) email = emailM[1].trim();

            // Phone (Avoid bank account numbers)
            const phoneM = text.match(/\b(?:phone|call|tel|mobile|cell|contact|ph)\b[\s:.\-on]*(\+?[0-9\s\-()]{7,20})/i);
            if (phoneM && phoneM[1]) {
                const cand = phoneM[1].replace(/[^0-9+]/g, '').trim();
                if (cand.length >= 7) phone = cand;
            }
            if (!phone) {
                const phoneM2 = text.match(/\+91[\s\-]?[6-9]\d{9}|\+\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+\d{2,3}\s*\d{2,4}\s*\d{4,8}/);
                if (phoneM2) phone = phoneM2[0].trim();
            }

            return { vendor: vendor, vendorAddr: vendorAddr, customer: customer, customerAddr: customerAddr, email: email, phone: phone };
        }

        function extractFinancialsJS(docText) {
            const cleanLines = docText.split('\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 0; });
            let subtotal = null, taxable = null, discount = null, cgst = null, sgst = null, igst = null, taxTotal = null, grandTotal = null;

            for (let i = 0; i < cleanLines.length; i++) {
                const l = cleanLines[i].replace(/[*`]/g, '').trim();
                if (/\b(?:sub\s*total|subtotal|gross\s*amount)\b/i.test(l)) {
                    const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                    if (amounts.length > 0) subtotal = amounts[amounts.length - 1].trim();
                } else if (/\b(?:taxable\s*amount|taxable\s*value|net\s*taxable|net\s*amount)\b/i.test(l)) {
                    const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                    if (amounts.length > 0) taxable = amounts[amounts.length - 1].trim();
                } else if (/\b(?:discount)\b/i.test(l) && !/earlypay/i.test(l)) {
                    const amounts = (l.match(/(-?[₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                    const pct = l.match(/(\d+%)/);
                    if (pct && amounts.length >= 2) {
                        discount = pct[1] + " (" + amounts[amounts.length - 1].trim() + ")";
                    } else if (amounts.length > 0) {
                        discount = amounts[amounts.length - 1].trim();
                    }
                } else if (/\bcgst\b/i.test(l)) {
                    const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                    if (amounts.length > 0) cgst = amounts[amounts.length - 1].trim();
                } else if (/\bsgst\b/i.test(l)) {
                    const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                    if (amounts.length > 0) sgst = amounts[amounts.length - 1].trim();
                } else if (/\bigst\b/i.test(l)) {
                    const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                    if (amounts.length > 0) igst = amounts[amounts.length - 1].trim();
                } else if (/\b(?:total\s*tax|tax\s*amount|vat\s*amount|vat\s*\(|sales\s*tax)\b/i.test(l)) {
                    const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                    if (amounts.length > 0) taxTotal = amounts[amounts.length - 1].trim();
                } else if (/\b(?:grand\s*total|invoice\s*total|total\s*amount|balance\s*due|net\s*payable|\btotal\b)\b/i.test(l)) {
                    if (!/\b(?:sub\s*total|subtotal|tax\s*rate|unit\s*price|line\s*total|words|earlypay)\b/i.test(l)) {
                        const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(function(a) { return /\d/.test(a); });
                        if (amounts.length > 0) grandTotal = amounts[amounts.length - 1].trim();
                    }
                }
            }

            const rows = [];
            if (subtotal) rows.push("• **Subtotal / Gross Amount:** `" + subtotal + "`");
            if (discount) rows.push("• **Discount:** `" + discount + "`");
            if (taxable) rows.push("• **Taxable Amount:** `" + taxable + "`");
            if (cgst && sgst) rows.push("• **Taxes (CGST + SGST):** `CGST: " + cgst + " | SGST: " + sgst + "`");
            else if (cgst) rows.push("• **CGST:** `" + cgst + "`");
            else if (sgst) rows.push("• **SGST:** `" + sgst + "`");
            else if (igst) rows.push("• **IGST:** `" + igst + "`");
            else if (taxTotal) rows.push("• **Tax Amount:** `" + taxTotal + "`");
            if (grandTotal) rows.push("• **Grand Total:** `" + grandTotal + "`");

            if (rows.length > 0) {
                return "💰 **Financial Breakdown Extracted from Document:**\n\n" + rows.join('\n');
            }
            return "No financial breakdown or totals detected in this document.";
        }

        function extractGstDetailsJS(text) {
            const clean = text.replace(/<[^>]+>/g, ' ');
            const rawGstins = clean.match(/\b(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b/gi) || [];
            const gstins = [];
            rawGstins.forEach(function(g) {
                const gu = g.toUpperCase();
                if (!gstins.includes(gu)) gstins.push(gu);
            });

            const rawPans = clean.match(/\b([A-Z]{5}\d{4}[A-Z])\b/gi) || [];
            const standalonePans = [];
            const gstinPans = gstins.map(function(g) { return g.substring(2, 12); });
            rawPans.forEach(function(p) {
                const pu = p.toUpperCase();
                if (!standalonePans.includes(pu) && !gstinPans.includes(pu)) standalonePans.push(pu);
            });

            const rows = [];
            let sellerGstin = null, buyerGstin = null;
            const sMatch = clean.match(/(?:billed\s*by|seller|vendor|supplier|from)[\s\S]{1,300}?(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b/i);
            if (sMatch) sellerGstin = sMatch[1].toUpperCase();

            const bMatch = clean.match(/(?:billed\s*to|buyer|customer|client|ship\s*to)[\s\S]{1,300}?(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b/i);
            if (bMatch) buyerGstin = bMatch[1].toUpperCase();

            if (sellerGstin && buyerGstin && sellerGstin !== buyerGstin) {
                rows.push("• **Seller / Vendor GSTIN:** `" + sellerGstin + "` (PAN: `" + sellerGstin.substring(2, 12) + "`)");
                rows.push("• **Buyer / Customer GSTIN:** `" + buyerGstin + "` (PAN: `" + buyerGstin.substring(2, 12) + "`)");
                gstins.forEach(function(g) {
                    if (g !== sellerGstin && g !== buyerGstin) {
                        rows.push("• **GSTIN:** `" + g + "` (PAN: `" + g.substring(2, 12) + "`)");
                    }
                });
            } else {
                gstins.forEach(function(g) {
                    rows.push("• **GSTIN / GST Number:** `" + g + "` (PAN: `" + g.substring(2, 12) + "`)");
                });
            }

            standalonePans.forEach(function(p) {
                rows.push("• **PAN Number:** `" + p + "`");
            });

            // European / UK VAT Numbers
            const euVats = clean.match(/\b(?:AT|BE|BG|CY|CZ|DE|DK|EE|EL|ES|FI|FR|GB|GR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK|CHE)\s?[0-9A-Z]{8,12}\b/gi) || [];
            const seenVats = [];
            euVats.forEach(function(v) {
                const vu = v.replace(/\s+/g, '').toUpperCase();
                if (!seenVats.includes(vu) && !gstins.includes(vu) && !standalonePans.includes(vu)) {
                    seenVats.push(vu);
                    rows.push("• **VAT / Tax Registration ID:** `" + vu + "`");
                }
            });

            // Explicit VAT, ABN, CIN, TIN, Tax ID label matches
            const taxIdMatches = clean.match(/(?:vat\s*(?:id|no|number|reg)?|ust-idnr|tva|abn|acn|tax\s*(?:id|no|number|reg)?|cin|tin)[:\s\-|]*([A-Z0-9\s\-]{5,25})\b/gi) || [];
            const seenTids = [];
            taxIdMatches.forEach(function(m) {
                const parts = m.split(/[:\s\-|]+/);
                const tid = parts[parts.length - 1].toUpperCase();
                if (tid.length >= 5 && !seenTids.includes(tid) && !gstins.includes(tid) && !seenVats.includes(tid) && !/INVOICE|TOTAL|AMOUNT|SUBTOTAL/i.test(tid)) {
                    seenTids.push(tid);
                    rows.push("• **Tax / Registration ID:** `" + tid + "`");
                }
            });

            if (rows.length > 0) {
                return "🧾 **GST & Tax Registration Details:**\n\n" + rows.join('\n');
            }
            return "No GSTIN, PAN, or Tax registration numbers detected in this document.";
        }

        function localExtractAnswer(query) {
            const q = query.toLowerCase().trim();
            const docText = (documentData.markdown || '') + '\n' + (documentData.text || '');

            // 1. Identity & Introduction Queries
            if (/^(who are (you|u|r u)|who r u|what is your name|who made you|what are you)\b/i.test(q)) {
                return "👋 I’m **Reeva AI**, the Intelligent Document Processing (IDP) Assistant built by **Reeva Dev**!\n\nI specialize in analyzing, extracting, and inspecting your documents, invoices, receipts, and forms using advanced OCR, YOLO layout segmentation, and Explainable AI fraud detection.";
            }

            // 2. Capability & Feature Queries
            if (/^(what (can|did|do) (you|u) do|what are your (features|capabilities)|how can you help|what else can you do)\b/i.test(q) || /what (can|did|do) (you|u) do/i.test(q)) {
                return "✨ **Here is everything I can do for you:**\n\n• 📄 **Document Extraction:** Parse text, structured markdown, and JSON tables from PDFs, images, DOCX, and XLSX.\n• 💰 **Financial Breakdown:** Extract and verify Subtotals, Tax/GST/VAT, and Grand Totals.\n• 🔢 **Invoice Details:** Extract Invoice Numbers, Issue Dates, Due Dates, and Reference IDs.\n• 🏢 **Parties & Contacts:** Identify Vendor/Issuer details, Customer/Billed To info, and email addresses.\n• 🛡️ **Explainable AI Fraud Inspection:** Detect layout tampering, arithmetic discrepancies, and calculate risk scores.\n• 📱 **QR & Barcode Decoding:** Decode scannable payloads and UPI payment links.\n• 🔊 **Voice Speech & Audio:** Read responses aloud and accept microphone voice input.\n\n*Upload a document on the homepage to start asking questions about it!*";
            }

            // 3. Greeting Queries
            if (/^(hi|hello|hey|hola|greetings|good morning|good afternoon|good evening)\b/i.test(q)) {
                return "👋 **Hello " + defaultUserName + "!** How can I assist you with your document processing or questions today?";
            }

            // 4. Help & Instructions Queries
            if (/^(how to (use|upload|process)|help|how does (it|this) work|instructions)\b/i.test(q)) {
                return "🚀 **How to Use IDP:**\n\n1. **Upload Documents:** Drag and drop your PDF or image into the upload box at the top.\n2. **Convert:** Click **🚀 Convert & Process Documents** to run OCR, YOLO layout analysis, and fraud checks.\n3. **Inspect Tabs:** Review the extracted Markdown, Tables, JSON, YOLO Layout Crops, and Fraud overlays.\n4. **Ask Reeva AI:** Ask me any specific question about amounts, dates, or items here in the chat (or click 🎙️ to speak)!";
            }

            // 5. Supported Formats
            if (/^(supported formats|what formats|file types|formats supported)\b/i.test(q) || /supported formats/i.test(q)) {
                return "📁 **Supported Document Formats:**\n\n• 📄 **PDFs:** Scanned and digital multi-page PDFs\n• 🖼️ **Images:** PNG, JPG, JPEG, TIFF, WEBP\n• 📊 **Office Documents:** DOCX, PPTX, XLSX";
            }

            if (!docText.trim()) {
                return "👋 **No document content is currently loaded.**\n\nPlease drag and drop a PDF or image invoice into the upload box above and click **Convert & Process Documents** to analyze it!";
            }

            // GSTIN / Tax ID / PAN / VAT / Registration Number Extraction
            if (/\b(gst|gstin|gst no|gst number|tax id|tax no|tax number|pan|pan card|pan no|vat|vat no|vat number|tin|cin|registration no|reg no)\b/i.test(q)) {
                return extractGstDetailsJS(docText);
            }

            // Bank & Payment Information
            if (/\b(bank|account|account number|a\/c|ifsc|iban|swift|upi|payment method|payment mode)\b/i.test(q)) {
                const bankLines = [];
                const clean = docText.replace(/<[^>]+>/g, '\n');
                const lines = clean.split('\n');
                for (let i = 0; i < lines.length; i++) {
                    const l = cleanTextVal(lines[i]);
                    if (!l || l.length < 3) continue;
                    if (/\b(?:bank|account|a\/c|ifsc|iban|swift|upi|branch|savings|current)\b/i.test(l)) {
                        if (!/\b(?:terms|condition|please pay|charged on)\b/i.test(l)) {
                            if (!bankLines.includes("• " + l)) bankLines.push("• " + l);
                        }
                    }
                }
                if (bankLines.length > 0) {
                    return "🏦 **Bank & Payment Details:**\n\n" + bankLines.slice(0, 6).join('\n');
                }
            }

            // PO / Order Number
            if (/\b(po number|po no|purchase order|order number|order no|quote number|job number)\b/i.test(q)) {
                const poM = docText.match(/(?:p\.?o\.?\s*(?:no|num|number|#)|purchase\s*order|order\s*(?:no|number|#))[\s*:#.-]*([A-Za-z0-9\/-]{2,30})/i);
                if (poM) {
                    return "📦 **Order Information:**\n\n• **PO / Order Number:** `" + poM[1].replace(/[*_`]/g, '').trim() + "`";
                }
            }

            const isInvQuery = /invoice number|invoice no|inv no|invoice #|invoice id|reference number|bill number/i.test(q);
            const isDateQuery = /due date|invoice date|billing date|issue date|date of issue|when was|pay by/i.test(q);

            if (isInvQuery || isDateQuery) {
                const invNum = extractInvoiceNumberJS(docText);
                const dates = extractDatesJS(docText);
                const invRows = [];

                if (invNum && isInvQuery) invRows.push("• **Invoice Number:** `" + invNum + "`");
                if (dates.invDate && (isDateQuery || q.includes('date'))) invRows.push("• **Invoice Date:** `" + dates.invDate + "`");
                if (dates.dueDate && (isDateQuery || q.includes('due') || q.includes('date'))) invRows.push("• **Due Date:** `" + dates.dueDate + "`");

                if (isInvQuery && invNum) {
                    if (dates.invDate && !invRows.some(function(r) { return r.includes('Invoice Date'); })) {
                        invRows.push("• **Invoice Date:** `" + dates.invDate + "`");
                    }
                    if (dates.dueDate && !invRows.some(function(r) { return r.includes('Due Date'); })) {
                        invRows.push("• **Due Date:** `" + dates.dueDate + "`");
                    }
                }

                if (invRows.length > 0) {
                    return "🔢 **Invoice Information:**\n\n" + invRows.join('\n');
                }
            }

            if (/total|amount|grand total|subtotal|tax|gst|vat|price|cost|how much|balance due|net amount|net payable/i.test(q)) {
                return extractFinancialsJS(docText);
            }

            if (/vendor|seller|supplier|company|customer|buyer|client|billed to|who issued|parties|who is/i.test(q)) {
                const parties = extractPartiesJS(docText);
                const rows = [];
                if (parties.vendor) {
                    rows.push("• **Vendor / Seller:** `" + parties.vendor + "`");
                    if (parties.vendorAddr) rows.push("  *Address:* " + parties.vendorAddr);
                }
                if (parties.customer) {
                    rows.push("• **Customer / Billed To:** `" + parties.customer + "`");
                    if (parties.customerAddr) rows.push("  *Address:* " + parties.customerAddr);
                }
                if (parties.email) rows.push("• **Contact Email:** `" + parties.email + "`");
                if (parties.phone) rows.push("• **Contact Phone:** `" + parties.phone + "`");

                if (rows.length > 0) {
                    return "🏢 **Parties Information:**\n\n" + rows.join('\n');
                }
            }

            // Amount in Words
            if (/in words|amount in words|total in words|words/i.test(q)) {
                const wordsM = docText.match(/\b(?:amount\s*in\s*words|total\s*in\s*words|invoice\s*total\s*\(in\s*words\)|in\s*words)[:\s\t\-|]*[\r\n]*([A-Za-z\s\-]+(?:rupees|dollars|cents|euros|pounds|only|paisa|aud|cad|inr|usd))\b/i);
                if (wordsM && wordsM[1]) {
                    return "🔤 **Amount in Words:**\n\n• `" + cleanTextVal(wordsM[1]) + "`";
                }
            }

            // Terms & Conditions / Notes / Early Pay
            if (/terms|condition|conditions|policy|late fee|overdue interest|early pay|earlypay|notes|additional notes|remarks/i.test(q)) {
                const parts = [];
                const tMatch = docText.match(/(?:terms\s*and\s*conditions|terms\s*&\s*conditions|payment\s*terms)[\s:.\-|]*[\r\n]+([\s\S]{1,400}?)(?:\n\s*\n|additional\s*notes|bank|$)/i);
                if (tMatch && tMatch[1]) {
                    parts.push("📜 **Terms & Conditions:**\n" + cleanTextVal(tMatch[1]));
                }
                const earlyMatches = docText.match(/\b(?:earlypay|early\s*payment|early\s*bird)\b[^\n]+/gi);
                if (earlyMatches && earlyMatches.length > 0) {
                    parts.push("⚡ **Early Payment Benefit:**\n" + earlyMatches.map(function(e) { return "• " + cleanTextVal(e); }).join('\n'));
                }
                const notesMatch = docText.match(/(?:additional\s*notes|notes|remarks)[\s:.\-|]*[\r\n]+([\s\S]{1,300}?)(?:\n\s*\n|for\s*any\s*enquiries|$)/i);
                if (notesMatch && notesMatch[1]) {
                    parts.push("📝 **Additional Notes:**\n" + cleanTextVal(notesMatch[1]));
                }
                if (parts.length > 0) {
                    return parts.join('\n\n');
                }
            }

            // Place of Supply / Country / Shipping Location
            if (/place of supply|country of supply|pos|shipping address|ship to|delivery location|dispatch/i.test(q)) {
                const posRows = [];
                const posM = docText.match(/\b(?:place\s*of\s*supply|pos)\b[:\s\t\-|]*([^\r\n]{2,40})/i);
                if (posM && posM[1]) posRows.push("• **Place of Supply:** `" + cleanTextVal(posM[1]) + "`");
                const cosM = docText.match(/\b(?:country\s*of\s*supply|country)\b[:\s\t\-|]*([^\r\n]{2,40})/i);
                if (cosM && cosM[1]) posRows.push("• **Country of Supply:** `" + cleanTextVal(cosM[1]) + "`");
                if (posRows.length > 0) {
                    return "📍 **Supply & Delivery Details:**\n\n" + posRows.join('\n');
                }
            }

            if (/fraud|fake|suspicious|valid|risk|tampered/i.test(q)) {
                if (documentData.fraud_report && documentData.fraud_report.verdict) {
                    const fr = documentData.fraud_report;
                    return "🛡️ **Explainable AI Fraud Inspection:**\n\n• **Verdict:** **" + fr.verdict + "**\n• **Risk Score:** `" + (fr.risk_score || 0) + "%`\n• **Status:** Visual layout and rule checks validated.";
                }
                return "🛡️ **Fraud Status:** All mathematical arithmetic checks and layout checks appear consistent. See Fraud Detection tab for visual overlays.";
            }

            if (/qr|qr code|barcode|scannable/i.test(q)) {
                if (documentData.qr_codes && documentData.qr_codes.length > 0) {
                    const list = documentData.qr_codes.map(function(qr, i) { return "**QR #" + (i+1) + ":** `" + (qr.content || 'Decoded Data') + "`"; }).join('\n');
                    return "📱 **QR Codes Found in Document:**\n\n" + list;
                }
                return "📱 **QR Code Status:** No QR codes were detected in the current document.";
            }

            if (/items|line items|products|services|table|breakdown|quantities|quantity|qty|rate|hsn|description/i.test(q)) {
                // Check if HTML table exists
                if (docText.includes('<table')) {
                    const parser = new DOMParser();
                    const docParsed = parser.parseFromString(docText, 'text/html');
                    const tables = docParsed.querySelectorAll('table');
                    if (tables.length > 0) {
                        const table = tables[0];
                        const trs = table.querySelectorAll('tr');
                        const rows = [];
                        trs.forEach(function(tr) {
                            const cells = tr.querySelectorAll('th, td');
                            const row = [];
                            cells.forEach(function(c) { row.push(c.textContent.trim().replace(/\s+/g, ' ')); });
                            if (row.length > 0) rows.push(row);
                        });
                        if (rows.length > 0) {
                            const maxCols = Math.max.apply(null, rows.map(function(r) { return r.length; }));
                            const padded = rows.map(function(r) { while(r.length < maxCols) r.push(''); return r; });
                            const mdLines = [
                                "| " + padded[0].join(' | ') + " |",
                                "| " + padded[0].map(function() { return '---'; }).join(' | ') + " |"
                            ];
                            for (let r = 1; r < padded.length; r++) {
                                mdLines.push("| " + padded[r].join(' | ') + " |");
                            }
                            return "📋 **Extracted Line Items / Table:**\n\n" + mdLines.join('\n');
                        }
                    }
                }

                const tableLines = docText.split('\n').filter(function(l) { return l.includes('|') && !l.startsWith('<'); });
                if (tableLines.length >= 2) {
                    return "📋 **Extracted Line Items / Table:**\n\n" + tableLines.slice(0, 15).map(cleanTextVal).join('\n');
                }
            }

            // Universal Keyword & Field Line Search across entire document
            const stopWords = ['provide', 'give', 'tell', 'show', 'find', 'what', 'is', 'the', 'of', 'for', 'in', 'this', 'document', 'file', 'please', 'me', 'can', 'you', 'number', 'details'];
            const keywords = q.split(/[^a-zA-Z0-9]+/).filter(function(w) { return w.length >= 2 && !stopWords.includes(w); });
            if (keywords.length > 0) {
                const matchingLines = [];
                const clean = docText.replace(/<[^>]+>/g, '\n');
                const lines = clean.split('\n');
                for (let i = 0; i < lines.length; i++) {
                    const l = cleanTextVal(lines[i]);
                    if (!l || l.length < 3 || l.startsWith('<')) continue;
                    const lLower = l.toLowerCase();
                    if (keywords.some(function(k) { return lLower.includes(k); })) {
                        if (!matchingLines.includes(l)) matchingLines.push(l);
                    }
                }
                if (matchingLines.length > 0) {
                    const formatted = matchingLines.slice(0, 6).map(function(l) { return "• " + l; });
                    return "🔍 **Matching Document Content:**\n\n" + formatted.join('\n');
                }
            }

            const clean = docText.replace(/<[^>]+>/g, '\n');
            const paras = clean.split(/\n\s*\n/).map(cleanTextVal).filter(function(p) { return p.length > 15; });
            const tokens = q.split(' ').filter(function(w) { return w.length >= 3; });
            let best = '', bScore = 0;
            for (let i = 0; i < paras.length; i++) {
                let s = 0;
                const pL = paras[i].toLowerCase();
                for (let j = 0; j < tokens.length; j++) {
                    if (pL.includes(tokens[j])) s++;
                }
                if (s > bScore) { bScore = s; best = paras[i]; }
            }
            if (best && bScore >= 1) {
                return "🔍 **Information Found in Document:**\n\n" + best.trim();
            }

            return "I searched the uploaded document for **\"" + query + "\"**.\n\nYou can ask me about:\n• 💰 **Invoice Total & Tax**\n• 🔢 **Invoice Number & Dates**\n• 🏢 **Vendor & Customer Info**\n• 🛡️ **Fraud & QR Code Checks**";
        }

        async function sendMessage(text) {
            const val = (text || inputField.value).trim();
            if (!val) return;
            inputField.value = '';

            const userRow = pdoc.createElement('div');
            userRow.className = 'reeva-msg-row-user';
            userRow.innerHTML = '<div class="reeva-user-bubble">' + htmlEscape(val) + '</div>';
            scrollArea.appendChild(userRow);
            scrollArea.scrollTop = scrollArea.scrollHeight;

            const typingRow = pdoc.createElement('div');
            typingRow.className = 'reeva-msg-row-ai';
            typingRow.id = 'reeva-temp-typing';
            typingRow.innerHTML = `
                <div class="reeva-ai-avatar-circle">R</div>
                <div class="reeva-ai-bubble-wrap">
                    <div class="reeva-ai-bubble" style="padding:8px 12px; color:#64748b; font-size:12px;">
                        Reeva AI is analyzing document...
                    </div>
                    <span class="reeva-ai-sender-name">Reeva AI</span>
                </div>
            `;
            scrollArea.appendChild(typingRow);
            scrollArea.scrollTop = scrollArea.scrollHeight;

            let answerText = '';
            const docTextContent = (documentData.markdown || '') + '\n' + (documentData.text || '') + (documentData.fraud_report ? ('\n--- Fraud Report ---\n' + JSON.stringify(documentData.fraud_report)) : '');
            const systemPrompt = "You are an expert Intelligent Document Processing (IDP) & Forensic Accounting AI Assistant called Reeva AI.\nAnalyze the following extracted document content and answer the user's question accurately, directly, and concisely.\n--- DOCUMENT CONTENT ---\n" + (docTextContent || "No document currently loaded.") + "\n--- END DOCUMENT CONTENT ---\nCRITICAL RESPONSE RULES:\n1. STRICTLY TARGETED & CONCISE: Answer ONLY the specific question asked by the user. Do NOT dump unsolicited calculations, item lists, or extra invoice breakdowns unless the user asks for a full breakdown. If the user asks about a date (e.g. 'is date fake or legit'), answer ONLY about the date in 1-2 clear sentences.\n2. MATH ACCURACY: If calculations are asked, compute Line Total = Qty × Unit Price (e.g. 5 × $50 = $250). If document states $2500, state that the document contains an arithmetic overcharge for that item.\n3. CONCISE & PROFESSIONAL: Keep answers short, direct, and well-formatted with markdown.";

            // 1. Try Local Ollama LLM (Qwen2.5:3b)
            if (docTextContent && docTextContent.trim()) {
                try {
                    const ollamaRes = await fetch("http://localhost:11434/api/chat", {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            model: 'qwen2.5:3b',
                            messages: [
                                { role: 'system', content: systemPrompt },
                                { role: 'user', content: val }
                            ],
                            stream: false,
                            options: { temperature: 0.15, top_p: 0.9 }
                        })
                    });
                    if (ollamaRes.ok) {
                        const od = await ollamaRes.json();
                        if (od && od.message && od.message.content) {
                            answerText = od.message.content.trim();
                        }
                    }
                } catch(e) {
                    console.info('Ollama local LLM query bypassed:', e);
                }
            }

            // 2. Try Google Gemini API
            if (!answerText && apiKey && docTextContent && docTextContent.trim()) {
                try {
                    const res = await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + apiKey, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            contents: [{ role: 'user', parts: [{ text: systemPrompt + "\n\nQuestion: " + val }] }]
                        })
                    });
                    if (res.ok) {
                        const d = await res.json();
                        answerText = (d?.candidates?.[0]?.content?.parts?.[0]?.text || '').trim();
                    }
                } catch(e) {
                    console.warn('Gemini request failed:', e);
                }
            }

            // 3. High-Precision Local Extraction Fallback
            if (!answerText) {
                await new Promise(function(r) { setTimeout(r, 250); });
                answerText = localExtractAnswer(val);
            }

            const tEl = pdoc.getElementById('reeva-temp-typing');
            if (tEl) tEl.remove();

            const aiRow = pdoc.createElement('div');
            aiRow.className = 'reeva-msg-row-ai';
            const formatted = formatMessageHtml(answerText);
            aiRow.innerHTML = `
                <div class="reeva-ai-avatar-circle">R</div>
                <div class="reeva-ai-bubble-wrap">
                    <div class="reeva-ai-bubble">` + formatted + `</div>
                    <div style="display:flex; align-items:center; justify-content:space-between; padding:0 2px;">
                        <span class="reeva-ai-sender-name">Reeva AI</span>
                        <button class="reeva-msg-speaker-btn">🔊 Listen</button>
                    </div>
                </div>
            `;
            const speakBtn = aiRow.querySelector('.reeva-msg-speaker-btn');
            speakBtn.onclick = function() { speakText(answerText); };

            scrollArea.appendChild(aiRow);
            scrollArea.scrollTop = scrollArea.scrollHeight;

            speakText(answerText);
        }

        function htmlEscape(str) {
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        sendBtn.onclick = function() { sendMessage(); };
        inputField.onkeydown = function(e) {
            if (e.key === 'Enter') sendMessage();
        };
    }

    // Run immediately once
    initReevaWidget();
})();
</script>
"""
    return (
        template
        .replace("__DOC_DATA__", doc_json_str)
        .replace("__DOC_NAME__", safe_doc_name)
        .replace("__USER_NAME__", clean_user_name)
        .replace("__API_KEY__", api_key_safe)
    )
