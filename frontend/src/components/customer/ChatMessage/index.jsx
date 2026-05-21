import { Children, useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ── Inline decorators ─────────────────────────────────────────────────────────
const SourceChip = ({ name }) => (
  <span className="inline-flex items-center gap-1 align-baseline mx-0.5 px-1.5 py-0.5 rounded-md
    bg-primary-50 text-primary-700 text-[11px] font-medium border border-primary-100">
    <svg viewBox="0 0 24 24" className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 2v6h6M9 13h6M9 17h6" />
    </svg>
    {name}
  </span>
)

const CurrencyBadge = ({ raw }) => (
  <span className="inline-block align-baseline mx-0.5 px-1.5 py-0.5 rounded
    bg-amber-50 text-amber-800 text-[11px] font-semibold border border-amber-100 tabular-nums">
    {raw}
  </span>
)

const STATUS_STYLES = {
  AUTO_REJECTED:   'bg-red-50 text-red-700 border-red-100',
  REJECTED:        'bg-red-50 text-red-700 border-red-100',
  ADMIN_REJECTED:  'bg-red-50 text-red-700 border-red-100',
  PENDING_REVIEW:  'bg-blue-50 text-blue-700 border-blue-100',
  AWAITING_INFO:   'bg-amber-50 text-amber-800 border-amber-100',
  APPROVED:        'bg-emerald-50 text-emerald-700 border-emerald-100',
  DRAFT:           'bg-gray-100 text-gray-700 border-gray-200',
}

const StatusBadge = ({ status }) => (
  <span className={`inline-block align-baseline mx-0.5 px-1.5 py-0.5 rounded
    text-[10px] font-semibold uppercase tracking-wide border ${STATUS_STYLES[status] || 'bg-gray-100 text-gray-700 border-gray-200'}`}>
    {status}
  </span>
)

// ── Text-node post-processing ────────────────────────────────────────────────
// Order matters: most specific patterns first.
const TEXT_PATTERNS = [
  {
    // [faq.md], [policy.md], [pricing.md] — sources cited inline
    regex: /\[([\w.-]+\.md)\]/g,
    build: (match, key) => <SourceChip key={key} name={match[1]} />,
  },
  {
    // AUTO_REJECTED, PENDING_REVIEW, AWAITING_INFO, APPROVED, etc.
    regex: /\b(AUTO_REJECTED|ADMIN_REJECTED|REJECTED|PENDING_REVIEW|AWAITING_INFO|APPROVED|DRAFT)\b/g,
    build: (match, key) => <StatusBadge key={key} status={match[1]} />,
  },
  {
    // $617, $1,250.50, ₫500,000
    regex: /(?:[$₫€£]\s?[\d,]+(?:\.\d+)?)/g,
    build: (match, key) => <CurrencyBadge key={key} raw={match[0]} />,
  },
]

const transformText = (text) => {
  if (!text || typeof text !== 'string') return text
  // Collect all matches across all patterns, then stitch the string back together
  // by replacing earliest-match-first non-overlapping spans.
  const matches = []
  TEXT_PATTERNS.forEach((p, patternIdx) => {
    let m
    p.regex.lastIndex = 0
    while ((m = p.regex.exec(text)) !== null) {
      matches.push({ start: m.index, end: m.index + m[0].length, match: m, patternIdx })
    }
  })
  if (matches.length === 0) return text
  // Sort by start asc; drop overlaps (keep earlier).
  matches.sort((a, b) => a.start - b.start)
  const filtered = []
  let cursor = 0
  for (const x of matches) {
    if (x.start >= cursor) {
      filtered.push(x)
      cursor = x.end
    }
  }
  // Build output: alternate plain-text slices and rendered components.
  const out = []
  let pos = 0
  filtered.forEach((x, i) => {
    if (x.start > pos) out.push(text.slice(pos, x.start))
    out.push(TEXT_PATTERNS[x.patternIdx].build(x.match, `tx-${i}`))
    pos = x.end
  })
  if (pos < text.length) out.push(text.slice(pos))
  return out
}

const wrapChildren = (children) => Children.map(children, (child) =>
  typeof child === 'string' ? transformText(child) : child
)

// ── react-markdown component overrides ───────────────────────────────────────
const markdownComponents = {
  p: ({ node, children, ...props }) => (
    <p className="mb-2 last:mb-0" {...props}>{wrapChildren(children)}</p>
  ),
  ul: ({ node, ...props }) => (
    <ul className="list-disc pl-5 space-y-1.5 mb-2 last:mb-0 marker:text-primary-400" {...props} />
  ),
  ol: ({ node, ...props }) => (
    <ol className="list-decimal pl-5 space-y-1.5 mb-2 last:mb-0 marker:text-primary-400" {...props} />
  ),
  li: ({ node, children, ...props }) => (
    <li className="leading-7 pl-1" {...props}>{wrapChildren(children)}</li>
  ),
  strong: ({ node, children, ...props }) => (
    <strong className="font-semibold text-gray-950" {...props}>{wrapChildren(children)}</strong>
  ),
  em: ({ node, children, ...props }) => (
    <em className="italic" {...props}>{wrapChildren(children)}</em>
  ),
  code: ({ node, inline, ...props }) =>
    inline
      ? <code className="bg-gray-100 text-gray-800 rounded px-1 py-0.5 text-xs font-mono" {...props} />
      : <code className="block bg-gray-100 text-gray-800 rounded p-2 my-2 text-xs font-mono overflow-x-auto" {...props} />,
  a: ({ node, ...props }) => (
    <a className="text-primary-600 underline hover:text-primary-700" target="_blank" rel="noopener noreferrer" {...props} />
  ),
  h1: ({ node, ...props }) => <h3 className="text-base font-semibold mt-2 mb-1" {...props} />,
  h2: ({ node, ...props }) => <h3 className="text-base font-semibold mt-2 mb-1" {...props} />,
  h3: ({ node, ...props }) => <h3 className="text-sm font-semibold mt-2 mb-1" {...props} />,
}

const ChatMessage = ({ message, typewriter = false }) => {
  const isUser = message.role === 'user'
  const fullContent = message.content || ''
  // Track ONLY the animated length; derive `displayed` from content + length below.
  // This guarantees that when typewriter flips false (e.g. another message arrives
  // mid-animation), the full content is always shown — no partial truncation.
  const [animatedLength, setAnimatedLength] = useState(typewriter ? 0 : fullContent.length)

  useEffect(() => {
    if (!typewriter) {
      setAnimatedLength(fullContent.length)
      return
    }
    setAnimatedLength(0)
    let pos = 0
    const len = fullContent.length
    const chunk = len > 500 ? 10 : len > 200 ? 5 : 2
    const id = setInterval(() => {
      pos = Math.min(pos + chunk, len)
      setAnimatedLength(pos)
      if (pos >= len) clearInterval(id)
    }, 16)
    return () => clearInterval(id)
  }, [fullContent, typewriter])

  const displayed = typewriter ? fullContent.slice(0, animatedLength) : fullContent

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold
        ${isUser ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
        {isUser ? 'Tôi' : 'AI'}
      </div>

      <div className={`max-w-[65ch] rounded-2xl px-4 py-3 text-sm leading-7 break-words
        ${isUser
          ? 'bg-primary-600 text-white rounded-tr-sm'
          : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'}`}>
        {isUser
          ? <div className="whitespace-pre-wrap">{displayed}</div>
          : <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{displayed}</ReactMarkdown>}
      </div>
    </div>
  )
}

export default ChatMessage
