'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link'; // Import the Link component from next/link


export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [role, setRole] = useState('DA');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const router = useRouter();

  // Initialize the session
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file) {
      alert('Please upload a PDF file.');
      return;
    }

    const formData = new FormData();
    formData.append('pdf', file);
    formData.append('role', role);

    const response = await fetch('http://localhost:8000/initialize', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    if (data.session_id && data.response) {
      // Extract and format the messages
      const transformedMessages = data.response.map((msg: { name: string; content: string }) => ({
        sender: msg.name,
        content: msg.content,
      }));

      // Set session ID and initialize chat messages
      setSessionId(data.session_id);

      // Construct the URL with query parameters using URLSearchParams
      const queryParams = new URLSearchParams({
        sessionId: data.session_id,
        initialMessages: JSON.stringify(transformedMessages),
      }).toString();

      // Redirect to the /chat page with the properly formatted query string
    } else {
      alert('Failed to initialize session.');
    }
  };

  return (
    <div className="container-home">
      <h1 id="title">
        <Link href="/" passHref>
          DeFacto
        </Link>
      </h1>

      {/* Form for uploading PDF and selecting role */}
      {!sessionId ? (
        <form onSubmit={handleSubmit} className="form">
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
          <button type="submit" className="submit-btn">Start</button>
        </form>
      ) : (
        <div>
          {/* No need to display messages here, as we're redirecting */}
          <p>Loading chat...</p>
        </div>
      )}
    </div>
  );
}
