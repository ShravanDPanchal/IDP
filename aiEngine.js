/**
 * Intelligent Document Processing (IDP) AI Assistant Engine
 * 
 * Supports:
 * 1. Document-grounded Q&A via Google Gemini API (gemini-1.5-flash / gemini-2.0-flash)
 * 2. Intelligent local RAG & field extraction fallback (offline or without API key)
 * 3. General IDP knowledge base and contextual document starter prompts
 */

// General IDP Starter Prompts
export const idpStarterPrompts = [
  { label: '💰 Invoice Total & Tax', query: 'What is the total amount, subtotal, and tax in this document?' },
  { label: '🔢 Invoice No & Date', query: 'What is the invoice number, date, and due date?' },
  { label: '🏢 Vendor & Customer', query: 'Who is the vendor/seller and who is the customer/buyer?' },
  { label: '🛡️ Fraud & Risk Check', query: 'Are there any fraud indicators, layout mismatches, or suspicious items?' },
  { label: '📋 List Line Items', query: 'List all items, quantities, unit prices, and line totals in a table.' },
  { label: '📱 QR Code Data', query: 'What information was decoded from the QR codes in this document?' }
]

// Fallback general starter prompts if no document is uploaded yet
export const noDocStarterPrompts = [
  { label: '📄 How to upload files?', query: 'How do I upload and extract documents with this IDP system?' },
  { label: '🔍 Supported File Formats', query: 'What file formats and document types are supported?' },
  { label: '🎯 YOLO Layout Analysis', query: 'How does YOLO layout segmentation and crop inspection work?' },
  { label: '🛡️ Invoice Fraud Detection', query: 'How does the Explainable AI Fraud Detection feature work?' }
]

// Helper: Normalize text for matching
function cleanText(text) {
  return (text || '')
    .toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Main Answer Generation Function
 * 
 * @param {string} query - User question / prompt
 * @param {string} [apiKey] - Optional Google Gemini API Key
 * @param {string|object} [documentData] - Extracted document text, markdown, or JSON object
 * @param {object} [options] - Additional options (e.g. documentName, history)
 * @returns {Promise<{ text: string, suggestions?: string[], actionLinks?: Array<{label: string, path?: string, href?: string}> }>}
 */
export async function generateSmartAnswer(query, apiKey, documentData, options = {}) {
  const trimmedQuery = (query || '').trim()
  const docName = options.documentName || 'Uploaded Document'

  if (!trimmedQuery) {
    if (documentData) {
      return {
        text: `📄 **Document Loaded:** \`${docName}\`\n\nI have analyzed your document content. What would you like to know about it? You can ask about invoice totals, dates, vendor details, line items, QR codes, or fraud checks.`,
        suggestions: idpStarterPrompts.map(p => p.label)
      }
    }
    return {
      text: "👋 **Hello! I'm your Intelligent Document Processing (IDP) AI Assistant.**\n\nPlease upload a PDF or image document on the homepage to start asking questions, or ask me how the IDP system works!",
      suggestions: noDocStarterPrompts.map(p => p.label)
    }
  }

  // If documentData is provided, prepare normalized string
  let docString = ''
  if (documentData) {
    if (typeof documentData === 'object') {
      try {
        // Extract relevant parts for clean prompting
        const parts = []
        if (documentData.file_name) parts.push(`File Name: ${documentData.file_name}`)
        if (documentData.markdown) parts.push(`--- Extracted Markdown Content ---\n${documentData.markdown}`)
        if (documentData.text && documentData.text !== documentData.markdown) {
          parts.push(`--- Extracted Raw Text ---\n${documentData.text}`)
        }
        if (documentData.qr_codes && documentData.qr_codes.length > 0) {
          parts.push(`--- Decoded QR Codes ---\n${JSON.stringify(documentData.qr_codes, null, 2)}`)
        }
        if (documentData.json && Object.keys(documentData.json).length > 0) {
          parts.push(`--- Structured JSON Data ---\n${JSON.stringify(documentData.json, null, 2)}`)
        }
        if (documentData.fraud_report) {
          parts.push(`--- Fraud Detection Analysis ---\n${JSON.stringify(documentData.fraud_report, null, 2)}`)
        }
        docString = parts.length > 0 ? parts.join('\n\n') : JSON.stringify(documentData, null, 2)
      } catch {
        docString = JSON.stringify(documentData, null, 2)
      }
    } else {
      docString = String(documentData).trim()
    }
  }

  // -------------------------------------------------------------------------
  // 1. TRY GEMINI LLM API (If API key provided)
  // -------------------------------------------------------------------------
  const effectiveApiKey = apiKey || (typeof process !== 'undefined' && process.env?.GEMINI_API_KEY) || ''
  
  if (effectiveApiKey && docString) {
    try {
      const systemPrompt = `You are an Intelligent Document Processing (IDP) AI Assistant.
Analyze the following extracted document content and answer the user's question accurately.
--- DOCUMENT CONTENT ---
${docString}
--- END DOCUMENT CONTENT ---

Instructions:
1. Answer strictly based on the document data provided above.
2. If the information is not present in the document, politely state that it's not found in the uploaded file.
3. Keep responses clear, concise, and highlight key extracted fields (like Invoice No, Dates, Totals, Names, Line Items, etc.) using markdown formatting.
4. Format tables nicely when displaying itemized lists or financial breakdowns.`

      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${effectiveApiKey}`

      const payload = {
        contents: [
          {
            role: 'user',
            parts: [{ text: `${systemPrompt}\n\nUser Question: ${trimmedQuery}` }]
          }
        ],
        generationConfig: {
          temperature: 0.2,
          maxOutputTokens: 1200
        }
      }

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (res.ok) {
        const data = await res.json()
        const text = data?.candidates?.[0]?.content?.parts?.[0]?.text
        if (text && text.trim()) {
          return {
            text: text.trim(),
            suggestions: [
              '💰 What is the total amount?',
              '📅 Extract invoice dates',
              '🛡️ Any fraud detected?',
              '📋 Show item list'
            ]
          }
        }
      } else {
        console.warn('Gemini API returned error status:', res.status)
      }
    } catch (err) {
      console.warn('Gemini API call failed, falling back to local document engine:', err)
    }
  }

  // -------------------------------------------------------------------------
  // 2. LOCAL INTELLIGENT DOCUMENT PARSER & RAG (Offline Fallback)
  // -------------------------------------------------------------------------
  if (docString) {
    return generateLocalDocumentAnswer(trimmedQuery, docString, documentData)
  }

  // -------------------------------------------------------------------------
  // 3. GENERAL IDP SYSTEM ANSWERS (When no document is uploaded)
  // -------------------------------------------------------------------------
  return generateGeneralIdpAnswer(trimmedQuery)
}

/**
 * Intelligent Local Document Grounding Engine
 */
function generateLocalDocumentAnswer(query, docText, rawDocData) {
  const qLower = cleanText(query)
  const cleanStr = String(docText || '').replace(/<[^>]+>/g, ' ')

  // Helper functions
  const cleanVal = (val) => {
    if (!val) return ''
    return String(val).replace(/[*_`#]/g, '').replace(/^[:\s\-|#]+|[:\s\-|#]+$/g, '').trim()
  }

  // 1. GST & Tax Registration Details
  if (/\b(gst|gstin|gst no|gst number|tax id|tax no|tax number|pan|pan card|pan no|vat|vat no|vat number|tin|cin|registration no|reg no)\b/i.test(qLower)) {
    const rawGstins = cleanStr.match(/\b(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b/gi) || []
    const gstins = []
    rawGstins.forEach(g => {
      const gu = g.toUpperCase()
      if (!gstins.includes(gu)) gstins.push(gu)
    })

    const rawPans = cleanStr.match(/\b([A-Z]{5}\d{4}[A-Z])\b/gi) || []
    const standalonePans = []
    const gstinPans = gstins.map(g => g.substring(2, 12))
    rawPans.forEach(p => {
      const pu = p.toUpperCase()
      if (!standalonePans.includes(pu) && !gstinPans.includes(pu)) standalonePans.push(pu)
    })

    const rows = []
    let sellerGstin = null, buyerGstin = null
    const sMatch = cleanStr.match(/(?:billed\s*by|seller|vendor|supplier|from)[\s\S]{1,300}?(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b/i)
    if (sMatch) sellerGstin = sMatch[1].toUpperCase()

    const bMatch = cleanStr.match(/(?:billed\s*to|buyer|customer|client|ship\s*to)[\s\S]{1,300}?(\d{2}[A-Z]{5}\d{4}[A-Z0-9]{4})\b/i)
    if (bMatch) buyerGstin = bMatch[1].toUpperCase()

    if (sellerGstin && buyerGstin && sellerGstin !== buyerGstin) {
      rows.push(`• **Seller / Vendor GSTIN:** \`${sellerGstin}\` (PAN: \`${sellerGstin.substring(2, 12)}\`)`)
      rows.push(`• **Buyer / Customer GSTIN:** \`${buyerGstin}\` (PAN: \`${buyerGstin.substring(2, 12)}\`)`)
      gstins.forEach(g => {
        if (g !== sellerGstin && g !== buyerGstin) {
          rows.push(`• **GSTIN:** \`${g}\` (PAN: \`${g.substring(2, 12)}\`)`)
        }
      })
    } else {
      gstins.forEach(g => {
        rows.push(`• **GSTIN / GST Number:** \`${g}\` (PAN: \`${g.substring(2, 12)}\`)`)
      })
    }

    standalonePans.forEach(p => {
      rows.push(`• **PAN Number:** \`${p}\``)
    })

    // European / UK VAT Numbers
    const euVats = cleanStr.match(/\b(?:AT|BE|BG|CY|CZ|DE|DK|EE|EL|ES|FI|FR|GB|GR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK|CHE)\s?[0-9A-Z]{8,12}\b/gi) || []
    const seenVats = []
    euVats.forEach(v => {
      const vu = v.replace(/\s+/g, '').toUpperCase()
      if (!seenVats.includes(vu) && !gstins.includes(vu) && !standalonePans.includes(vu)) {
        seenVats.push(vu)
        rows.push(`• **VAT / Tax Registration ID:** \`${vu}\``)
      }
    })

    // Explicit VAT, ABN, CIN, TIN, Tax ID label matches
    const taxIdMatches = cleanStr.match(/(?:vat\s*(?:id|no|number|reg)?|ust-idnr|tva|abn|acn|tax\s*(?:id|no|number|reg)?|cin|tin)[:\s\-|]*([A-Z0-9\s\-]{5,25})\b/gi) || []
    const seenTids = []
    taxIdMatches.forEach(m => {
      const parts = m.split(/[:\s\-|]+/)
      const tid = parts[parts.length - 1].toUpperCase()
      if (tid.length >= 5 && !seenTids.includes(tid) && !gstins.includes(tid) && !seenVats.includes(tid) && !/INVOICE|TOTAL|AMOUNT|SUBTOTAL/i.test(tid)) {
        seenTids.push(tid)
        rows.push(`• **Tax / Registration ID:** \`${tid}\``)
      }
    })

    if (rows.length > 0) {
      return {
        text: `🧾 **GST & Tax Registration Details:**\n\n${rows.join('\n')}`,
        suggestions: ['💰 Invoice Total', '🔢 Invoice Number', '🏢 Vendor Details']
      }
    }
  }

  // 2. Invoice Number & Dates Extraction
  const isInvQuery = /\b(invoice number|invoice no|inv no|invoice #|invoice id|reference number|bill number|receipt number|document number)\b/i.test(qLower)
  const isDateQuery = /\b(due date|invoice date|billing date|issue date|date of issue|when was|pay by)\b/i.test(qLower)

  if (isInvQuery || isDateQuery) {
    let invNum = null
    const english_blacklist = ['when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom', 'whose', 'remitting', 'payment', 'payments', 'here', 'there', 'above', 'below', 'mentioned', 'specified', 'provided', 'indicated', 'shown', 'will', 'shall', 'must', 'should', 'can', 'could', 'may', 'might', 'would', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'for', 'on', 'in', 'at', 'by', 'to', 'from', 'with', 'without', 'within', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'under', 'up', 'down', 'off', 'over', 'again', 'further', 'then', 'once', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'that', 'this', 'these', 'those', 'am', 'the', 'a', 'an', 'please', 'quote', 'kindly', 'note', 'reference', 'refer', 'regarding', 'subject', 'format', 'template', 'sample', 'copy', 'original', 'duplicate', 'date', 'due', 'tax', 'bill', 'total', 'amount', 'item', 'subtotal', 'number', 'num', 'no', 'gstin', 'pan', 'hsn', 'ber', 'er', 'id', 'code', 'inv', 'invoice', 'receipt']
    const invPatterns = [
      /\b(?:invoice|inv|bill|receipt)\s*#\s*([A-Za-z0-9\-\/]{1,30})\b/i,
      /\b(?:invoice|inv|bill|receipt|doc(?:ument)?)\s*(?:number|num|no|id|code)\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b/i,
      /\b(?:invoice|inv|bill|receipt)\s*(?:no|number|num|#|id)\b\s*[\n\r]+\s*([A-Za-z0-9\-\/]{1,30})\b/i,
      /\b(?:invoice|inv|bill|receipt)\s*(?:number|num|no|id|code)\s+([A-Za-z0-9\-\/]{1,30})\b/i,
      /\b(?:invoice|inv)\b(?!\s*(?:date|total|tax|amount|due|subtotal|table|summary|item|to|by|from|when|remitting|funds|please))\s*[:#.\-|]\s*([A-Za-z0-9\-\/]{1,30})\b/i
    ]
    for (let i = 0; i < invPatterns.length; i++) {
      const matches = cleanStr.matchAll(new RegExp(invPatterns[i].source, 'gi'))
      for (const m of matches) {
        if (m && m[1]) {
          let val = m[1].trim().replace(/^(?:number|num|no|id|code|#|ref)[:\s.-]*/i, '').trim()
          if (val && !english_blacklist.includes(val.toLowerCase()) && val.length >= 1) {
            invNum = val
            break
          }
        }
      }
      if (invNum) break
    }

    const datePat = "([0-9]{1,4}[/\\.-][0-9]{1,2}[/\\.-][0-9]{2,4}|[a-zA-Z]{3,9}\\s+[0-9]{1,2},?\\s+[0-9]{4}|[0-9]{1,2}\\s+[a-zA-Z]{3,9}\\s+[0-9]{4})"
    let invDate = null, dueDate = null
    const dMatch = cleanStr.match(new RegExp("(?:invoice\\s*date|bill\\s*date|date\\s*of\\s*issue|issue\\s*date|dated|\\bdate\\b)[:\\s\\t\\-|]*" + datePat, "i"))
    if (dMatch && dMatch[1]) invDate = dMatch[1].trim()
    else {
      const fb = cleanStr.match(/\b([0-9]{1,2}[/\.-][0-9]{1,2}[/\.-][0-9]{2,4})\b/)
      if (fb && fb[1]) invDate = fb[1].trim()
    }

    const dueMatch = cleanStr.match(new RegExp("(?:due\\s*date|payment\\s*due|valid\\s*until|due\\s*by|pay\\s*by)[:\\s\\t\\-|]*" + datePat, "i"))
    if (dueMatch && dueMatch[1]) dueDate = dueMatch[1].trim()

    const invRows = []
    if (invNum && isInvQuery) invRows.push(`• **Invoice Number:** \`${invNum}\``)
    if (invDate && (isDateQuery || qLower.includes('date'))) invRows.push(`• **Invoice Date:** \`${invDate}\``)
    if (dueDate && (isDateQuery || qLower.includes('due') || qLower.includes('date'))) invRows.push(`• **Due Date:** \`${dueDate}\``)

    if (isInvQuery && invNum) {
      if (invDate && !invRows.some(r => r.includes('Invoice Date'))) invRows.push(`• **Invoice Date:** \`${invDate}\``)
      if (dueDate && !invRows.some(r => r.includes('Due Date'))) invRows.push(`• **Due Date:** \`${dueDate}\``)
    }

    if (invRows.length > 0) {
      return {
        text: `🔢 **Invoice Information:**\n\n${invRows.join('\n')}`,
        suggestions: ['📅 Invoice Dates', '💰 Invoice Total', '🏢 Vendor & Customer']
      }
    }
  }

  // 3. Parties Information (Vendor vs Customer)
  if (/\b(vendor|seller|supplier|company|customer|buyer|client|billed to|who issued|parties|who is)\b/i.test(qLower)) {
    const lines = String(docText || '').replace(/<[^>]+>/g, '\n').split('\n').map(l => l.trim()).filter(l => l.length > 0 && !l.startsWith('---') && !l.startsWith('===') && !l.startsWith('###'))
    let vendor = null, vendorAddr = null, customer = null, customerAddr = null, email = null, phone = null
    const exactBad = ['date', 'invoice', 'due', 'total', 'tax', 'subtotal', 'terms', 'within', 'gstin', 'pan', 'the date', 'extracted markdown', 'markdown', 'raw text', 'structured json', 'decoded qr', 'document name', 'document content', 'original', 'duplicate']

    const isPartyLabel = (t) => {
      if (!t) return false
      const cl = t.toLowerCase().trim()
      return /^\s*(?:billed\s*(?:to|by)|bill\s*(?:to|by)|sold\s*(?:to|by)|ship\s*(?:to|by)|shipped\s*to|invoiced\s*to|buyer|seller|vendor|supplier|customer|client|place\s*of\s*supply|country\s*of\s*supply|terms\s*and\s*conditions|bank\s*&\s*payment)\b/i.test(cl)
    }

    const isValid = (cand) => {
      if (!cand || cand.length < 2 || cand.length > 75) return false
      const cl = cand.toLowerCase().trim()
      if (isPartyLabel(cl)) return false
      if (exactBad.includes(cl)) return false
      if (/terms\s*and\s*conditions|remitting\s*funds|overdue\s*interest|delayed\s*payments|please\s*pay|pay\s*within|charged\s*on/i.test(cl)) return false
      if (/payment\s*(?:due|terms|method|mode|status|details)|bank\s*details|scan\s*to\s*pay/i.test(cl)) return false
      if (/the\s*date\s*of\s*invoice|from\s*the\s*date/i.test(cl)) return false
      if (/extracted\s*markdown|raw\s*text|structured\s*json/i.test(cl)) return false
      return true
    }

    const sanitize = (val) => {
      let v = cleanVal(val).split('\n')[0].trim()
      v = v.replace(/^(?:name|company|firm|attn|to|by|m\/s|mr|ms|dr)[:\s.-]*/i, '').trim()
      v = v.replace(/\b(?:gstin|pan|date|cin|ph|phone|email|state|pin|zip)[\s:0-9a-z]*$/i, '').trim()
      return v.replace(/^[,\s;:-]+|[,\s;:-]+$/g, '')
    }

    // Step 1: Paired 2-column side-by-side OCR layout (Billed by \n Billed to \n Vendor \n Customer)
    for (let i = 0; i < lines.length - 3; i++) {
      const l0 = lines[i], l1 = lines[i+1], l2 = lines[i+2], l3 = lines[i+3]
      const isVHdr = /^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$/i.test(l0)
      const isCHdr = /^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client)\s*[:\s\-|]*$/i.test(l1)
      if (isVHdr && isCHdr) {
        const candV = sanitize(l2), candC = sanitize(l3)
        if (isValid(candV) && isValid(candC)) {
          vendor = candV
          customer = candC
          if (i + 4 < lines.length && isValid(sanitize(lines[i+4])) && !isPartyLabel(lines[i+4])) {
            vendorAddr = cleanVal(lines[i+4])
          }
          if (i + 5 < lines.length && isValid(sanitize(lines[i+5])) && !isPartyLabel(lines[i+5])) {
            customerAddr = cleanVal(lines[i+5])
          }
          break
        }
      }
    }

    // Step 2: Same-line or single-column Vendor
    if (!vendor) {
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        const m = line.match(/\b(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier|company\s*name)\b[:\s\-|]+(.+)/i)
        if (m && m[1]) {
          const cand = sanitize(m[1])
          if (isValid(cand)) {
            vendor = cand
            if (i + 1 < lines.length && isValid(sanitize(lines[i + 1])) && !isPartyLabel(lines[i + 1])) {
              vendorAddr = cleanVal(lines[i + 1])
            }
            break
          }
        }
        if (/^\s*(?:billed\s*by|bill\s*by|sold\s*by|issued\s*by|seller|vendor|supplier)\s*[:\s\-|]*$/i.test(line)) {
          if (i + 1 < lines.length) {
            const cand = sanitize(lines[i + 1])
            if (isValid(cand)) {
              vendor = cand
              if (i + 2 < lines.length && isValid(sanitize(lines[i + 2])) && !isPartyLabel(lines[i + 2])) {
                vendorAddr = cleanVal(lines[i + 2])
              }
              break
            }
          }
        }
      }
    }

    // Secondary Vendor check: strict 'From:'
    if (!vendor) {
      for (let i = 0; i < lines.length; i++) {
        const m = lines[i].match(/^\s*from\s*[:\-]\s*(.+)/i)
        if (m && m[1]) {
          const cand = sanitize(m[1])
          if (isValid(cand)) { vendor = cand; break }
        }
      }
    }

    // Step 3: Same-line or single-column Customer
    if (!customer) {
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        const m = line.match(/\b(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client|recipient|consignee|empfanger)\b[:\s\-|]+(.+)/i)
        if (m && m[1]) {
          const cand = sanitize(m[1])
          if (isValid(cand)) {
            customer = cand
            if (i + 1 < lines.length && isValid(sanitize(lines[i + 1])) && !isPartyLabel(lines[i + 1])) {
              customerAddr = cleanVal(lines[i + 1])
            }
            break
          }
        }
        if (/^\s*(?:billed\s*to|bill\s*to|sold\s*to|ship\s*to|shipped\s*to|invoiced\s*to|buyer|customer|client|recipient|consignee|empfanger)\s*[:\s\-|]*$/i.test(line)) {
          if (i + 1 < lines.length) {
            const cand = sanitize(lines[i + 1])
            if (isValid(cand)) {
              customer = cand
              if (i + 2 < lines.length && isValid(sanitize(lines[i + 2])) && !isPartyLabel(lines[i + 2])) {
                customerAddr = cleanVal(lines[i + 2])
              }
              break
            }
          }
        }
      }
    }

    // Step 4: Header fallback for Vendor (first non-label line at top)
    if (!vendor) {
      for (let i = 0; i < Math.min(lines.length, 6); i++) {
        const cand = sanitize(lines[i])
        if (isValid(cand) && !/invoice|tax|bill|receipt|date|due|phone|email|tel|http|www|page|original|duplicate|extracted|markdown|raw text/i.test(cand)) {
          vendor = cand
          if (i + 1 < lines.length && isValid(sanitize(lines[i + 1])) && !isPartyLabel(lines[i + 1])) {
            vendorAddr = cleanVal(lines[i + 1])
          }
          break
        }
      }
    }

    const emailM = docText.match(/\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|in|org|net|co|io|edu|gov|co\.in|org\.in|dev|ai|app|biz|info))\b/i)
    if (emailM) email = emailM[1].trim()

    const phoneM = docText.match(/(?:\+?91[\s\-]?)?[6-9]\d{9}|\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/)
    if (phoneM) phone = phoneM[0].trim()

    const rows = []
    if (vendor) {
      rows.push(`• **Vendor / Seller:** \`${vendor}\``)
      if (vendorAddr) rows.push(`  *Address:* ${vendorAddr}`)
    }
    if (customer) {
      rows.push(`• **Customer / Billed To:** \`${customer}\``)
      if (customerAddr) rows.push(`  *Address:* ${customerAddr}`)
    }
    if (email) rows.push(`• **Contact Email:** \`${email}\``)
    if (phone) rows.push(`• **Contact Phone:** \`${phone}\``)

    if (rows.length > 0) {
      return {
        text: `🏢 **Parties Information:**\n\n${rows.join('\n')}`,
        suggestions: ['💰 Invoice Total', '🔢 Invoice Number', '🧾 GST & Tax Details']
      }
    }
  }

  // 4. Financial Breakdown & Totals
  if (/\b(total|amount|grand total|subtotal|tax|gst|vat|price|cost|how much|balance due|net amount|net payable)\b/i.test(qLower)) {
    const cleanLines = String(docText || '').replace(/<[^>]+>/g, '\n').split('\n').map(l => l.trim()).filter(l => l.length > 0)
    let subtotal = null, taxable = null, discount = null, cgst = null, sgst = null, igst = null, taxTotal = null, grandTotal = null

    for (let i = 0; i < cleanLines.length; i++) {
      const l = cleanLines[i].replace(/[*`]/g, '').trim()
      if (/\b(?:sub\s*total|subtotal|gross\s*amount)\b/i.test(l)) {
        const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
        if (amounts.length > 0) subtotal = amounts[amounts.length - 1].trim()
      } else if (/\b(?:taxable\s*amount|taxable\s*value|net\s*taxable|net\s*amount)\b/i.test(l)) {
        const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
        if (amounts.length > 0) taxable = amounts[amounts.length - 1].trim()
      } else if (/\b(?:discount)\b/i.test(l) && !/earlypay/i.test(l)) {
        const amounts = (l.match(/(-?[₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
        const pct = l.match(/(\d+%)/)
        if (pct && amounts.length >= 2) {
          discount = `${pct[1]} (${amounts[amounts.length - 1].trim()})`
        } else if (amounts.length > 0) {
          discount = amounts[amounts.length - 1].trim()
        }
      } else if (/\bcgst\b/i.test(l)) {
        const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
        if (amounts.length > 0) cgst = amounts[amounts.length - 1].trim()
      } else if (/\bsgst\b/i.test(l)) {
        const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
        if (amounts.length > 0) sgst = amounts[amounts.length - 1].trim()
      } else if (/\bigst\b/i.test(l)) {
        const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
        if (amounts.length > 0) igst = amounts[amounts.length - 1].trim()
      } else if (/\b(?:total\s*tax|tax\s*amount|vat\s*amount|vat\s*\(|sales\s*tax)\b/i.test(l)) {
        const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
        if (amounts.length > 0) taxTotal = amounts[amounts.length - 1].trim()
      } else if (/\b(?:grand\s*total|invoice\s*total|total\s*amount|balance\s*due|net\s*payable|\btotal\b)\b/i.test(l)) {
        if (!/\b(?:sub\s*total|subtotal|tax\s*rate|unit\s*price|line\s*total|words|earlypay)\b/i.test(l)) {
          const amounts = (l.match(/([₹$€£]?\s*[\d,]+(?:\.\d{1,2})?)/g) || []).filter(a => /\d/.test(a))
          if (amounts.length > 0) grandTotal = amounts[amounts.length - 1].trim()
        }
      }
    }

    const rows = []
    if (subtotal) rows.push(`• **Subtotal / Gross Amount:** \`${subtotal}\``)
    if (discount) rows.push(`• **Discount:** \`${discount}\``)
    if (taxable) rows.push(`• **Taxable Amount:** \`${taxable}\``)
    if (cgst && sgst) rows.push(`• **Taxes (CGST + SGST):** \`CGST: ${cgst} | SGST: ${sgst}\``)
    else if (cgst) rows.push(`• **CGST:** \`${cgst}\``)
    else if (sgst) rows.push(`• **SGST:** \`${sgst}\``)
    else if (igst) rows.push(`• **IGST:** \`${igst}\``)
    else if (taxTotal) rows.push(`• **Tax Amount:** \`${taxTotal}\``)
    if (grandTotal) rows.push(`• **Grand Total:** \`${grandTotal}\``)

    if (rows.length > 0) {
      return {
        text: `💰 **Financial Breakdown Extracted from Document:**\n\n${rows.join('\n')}`,
        suggestions: ['🔢 Invoice Number & Date', '🏢 Who is the Vendor?', '📋 List all items']
      }
    }
  }

  // 5. Amount in Words
  if (/in words|amount in words|total in words|words/i.test(qLower)) {
    const wordsM = String(docText || '').match(/\b(?:amount\s*in\s*words|total\s*in\s*words|invoice\s*total\s*\(in\s*words\)|in\s*words)[:\s\t\-|]*[\r\n]*([A-Za-z\s\-]+(?:rupees|dollars|cents|euros|pounds|only|paisa|aud|cad|inr|usd))\b/i)
    if (wordsM && wordsM[1]) {
      return {
        text: `🔤 **Amount in Words:**\n\n• \`${cleanVal(wordsM[1])}\``,
        suggestions: ['💰 Numeric Total', '🔢 Invoice Number', '🏢 Vendor Details']
      }
    }
  }

  // 6. Terms & Conditions / Notes / Early Payment
  if (/terms|condition|conditions|policy|late fee|overdue interest|early pay|earlypay|notes|additional notes|remarks/i.test(qLower)) {
    const parts = []
    const tMatch = String(docText || '').match(/(?:terms\s*and\s*conditions|terms\s*&\s*conditions|payment\s*terms)[\s:.\-|]*[\r\n]+([\s\S]{1,400}?)(?:\n\s*\n|additional\s*notes|bank|$)/i)
    if (tMatch && tMatch[1]) {
      parts.push(`📜 **Terms & Conditions:**\n${cleanVal(tMatch[1])}`)
    }
    const earlyMatches = String(docText || '').match(/\b(?:earlypay|early\s*payment|early\s*bird)\b[^\n]+/gi)
    if (earlyMatches && earlyMatches.length > 0) {
      parts.push(`⚡ **Early Payment Benefit:**\n${earlyMatches.map(e => `• ${cleanVal(e)}`).join('\n')}`)
    }
    const notesMatch = String(docText || '').match(/(?:additional\s*notes|notes|remarks)[\s:.\-|]*[\r\n]+([\s\S]{1,300}?)(?:\n\s*\n|for\s*any\s*enquiries|$)/i)
    if (notesMatch && notesMatch[1]) {
      parts.push(`📝 **Additional Notes:**\n${cleanVal(notesMatch[1])}`)
    }
    if (parts.length > 0) {
      return {
        text: parts.join('\n\n'),
        suggestions: ['💰 Invoice Total', '📅 Due Date', '🏦 Bank Details']
      }
    }
  }

  // 7. Place of Supply / Country / Shipping Location
  if (/place of supply|country of supply|pos|shipping address|ship to|delivery location|dispatch/i.test(qLower)) {
    const posRows = []
    const posM = String(docText || '').match(/\b(?:place\s*of\s*supply|pos)\b[:\s\t\-|]*([^\r\n]{2,40})/i)
    if (posM && posM[1]) posRows.push(`• **Place of Supply:** \`${cleanVal(posM[1])}\``)
    const cosM = String(docText || '').match(/\b(?:country\s*of\s*supply|country)\b[:\s\t\-|]*([^\r\n]{2,40})/i)
    if (cosM && cosM[1]) posRows.push(`• **Country of Supply:** \`${cleanVal(cosM[1])}\``)
    if (posRows.length > 0) {
      return {
        text: `📍 **Supply & Delivery Details:**\n\n${posRows.join('\n')}`,
        suggestions: ['🏢 Vendor & Customer', '💰 Invoice Total', '🧾 GST Details']
      }
    }
  }

  // 8. QR Code inquiries
  if (/\b(qr|qr code|barcode|scannable|decoded qr)\b/i.test(qLower)) {
    if (rawDocData && rawDocData.qr_codes && rawDocData.qr_codes.length > 0) {
      const qrList = rawDocData.qr_codes.map((qr, i) => `**QR #${i+1}:** \`${qr.content || qr.text || 'Decoded'}\``).join('\n')
      return {
        text: `📱 **QR Codes Found in Document:**\n\n${qrList}`,
        suggestions: ['💰 Invoice Total', '🛡️ Fraud Check', '🔢 Invoice Number']
      }
    }
    return {
      text: "📱 **QR Code Status:** No QR codes were detected in the current document.",
      suggestions: ['💰 What is the total amount?', '📅 Extract dates', '🛡️ Fraud Check']
    }
  }

  // 9. Fraud / Risk / Legitimacy check
  if (/\b(fraud|fake|suspicious|valid|legit|risk|tampered|anomaly|anomalies)\b/i.test(qLower)) {
    if (rawDocData && rawDocData.fraud_report) {
      const fr = rawDocData.fraud_report
      const verdict = fr.verdict || 'ANALYZED'
      const riskScore = fr.risk_score !== undefined ? `${fr.risk_score}%` : 'Low'
      const issues = (fr.detected_issues || []).map(iss => `• ⚠️ **${iss.title}**: ${iss.reason}`).join('\n') || '• ✅ All mathematical and layout rules passed.'

      return {
        text: `🛡️ **Explainable AI Fraud Inspection Report:**\n\n• **Verdict:** **${verdict}**\n• **Risk Score:** \`${riskScore}\`\n\n**Detected Findings:**\n${issues}`,
        suggestions: ['💰 Verify Totals', '🔢 Check Invoice Number', '📋 Item Breakdown']
      }
    }
    return {
      text: "🛡️ **Fraud Detection:** Run the **Fraud Detection** tab in the main IDP dashboard for visual bounding box validation and automated rule checking.",
      suggestions: ['💰 What is the total amount?', '🔢 What is the invoice number?']
    }
  }

  // 10. Items / Table / Breakdown
  if (/\b(items|line items|products|services|table|breakdown|quantities|quantity|qty|rate|hsn|description)\b/i.test(qLower)) {
    const tableLines = String(docText || '').split('\n').filter(line => line.includes('|') && !line.startsWith('<'))
    if (tableLines.length >= 2) {
      const tableSample = tableLines.slice(0, 15).map(cleanVal).join('\n')
      return {
        text: `📋 **Extracted Line Items / Table:**\n\n${tableSample}\n\n*(Displaying extracted line items)*`,
        suggestions: ['💰 Grand Total', '📅 Invoice Date', '🏢 Vendor Info']
      }
    }
  }

  // 8. Bank & Payment Information
  if (/\b(bank|account|account number|a\/c|ifsc|iban|swift|upi|payment method|payment mode)\b/i.test(qLower)) {
    const bankLines = []
    const lines = String(docText || '').replace(/<[^>]+>/g, '\n').split('\n')
    for (const line of lines) {
      const l = cleanVal(line)
      if (!l || l.length < 3) continue
      if (/\b(?:bank|account|a\/c|ifsc|iban|swift|upi|branch|savings|current)\b/i.test(l)) {
        if (!/\b(?:terms|condition|please pay|charged on)\b/i.test(l)) {
          if (!bankLines.includes(`• ${l}`)) bankLines.push(`• ${l}`)
        }
      }
    }
    if (bankLines.length > 0) {
      return {
        text: `🏦 **Bank & Payment Details:**\n\n${bankLines.slice(0, 6).join('\n')}`,
        suggestions: ['💰 Invoice Total', '🔢 Invoice Number', '🏢 Vendor Info']
      }
    }
  }

  // Universal Keyword & Field Line Search across entire document
  const stopWords = ['provide', 'give', 'tell', 'show', 'find', 'what', 'is', 'the', 'of', 'for', 'in', 'this', 'document', 'file', 'please', 'me', 'can', 'you', 'number', 'details']
  const keywords = qLower.split(/[^a-zA-Z0-9]+/).filter(w => w.length >= 2 && !stopWords.includes(w))
  if (keywords.length > 0) {
    const matchingLines = []
    const lines = String(docText || '').replace(/<[^>]+>/g, '\n').split('\n')
    for (const line of lines) {
      const l = cleanVal(line)
      if (!l || l.length < 3 || l.startsWith('<')) continue
      const lLower = l.toLowerCase()
      if (keywords.some(k => lLower.includes(k))) {
        if (!matchingLines.includes(l)) matchingLines.push(l)
      }
    }
    if (matchingLines.length > 0) {
      const formatted = matchingLines.slice(0, 6).map(l => `• ${l}`)
      return {
        text: `🔍 **Matching Document Content:**\n\n${formatted.join('\n')}`,
        suggestions: ['💰 Total Amount', '🔢 Invoice Number', '📅 Document Dates']
      }
    }
  }

  // Default document fallback
  return {
    text: `I searched the uploaded document for **"${query}"**, but couldn't find a direct match in the extracted text.\n\nYou can try asking about:\n• 💰 **Invoice Total & Tax**\n• 🔢 **Invoice Number & Dates**\n• 🏢 **Vendor & Customer Info**\n• 📋 **Line Items & Quantities**\n• 🛡️ **Fraud & Risk Checks**`,
    suggestions: ['💰 Invoice Total', '🔢 Invoice Number', '📅 Invoice Date', '🛡️ Fraud Check']
  }
}


/**
 * General IDP Assistant Knowledge Base (When no document is loaded)
 */
function generateGeneralIdpAnswer(query) {
  const qClean = cleanText(query)

  // 1. Identity
  if (/^(who are (you|u|r u)|who r u|what is your name|who made you|what are you)\b/i.test(qClean)) {
    return {
      text: "👋 I’m **Reeva AI**, the Intelligent Document Processing (IDP) Assistant built by **Reeva Dev**!\n\nI specialize in analyzing, extracting, and inspecting documents, invoices, receipts, and forms with advanced OCR, YOLO layout segmentation, and Explainable AI fraud detection.",
      suggestions: ['✨ What can you do?', '📁 Supported Formats', '🚀 How to upload documents']
    }
  }

  // 2. Capabilities
  if (/^(what (can|did|do) (you|u) do|what are your (features|capabilities)|how can you help|what else can you do)\b/i.test(qClean) || /what (can|did|do) (you|u) do/i.test(qClean)) {
    return {
      text: "✨ **Here is everything I can do for you:**\n\n• 📄 **Document Extraction:** Parse text, structured markdown, and JSON tables from PDFs, images, DOCX, and XLSX.\n• 💰 **Financial Breakdown:** Extract and verify Subtotals, Tax/GST/VAT, and Grand Totals.\n• 🔢 **Invoice Details:** Extract Invoice Numbers, Issue Dates, Due Dates, and Reference IDs.\n• 🏢 **Parties & Contacts:** Identify Vendor/Issuer details, Customer/Billed To info, and email addresses.\n• 🛡️ **Explainable AI Fraud Inspection:** Detect layout tampering, arithmetic discrepancies, and calculate risk scores.\n• 📱 **QR & Barcode Decoding:** Decode scannable payloads and UPI payment links.\n• 🔊 **Voice Speech & Audio:** Read responses aloud and accept microphone voice input.\n\n*Upload a document on the homepage to start asking questions about it!*",
      suggestions: ['📁 Supported Formats', '🚀 How to upload documents', '🛡️ Fraud Detection Info']
    }
  }

  if (/^(hi|hello|hey|hola|greetings|good morning|good afternoon|good evening)\b/i.test(qClean)) {
    return {
      text: "👋 **Hello! Welcome to the Intelligent Document Processing (IDP) Assistant.**\n\nI can help you extract, parse, analyze, and inspect your documents, PDFs, and invoices.\n\nUpload a document on the homepage to start asking questions about its contents!",
      suggestions: noDocStarterPrompts.map(p => p.label)
    }
  }

  if (/\b(format|formats|supported|file type|file types|extension)\b/i.test(qClean)) {
    return {
      text: "📁 **Supported Document Formats:**\n\n• 📄 **PDFs:** Scanned and digital multi-page PDFs\n• 🖼️ **Images:** PNG, JPG, JPEG, TIFF, WEBP\n• 📊 **Office Documents:** DOCX, PPTX, XLSX\n\nOur pipeline uses advanced OCR (PaddleOCR / MinerU), YOLO layout segmentation, QR detection, and automated fraud scoring.",
      suggestions: ['🚀 How to upload documents', '🛡️ Fraud Detection Info', '🎯 YOLO Layout Analysis']
    }
  }

  if (/\b(how to upload|upload|process|pipeline|start)\b/i.test(qClean)) {
    return {
      text: "🚀 **How to Process Documents:**\n\n1. Drag and drop your file into the **Upload Hero Container** at the top of the homepage.\n2. The system will automatically process the document using deep OCR, layout analysis, and QR decoding.\n3. Explore the extracted Markdown, JSON, YOLO crops, and Fraud Detection tabs.\n4. Ask me any questions here in the chat about your uploaded document!",
      suggestions: ['📁 Supported Formats', '🛡️ How does Fraud Detection work?']
    }
  }

  if (/\b(yolo|layout|bounding box|crop|crops|segmentation)\b/i.test(qClean)) {
    return {
      text: "🎯 **YOLO Layout Segmentation & Interactive Preview:**\n\n• Automatically identifies document regions: **Header, Table, Text, Title, Figure, Stamp, Signature, Key-Value Pairs**.\n• In the **Layout Analysis (YOLO)** tab, you can click on any bounding box to inspect its cropped image snippet and extracted text in real time!",
      suggestions: ['🛡️ Fraud Detection', '📁 Supported Formats']
    }
  }

  if (/\b(fraud|detector|risk|fake|tampered)\b/i.test(qClean)) {
    return {
      text: "🛡️ **Explainable AI Invoice Fraud Detection:**\n\n• Validates subtotal + tax = total arithmetic consistency.\n• Detects duplicate invoice numbers, future dates, missing mandatory fields, and visual layout tampering.\n• Provides color-coded visual overlays (🟢 Valid fields vs 🔴 Suspicious fields) and actionable risk scores.",
      suggestions: ['🎯 YOLO Layout Analysis', '📁 Supported Formats']
    }
  }

  return {
    text: `🤖 **Intelligent Document Processing (IDP) Assistant**\n\nI am ready to answer any questions about your documents once uploaded. You can ask about:\n• 💰 Financial totals, subtotals, and taxes\n• 🔢 Invoice IDs, references, and dates\n• 🏢 Vendor and buyer details\n• 📋 Extracted tables and line items\n• 🛡️ Fraud indicators and QR codes\n\nPlease upload a document on the homepage to begin!`,
    suggestions: noDocStarterPrompts.map(p => p.label)
  }
}
