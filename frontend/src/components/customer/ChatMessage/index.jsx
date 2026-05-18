const normalizeAssistantContent = (content) => (
  String(content || '')
    .replace(/\r\n/g, '\n')
    .trim()
    .replace(/\s+(\*\*[^*\n]{2,90}\*\*)/g, '\n\n$1')
)

const renderInline = (text) => (
  String(text).split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} className="font-semibold text-gray-950">{part.slice(2, -2)}</strong>
    }
    return <span key={index}>{part}</span>
  })
)

const renderAssistantContent = (content) => {
  const blocks = normalizeAssistantContent(content)
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)

  return (
    <div className="space-y-3">
      {blocks.map((block, blockIndex) => {
        const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
        const isList = lines.length > 1 && lines.every((line) => /^[-*•]\s+/.test(line))

        if (isList) {
          return (
            <ul key={blockIndex} className="list-disc pl-5 space-y-1">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{renderInline(line.replace(/^[-*•]\s+/, ''))}</li>
              ))}
            </ul>
          )
        }

        return (
          <p key={blockIndex}>
            {lines.map((line, lineIndex) => (
              <span key={lineIndex}>
                {lineIndex > 0 && <br />}
                {renderInline(line)}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}

const ChatMessage = ({ message }) => {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold
        ${isUser ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
        {isUser ? 'Tôi' : 'AI'}
      </div>

      {/* Bubble */}
      <div className={`max-w-[85%] sm:max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-7 break-words
        ${isUser
          ? 'bg-primary-600 text-white rounded-tr-sm'
          : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'}`}>
        {isUser
          ? <div className="whitespace-pre-wrap">{message.content}</div>
          : renderAssistantContent(message.content)}
      </div>
    </div>
  )
}

export default ChatMessage
