'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link'; // Import the Link component from next/link

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState('DA');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ sender: string; content: string }[]>([]);
  const [userMessage, setUserMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);

  // Initialize the session
  const handleInitialize = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file) {
      alert('Please upload a PDF file.');
      return;
    }

    setIsInitializing(true);

    const formData = new FormData();
    formData.append('pdf', file);
    formData.append('role', role);

    try {
      const response = await fetch('http://localhost:8000/simulation/initailize', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.session_id && data.response) {
        const transformedMessages = data.response.map((msg: { name: string; content: string }) => ({
          sender: msg.name,
          content: msg.content,
        }));

        setSessionId(data.session_id);
        setMessages(transformedMessages); // Set initial messages
      } else {
        alert('Failed to initialize session.');
      }
    } catch (error) {
      console.error('Error initializing session:', error);
      alert('An error occurred.');
    } finally {
      setIsInitializing(false);
    }
  };

  // Send a message to the server
  const sendMessage = async () => {
    if (!sessionId || !userMessage) return;

    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/simulation/continue', {
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
    } catch (error) {
      console.error('Error sending message:', error);
      alert('An error occurred while sending the message.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <h1 id="title">
        <Link href="/" passHref>
          DeFacto
        </Link>
      </h1>

      {/* Initial Form for PDF Upload and Role Selection */}
      {!sessionId ? (
        <form onSubmit={handleInitialize} className="form">
          <label className="input-label">
            Upload PDF:
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="input-file"
            />
          </label>
          <label className="input-label">
            Select Role:
            <select value={role} onChange={(e) => setRole(e.target.value)} className="input-select">
              <option value="DA">Defense Attorney</option>
              <option value="PA">Prosecuting Attorney</option>
            </select>
          </label>
          <button type="submit" className="submit-btn" disabled={isInitializing}>
            {isInitializing ? 'Starting...' : 'Start'}
          </button>
        </form>
      ) : (
        // Chat Interface
        <div className="chat-container">
          <div className="messages-container">
            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.sender === 'You' ? 'message-user' : 'message-agent'}`}>
                <strong>{msg.sender}:</strong> {msg.content}
              </div>
            ))}
          </div>

          {/* Loading Spinner */}
          {isLoading && (
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Generating response...</p>
            </div>
          )}

          {/* Input Field */}
          <div className="input-container">
            <input
              type="text"
              value={userMessage}
              onChange={(e) => setUserMessage(e.target.value)}
              placeholder="Type a message..."
              className="input-text"
            />
            <button onClick={sendMessage} className="send-btn" disabled={isLoading}>
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
