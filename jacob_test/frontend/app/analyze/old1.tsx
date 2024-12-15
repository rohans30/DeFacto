'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link'; // Import the Link component from next/link

export default function Chat() {
  const searchParams = useSearchParams(); // Access query parameters
  const sessionId = searchParams.get('sessionId');
  const initialMessages = searchParams.get('initialMessages');

  const [messages, setMessages] = useState<{ sender: string; content: string }[]>([]);
  const [userMessage, setUserMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (initialMessages) {
      setMessages(JSON.parse(initialMessages)); // Parse initial messages from query
    }
  }, [initialMessages]);

  const sendMessage = async () => {
    if (!sessionId || !userMessage) return;

    setIsLoading(true);

    const response = await fetch('http://localhost:8000/continue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, user_message: userMessage }),
    });

    const data = await response.json();

    const newMessages = data.response.map((msg: { name: string; content: string }) => ({
      sender: msg.name,
      content: msg.content,
    }));

    setMessages((prev) => [
      ...prev,
      { sender: 'You', content: userMessage },
      ...newMessages,
    ]);
    setUserMessage('');
    setIsLoading(false);
  };

  return (
    <div className="container">

      {/* Messages container */}
      <div className="messages-container">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.sender === 'You' ? 'message-user' : 'message-agent'}`}>
            <strong>{msg.sender}:</strong> {msg.content}
          </div>
        ))}
        {/* Scrollable section */}
        <div id="messagesEnd" />
      </div>

      {/* Loading spinner */}
      {isLoading && (
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Generating response...</p>
        </div>
      )}

      {/* Input field for user to send messages */}
      <div className="input-container">
        <input
          type="text"
          value={userMessage}
          onChange={(e) => setUserMessage(e.target.value)}
          className="input-text"
        />
        <button onClick={sendMessage} className="send-btn">Send</button>
      </div>
    </div>
  );
}
