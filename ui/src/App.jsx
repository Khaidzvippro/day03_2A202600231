import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './index.css'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    { role: 'agent', content: 'Xin chào! Tôi là **ArXivInsight**, trợ lý nghiên cứu tài chính của bạn. Tôi có thể giúp bạn tìm kiếm và tóm tắt các bài báo nghiên cứu về tài chính, kinh tế từ ArXiv. Bạn muốn tìm hiểu gì hôm nay?' }
  ])
  const [input, setInput] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isThinking])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isThinking) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsThinking(true)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: userMessage })
      })

      if (!response.ok) {
        throw new Error('Network response was not ok')
      }

      const data = await response.json()
      setMessages(prev => [...prev, { role: 'agent', content: data.answer }])
    } catch (error) {
      console.error('Error fetching chat response:', error)
      setMessages(prev => [...prev, { 
        role: 'agent', 
        content: `❌ Lỗi kết nối: Không thể gửi yêu cầu đến Agent. Vui lòng đảm bảo bạn đã khởi chạy backend FastAPI bằng lệnh \`python api_server.py\`.` 
      }])
    } finally {
      setIsThinking(false)
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>ArXivInsight Demo</h1>
      </div>
      
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
        ))}
        
        {isThinking && (
          <div className="thinking-indicator">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
            <span>AGENT IS THINKING</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-area" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Research Query (e.g. Find recent papers on Alpha Momentum...)"
          disabled={isThinking}
        />
        <button type="submit" disabled={!input.trim() || isThinking}>
          Send
        </button>
      </form>
    </div>
  )
}

export default App
