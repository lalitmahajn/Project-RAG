import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const API_BASE = 'http://localhost:8000/api';

interface Book {
  id: string;
  name: string;
  description?: string;
  created_at: string;
}

interface Chapter {
  id: string;
  book_id: string;
  chapter_number: number;
  name?: string;
  created_at: string;
}

interface Vachan {
  id: string;
  book_id: string;
  chapter_id: string;
  page_number: number;
  vachan_number: number;
  original_text: string;
  hindi_meaning: string;
  status: string;
  created_at: string;
  book_name?: string;
  chapter_number?: number;
  chapter_name?: string;
}

interface IngestionTask {
  id: string;
  filename: string;
  status: string;
  error_message?: string;
  book_id?: string;
  created_at: string;
}

interface ChatMessage {
  sender: 'user' | 'assistant';
  text: string;
  citations?: Array<{
    book_name: string;
    chapter_number: number;
    page_number: number;
    vachan_number: number;
  }>;
}

const highlightText = (text: string, term: string) => {
  if (!term || !text) return text;
  
  const escapedTerm = term.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
  const regex = new RegExp(`(${escapedTerm})`, 'gi');
  const parts = text.split(regex);
  
  return parts.map((part, idx) => 
    regex.test(part) ? <mark key={idx} className="search-highlight">{part}</mark> : part
  );
};

const renderFormattedText = (text: string) => {
  if (!text) return null;
  
  const queryMatch = text.match(/Found \d+ result\(s\) for "(.*?)":/);
  const highlightQuery = queryMatch ? queryMatch[1] : '';

  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    const trimmed = line.trim();
    if (trimmed === '') {
      return <div key={lineIdx} style={{ height: '0.4rem' }} />;
    }
    
    const parseLineContent = (content: string) => {
      interface Token {
        type: 'text' | 'bold' | 'citation';
        start: number;
        end: number;
        text: string;
        bookName?: string;
        chapterNumber?: number;
        vachanNumber?: number;
      }
      
      const tokens: Token[] = [];
      
      // 1. Find bold matches
      const boldRegex = /\*\*(.*?)\*\*/g;
      let boldMatch;
      while ((boldMatch = boldRegex.exec(content)) !== null) {
        tokens.push({
          type: 'bold',
          start: boldMatch.index,
          end: boldMatch.index + boldMatch[0].length,
          text: boldMatch[1]
        });
      }
      
      // 2. Find citation matches
      // e.g. (ब्रम्हचारी विठ्ठलराव के सम्वाद, अध्याय 3, पृष्ठ 75, वचन 62)
      const citationRegex = /\(([^,)]+),\s*अध्याय\s*(\d+),\s*(?:पृष्ठ\s*(\d+),\s*)?वचन\s*(\d+(?:\s*,\s*\d+)*)\)/g;
      let citMatch;
      while ((citMatch = citationRegex.exec(content)) !== null) {
        const bookName = citMatch[1].trim();
        const chapterNumber = parseInt(citMatch[2]);
        const vachanStr = citMatch[4].trim();
        const firstVachan = parseInt(vachanStr.split(',')[0].trim());
        
        tokens.push({
          type: 'citation',
          start: citMatch.index,
          end: citMatch.index + citMatch[0].length,
          text: `📖 ${bookName.replace('ब्रम्हचारी ', '')} - Ch ${chapterNumber}, v.${vachanStr}`,
          bookName: bookName,
          chapterNumber: chapterNumber,
          vachanNumber: firstVachan
        });
      }
      
      // Sort and filter out overlaps
      tokens.sort((a, b) => a.start - b.start);
      
      const finalParts: React.ReactNode[] = [];
      let lastIdx = 0;
      
      const pushHighlightedText = (textToHighlight: string) => {
        const res = highlightText(textToHighlight, highlightQuery);
        if (Array.isArray(res)) {
          finalParts.push(...res);
        } else {
          finalParts.push(res);
        }
      };
      
      for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];
        if (token.start < lastIdx) continue;
        
        if (token.start > lastIdx) {
          pushHighlightedText(content.substring(lastIdx, token.start));
        }
        
        if (token.type === 'bold') {
          const res = highlightText(token.text, highlightQuery);
          finalParts.push(
            <strong key={`bold-${token.start}`}>
              {Array.isArray(res) ? res : [res]}
            </strong>
          );
        } else if (token.type === 'citation') {
          const citObj = {
            book_name: token.bookName || '',
            chapter_number: token.chapterNumber || 1,
            page_number: 0,
            vachan_number: token.vachanNumber || 1
          };
          
          finalParts.push(
            <span 
              key={`citation-${token.start}`} 
              className="citation-badge clickable"
              onClick={() => handleCitationClick(citObj)}
              title={`Click to navigate to ${token.bookName} Chapter ${token.chapterNumber}, Vachan ${token.vachanNumber}`}
            >
              {token.text}
            </span>
          );
        }
        
        lastIdx = token.end;
      }
      
      if (lastIdx < content.length) {
        pushHighlightedText(content.substring(lastIdx));
      }
      
      return finalParts;
    };

    if (trimmed.startsWith('### ')) {
      return <h4 key={lineIdx} className="chat-md-h4">{parseLineContent(trimmed.substring(4))}</h4>;
    }
    if (trimmed.startsWith('## ')) {
      return <h3 key={lineIdx} className="chat-md-h3">{parseLineContent(trimmed.substring(3))}</h3>;
    }
    if (trimmed.startsWith('# ')) {
      return <h2 key={lineIdx} className="chat-md-h2">{parseLineContent(trimmed.substring(2))}</h2>;
    }

    if (trimmed.startsWith('> ')) {
      return (
        <blockquote key={lineIdx} className="chat-md-blockquote">
          {parseLineContent(trimmed.substring(2))}
        </blockquote>
      );
    }

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      return (
        <li key={lineIdx} className="chat-md-li">
          {parseLineContent(trimmed.substring(2))}
        </li>
      );
    }

    if (line.startsWith('   ') || line.startsWith('\t') || line.startsWith('  ')) {
      return (
        <div key={lineIdx} className="chat-text-indented">
          {parseLineContent(line)}
        </div>
      );
    }
    
    const isHeading = line.startsWith('Found ') || /^\d+\./.test(trimmed) || trimmed.startsWith('**');
    
    return (
      <div 
        key={lineIdx} 
        className={isHeading ? "chat-text-heading" : "chat-text-line"}
      >
        {parseLineContent(line)}
      </div>
    );
  });
};

export default function App() {
  const [activeTab, setActiveTab] = useState<'browse' | 'search' | 'admin'>('browse');
  const [leftPanelOpen, setLeftPanelOpen] = useState<boolean>(false);
  
  // Scripture Browse State
  const [books, setBooks] = useState<Book[]>([]);
  const [selectedBookId, setSelectedBookId] = useState<string>('');
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<string>('');
  const [vachans, setVachans] = useState<Vachan[]>([]);
  
  // Search State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchBookId, setSearchBookId] = useState<string>('');
  const [searchChapterNum, setSearchChapterNum] = useState<string>('');
  const [searchResults, setSearchResults] = useState<Vachan[]>([]);
  
  // Assistant Chat State
  const [chatMode, setChatMode] = useState<'strict' | 'commentary' | 'search'>('strict');
  const [chatInput, setChatInput] = useState<string>('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isChatLoading, setIsChatLoading] = useState<boolean>(false);
  const [chatSearchType, setChatSearchType] = useState<'keyword' | 'semantic' | 'hybrid'>('keyword');
  const [generalSearchType, setGeneralSearchType] = useState<'keyword' | 'semantic' | 'hybrid'>('keyword');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Citation Navigation & Highlight State
  const [pendingCitation, setPendingCitation] = useState<{
    bookName: string;
    chapterNumber: number;
    vachanNumber: number;
  } | null>(null);
  const [highlightedVachanNumber, setHighlightedVachanNumber] = useState<number | null>(null);

  // Admin State
  const [uploadBookName, setUploadBookName] = useState<string>('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [ingestionTasks, setIngestionTasks] = useState<IngestionTask[]>([]);
  const [draftVachans, setDraftVachans] = useState<Vachan[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<Vachan | null>(null);
  const [editOriginal, setEditOriginal] = useState<string>('');
  const [editMeaning, setEditMeaning] = useState<string>('');
  const [activePdfFile, setActivePdfFile] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch initial books
  useEffect(() => {
    fetchBooks();
    if (activeTab === 'admin') {
      fetchAdminData();
    }
  }, [activeTab]);

  // Fetch chapters when book is selected
  useEffect(() => {
    if (selectedBookId) {
      fetchChapters(selectedBookId);
      setVachans([]);
      setSelectedChapterId('');
    }
  }, [selectedBookId]);

  // Fetch vachans when chapter is selected
  useEffect(() => {
    if (selectedChapterId) {
      fetchVachans(selectedChapterId);
    }
  }, [selectedChapterId]);

  // helper to scroll and highlight vachan card
  const scrollToAndHighlightVachan = (vachanNum: number) => {
    setTimeout(() => {
      const element = document.getElementById(`vachan-card-${vachanNum}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setHighlightedVachanNumber(vachanNum);
        setPendingCitation(null);
        setTimeout(() => {
          setHighlightedVachanNumber(null);
        }, 3000);
      }
    }, 150);
  };

  // Observe chapters changes to handle pending citation navigation
  useEffect(() => {
    if (pendingCitation && chapters.length > 0) {
      const targetChapter = chapters.find(c => c.chapter_number === pendingCitation.chapterNumber);
      if (targetChapter) {
        if (selectedChapterId !== targetChapter.id) {
          setSelectedChapterId(targetChapter.id);
        } else {
          // Chapter already selected, force reload vachans
          fetchVachans(targetChapter.id);
        }
      }
    }
  }, [chapters, pendingCitation]);

  // Observe vachans changes to handle pending citation scroll
  useEffect(() => {
    if (pendingCitation && vachans.length > 0) {
      const hasVachan = vachans.some(v => v.vachan_number === pendingCitation.vachanNumber);
      if (hasVachan) {
        scrollToAndHighlightVachan(pendingCitation.vachanNumber);
      }
    }
  }, [vachans, pendingCitation]);

  const handleCitationClick = (citation: { book_name: string; chapter_number: number; page_number: number; vachan_number: number }) => {
    setLeftPanelOpen(true);
    setActiveTab('browse');

    const targetBook = books.find(b => b.name === citation.book_name);
    if (!targetBook) return;

    setPendingCitation({
      bookName: citation.book_name,
      chapterNumber: citation.chapter_number,
      vachanNumber: citation.vachan_number
    });

    if (selectedBookId !== targetBook.id) {
      setSelectedBookId(targetBook.id);
    } else {
      const targetChapter = chapters.find(c => c.chapter_number === citation.chapter_number);
      if (targetChapter) {
        if (selectedChapterId !== targetChapter.id) {
          setSelectedChapterId(targetChapter.id);
        } else {
          scrollToAndHighlightVachan(citation.vachan_number);
        }
      }
    }
  };

  // Scroll to bottom of chat only when a new message is added
  const prevChatLenRef = useRef(0);
  useEffect(() => {
    if (chatHistory.length > prevChatLenRef.current) {
      // Small delay to let the DOM render, then scroll
      setTimeout(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
    prevChatLenRef.current = chatHistory.length;
  }, [chatHistory]);

  const fetchBooks = async () => {
    try {
      const res = await fetch(`${API_BASE}/books`);
      const data = await res.json();
      setBooks(data);
      if (data.length > 0 && !selectedBookId) {
        setSelectedBookId(data[0].id);
      }
    } catch (e) {
      console.error("Failed to fetch books", e);
    }
  };

  const fetchChapters = async (bookId: string) => {
    try {
      const res = await fetch(`${API_BASE}/books/${bookId}/chapters`);
      const data = await res.json();
      setChapters(data);
      if (data.length > 0) {
        setSelectedChapterId(data[0].id);
      }
    } catch (e) {
      console.error("Failed to fetch chapters", e);
    }
  };

  const fetchVachans = async (chapterId: string) => {
    try {
      // Browse page shows only approved vachans
      const res = await fetch(`${API_BASE}/chapters/${chapterId}/vachans?include_drafts=false`);
      const data = await res.json();
      setVachans(data);
    } catch (e) {
      console.error("Failed to fetch vachans", e);
    }
  };

  const executeSearch = async () => {
    try {
      let url = `${API_BASE}/search?q=${encodeURIComponent(searchQuery)}&include_drafts=false&search_type=${generalSearchType}`;
      if (searchBookId) url += `&book_id=${searchBookId}`;
      if (searchChapterNum) url += `&chapter_number=${searchChapterNum}`;
      
      const res = await fetch(url);
      const data = await res.json();
      setSearchResults(data);
    } catch (e) {
      console.error("Search failed", e);
    }
  };

  const handleAskAssistant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg: ChatMessage = { sender: 'user', text: chatInput };
    setChatHistory(prev => [...prev, userMsg]);
    setChatInput('');
    setIsChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: userMsg.text,
          mode: chatMode,
          search_type: chatSearchType,
          history: chatHistory.map(m => ({ role: m.sender === 'user' ? 'user' : 'model', parts: [m.text] }))
        })
      });

      if (res.ok) {
        const data = await res.json();
        setChatHistory(prev => [...prev, {
          sender: 'assistant',
          text: data.answer,
          citations: data.citations
        }]);
      } else {
        // Fallback mock answer if chat endpoint is not completed yet
        setTimeout(() => {
          setChatHistory(prev => [...prev, {
            sender: 'assistant',
            text: "AI Research Assistant module is being initialized. Once LLM abstraction keys are configured, research and citations query will run.",
            citations: []
          }]);
        }, 1000);
      }
    } catch (err) {
      setChatHistory(prev => [...prev, {
        sender: 'assistant',
        text: "Error connecting to AI Assistant service.",
        citations: []
      }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Admin actions
  const fetchAdminData = async () => {
    try {
      // Ingestion tasks
      const tasksRes = await fetch(`${API_BASE}/admin/tasks`);
      const tasks = await tasksRes.json();
      setIngestionTasks(tasks);

      // Draft vachans for review
      const reviewRes = await fetch(`${API_BASE}/admin/vachans/review?limit=100`);
      const drafts = await reviewRes.json();
      setDraftVachans(drafts);
    } catch (e) {
      console.error("Failed to load admin data", e);
    }
  };

  const handlePdfUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadBookName.trim()) return;

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('book_name', uploadBookName);

    try {
      const res = await fetch(`${API_BASE}/admin/upload`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        setUploadBookName('');
        setUploadFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        fetchAdminData();
        alert("Upload successful! Ingestion running in background.");
      } else {
        const err = await res.json();
        alert(`Upload failed: ${err.detail}`);
      }
    } catch (err) {
      alert("Error uploading PDF file.");
    }
  };

  const startReview = (vachan: Vachan) => {
    // Find matching document to get filename for PDF viewer
    const task = ingestionTasks.find(t => t.book_id === vachan.book_id);
    const filename = task ? task.filename : '';
    
    setSelectedDraft(vachan);
    setEditOriginal(vachan.original_text);
    setEditMeaning(vachan.hindi_meaning);
    setActivePdfFile(filename);
  };

  const saveDraftEdits = async (approve: boolean) => {
    if (!selectedDraft) return;

    try {
      const res = await fetch(`${API_BASE}/admin/vachans/${selectedDraft.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_text: editOriginal,
          hindi_meaning: editMeaning,
          status: approve ? 'approved' : 'draft'
        })
      });

      if (res.ok) {
        // Remove from list or update local state
        setDraftVachans(prev => prev.filter(v => v.id !== selectedDraft.id));
        
        // Find next draft in list to review immediately
        const currentIndex = draftVachans.findIndex(v => v.id === selectedDraft.id);
        if (currentIndex !== -1 && currentIndex + 1 < draftVachans.length) {
          startReview(draftVachans[currentIndex + 1]);
        } else {
          setSelectedDraft(null);
        }
        fetchAdminData();
      }
    } catch (e) {
      alert("Failed to save updates.");
    }
  };

  return (
    <div className="app-container">
      {/* Header navbar */}
      <header className="header">
        <a href="#" className="brand" onClick={() => setActiveTab('browse')}>
          🪨 <span className="brand-devanagari">सत्तगुरू सुखरामजी</span> Scripture Library
        </a>
        <div className="nav-links">
          <button 
            className={`nav-button ${activeTab === 'browse' ? 'active' : ''}`}
            onClick={() => setActiveTab('browse')}
          >
            Browse Library
          </button>
          <button 
            className={`nav-button ${activeTab === 'search' ? 'active' : ''}`}
            onClick={() => { setActiveTab('search'); executeSearch(); }}
          >
            Search Scripture
          </button>
          <button 
            className={`nav-button admin-btn ${activeTab === 'admin' ? 'active' : ''}`}
            onClick={() => setActiveTab('admin')}
          >
            Admin Panel
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="main-content">
        
        {/* Tab 1: Browse */}
        {activeTab === 'browse' && (
          <div className={`portal-layout animate-fade-in ${!leftPanelOpen ? 'panel-collapsed' : ''}`}>
            {/* Collapse toggle */}
            <button 
              className="panel-toggle-btn"
              onClick={() => setLeftPanelOpen(!leftPanelOpen)}
              title={leftPanelOpen ? 'Collapse scriptures' : 'Show scriptures'}
            >
              {leftPanelOpen ? '◀ Hide Scriptures' : '▶ Browse Scriptures'}
            </button>
            {leftPanelOpen && <div className="left-panel">
              <div className="glass-card search-controls" style={{ gap: '1.5rem', flexWrap: 'nowrap' }}>
                <div className="input-group" style={{ flex: 1 }}>
                  <label className="input-label">Select Book</label>
                  <select 
                    className="filter-select"
                    value={selectedBookId}
                    onChange={(e) => setSelectedBookId(e.target.value)}
                  >
                    {books.map(b => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
                <div className="input-group" style={{ flex: 1 }}>
                  <label className="input-label">Select Chapter</label>
                  <select 
                    className="filter-select"
                    value={selectedChapterId}
                    onChange={(e) => setSelectedChapterId(e.target.value)}
                  >
                    {chapters.map(c => (
                      <option key={c.id} value={c.id}>Chapter {c.chapter_number}: {c.name || 'Untitled'}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Vachan listings */}
              <div className="vachan-list">
                {vachans.length === 0 ? (
                  <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', color: 'hsl(var(--text-muted))' }}>
                    No approved Vachans found in this chapter. Visit the Admin Panel to approve drafts.
                  </div>
                ) : (
                  vachans.map(v => (
                    <div 
                      key={v.id} 
                      id={`vachan-card-${v.vachan_number}`}
                      className={`glass-card vachan-card animate-fade-in ${
                        highlightedVachanNumber === v.vachan_number ? 'vachan-highlight-glowing' : ''
                      }`}
                    >
                      <div className="vachan-meta">
                        <span className="meta-badge">Vachan {v.vachan_number}</span>
                        <span>Page {v.page_number}</span>
                      </div>
                      <div className="vachan-original">{v.original_text}</div>
                      <div className="vachan-meaning">{v.hindi_meaning}</div>
                    </div>
                  ))
                )}
              </div>
            </div>}

            {/* AI Assistant Chat on Right Side */}
            <div className="right-panel">
              <div className="assistant-container">
                <div className="assistant-header" style={{ flexDirection: 'column', alignItems: 'stretch', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>AI Research Assistant</div>
                    <div className="assistant-mode-toggle">
                      <button 
                        className={`mode-btn ${chatMode === 'strict' ? 'active' : ''}`}
                        onClick={() => setChatMode('strict')}
                      >
                        Strict
                      </button>
                      <button 
                        className={`mode-btn ${chatMode === 'commentary' ? 'active' : ''}`}
                        onClick={() => setChatMode('commentary')}
                      >
                        Commentary
                      </button>
                      <button 
                        className={`mode-btn ${chatMode === 'search' ? 'active' : ''}`}
                        onClick={() => setChatMode('search')}
                      >
                        Search
                      </button>
                    </div>
                  </div>
                  
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid hsla(var(--border), 0.5)', paddingTop: '0.75rem', fontSize: '0.85rem' }}>
                    <span style={{ color: 'hsl(var(--text-muted))', fontWeight: 500 }}>Search Strategy:</span>
                    <select 
                      className="filter-select"
                      style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', height: 'auto' }}
                      value={chatSearchType}
                      onChange={(e) => setChatSearchType(e.target.value as 'keyword' | 'semantic' | 'hybrid')}
                    >
                      <option value="keyword">Keyword (FTS5)</option>
                      <option value="semantic">Semantic (Vector)</option>
                      <option value="hybrid">Hybrid</option>
                    </select>
                  </div>
                </div>

                {/* Chat Bubbles */}
                <div className="chat-history">
                  {chatHistory.length === 0 && (
                    <div style={{ margin: 'auto', textAlign: 'center', padding: '1rem', color: 'hsl(var(--text-muted))', fontSize: '0.85rem' }}>
                      {chatMode === 'search'
                        ? 'Search scripture terms directly — no LLM needed. Results come straight from the database.'
                        : 'Ask me questions about teachings, compare Vachans, or search concepts. I will search the scripture database and cite sources.'
                      }
                    </div>
                  )}
                  {chatHistory.map((m, idx) => {
                    const isError = m.text.includes('Rate Limit Exceeded') || m.text.includes('Error running Gemini');
                    return (
                      <div key={idx} className={`chat-msg ${m.sender} ${isError ? 'error-msg' : ''}`}>
                      <div className="chat-msg-body">{renderFormattedText(m.text)}</div>
                      {m.citations && m.citations.length > 0 && (
                        <div>
                          <div className="citations-title">Sources:</div>
                          <div className="citation-list">
                            {m.citations.map((c, cIdx) => (
                              <span 
                                key={cIdx} 
                                className="citation-item clickable"
                                onClick={() => handleCitationClick(c)}
                                title="Click to view in scriptures"
                              >
                                {c.book_name} - Ch {c.chapter_number}, p.{c.page_number}, v.{c.vachan_number}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      </div>
                    );
                  })}
                  {isChatLoading && (
                    <div className="chat-msg assistant" style={{ fontStyle: 'italic', color: 'hsl(var(--text-muted))' }}>
                      Analyzing scripture references...
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Prompt input */}
                <form className="chat-input-area" onSubmit={handleAskAssistant}>
                  <input 
                    type="text" 
                    className="text-input" 
                    placeholder={chatMode === 'search' ? 'Search terms (e.g. राम, गुरु, भक्ति)...' : 'Ask scripture questions...'} 
                    style={{ flex: 1 }}
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={isChatLoading}
                  />
                  <button type="submit" className="btn btn-primary" disabled={isChatLoading}>Ask</button>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: General Search */}
        {activeTab === 'search' && (
          <div className="portal-layout animate-fade-in" style={{ gridTemplateColumns: '1fr' }}>
            <div className="left-panel">
              <div className="glass-card search-controls">
                <div className="search-bar-container input-group">
                  <label className="input-label">Search Query</label>
                  <input 
                    type="text" 
                    className="text-input" 
                    placeholder="Enter keywords or concepts..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && executeSearch()}
                  />
                </div>
                <div className="input-group" style={{ minWidth: '150px' }}>
                  <label className="input-label">Search Strategy</label>
                  <select 
                    className="filter-select"
                    value={generalSearchType}
                    onChange={(e) => setGeneralSearchType(e.target.value as 'keyword' | 'semantic' | 'hybrid')}
                  >
                    <option value="keyword">Keyword (FTS5)</option>
                    <option value="semantic">Semantic (Vector)</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </div>
                <div className="input-group" style={{ minWidth: '150px' }}>
                  <label className="input-label">Filter Book</label>
                  <select 
                    className="filter-select"
                    value={searchBookId}
                    onChange={(e) => setSearchBookId(e.target.value)}
                  >
                    <option value="">All Books</option>
                    {books.map(b => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
                <div className="input-group" style={{ minWidth: '120px' }}>
                  <label className="input-label">Chapter</label>
                  <input 
                    type="number" 
                    className="text-input" 
                    placeholder="Number" 
                    value={searchChapterNum}
                    onChange={(e) => setSearchChapterNum(e.target.value)}
                  />
                </div>
                <button className="btn btn-primary" onClick={executeSearch}>Search</button>
              </div>

              {/* Search listings */}
              <div className="vachan-list">
                {searchResults.length === 0 ? (
                  <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', color: 'hsl(var(--text-muted))' }}>
                    No results match your search filters.
                  </div>
                ) : (
                  searchResults.map(v => (
                    <div key={v.id} className="glass-card vachan-card animate-fade-in">
                      <div className="vachan-meta">
                        <span className="meta-badge">{v.book_name}</span>
                        <span>Chapter {v.chapter_number} • Vachan {v.vachan_number} • Page {v.page_number}</span>
                      </div>
                      <div className="vachan-original">{highlightText(v.original_text, searchQuery)}</div>
                      <div className="vachan-meaning">{highlightText(v.hindi_meaning, searchQuery)}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Admin Review Dashboard */}
        {activeTab === 'admin' && (
          <div className="admin-container animate-fade-in">
            <div className="admin-header-row">
              <h2 style={{ fontWeight: 600 }}>Scripture Administration & Verification</h2>
              <button className="btn" onClick={fetchAdminData}>🔄 Refresh Data</button>
            </div>

            <div className="admin-grid">
              
              {/* Ingestion & Upload side */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div className="glass-card">
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Upload New PDF</h3>
                  <form onSubmit={handlePdfUpload} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div className="input-group">
                      <label className="input-label">Book Name</label>
                      <input 
                        type="text" 
                        className="text-input" 
                        placeholder="e.g. सुखरामजी महाराज की जीवनी"
                        value={uploadBookName}
                        onChange={(e) => setUploadBookName(e.target.value)}
                        required
                      />
                    </div>
                    <div className="input-group">
                      <label className="input-label">PDF Document</label>
                      <input 
                        type="file" 
                        ref={fileInputRef}
                        accept=".pdf"
                        onChange={(e) => {
                          const file = e.target.files ? e.target.files[0] : null;
                          setUploadFile(file);
                          if (file) {
                            const baseName = file.name.replace(/\.[^/.]+$/, "");
                            setUploadBookName(baseName);
                          }
                        }}
                        required
                      />
                    </div>
                    <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>Upload & Ingest</button>
                  </form>
                </div>

                {/* Import Job status log */}
                <div className="glass-card" style={{ flex: 1 }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Ingestion logs</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '300px', overflowY: 'auto' }}>
                    {ingestionTasks.map(t => (
                      <div key={t.id} style={{ borderBottom: '1px solid hsl(var(--border))', paddingBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                          <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>
                            {t.filename}
                          </span>
                          <span className={`meta-badge ${t.status}`}>
                            {t.status}
                          </span>
                        </div>
                        {t.error_message && (
                          <div style={{ fontSize: '0.75rem', color: 'hsl(var(--accent-danger))', marginTop: '0.25rem' }}>
                            {t.error_message}
                          </div>
                        )}
                        <div style={{ fontSize: '0.75rem', color: 'hsl(var(--text-muted))' }}>
                          {new Date(t.created_at).toLocaleDateString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Review and Verification listings */}
              <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Extracted Scripture Verification Queue</h3>
                <p style={{ fontSize: '0.85rem', color: 'hsl(var(--text-muted))' }}>
                  The following draft records have been parsed. Click <b>Verify & Review</b> to open the side-by-side editing view against the original PDF page to approve them.
                </p>

                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '600px', overflowY: 'auto' }}>
                  {draftVachans.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '3rem', color: 'hsl(var(--text-muted))' }}>
                      All items approved! Queue is empty.
                    </div>
                  ) : (
                    draftVachans.map(v => (
                      <div 
                        key={v.id} 
                        style={{ background: 'hsl(var(--bg-input))', border: '1px solid hsl(var(--border))', borderRadius: 'var(--radius-sm)', padding: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '0.75rem', color: 'hsl(var(--text-muted))' }}>
                            <span className="meta-badge">Page {v.page_number}</span>
                            <span className="meta-badge">Vachan {v.vachan_number}</span>
                          </div>
                          <div style={{ fontFamily: 'Noto Sans Devanagari', fontSize: '1rem', fontWeight: 500, color: 'hsl(var(--text-main))', marginBottom: '0.25rem', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                            {v.original_text}
                          </div>
                          <div style={{ fontFamily: 'Noto Sans Devanagari', fontSize: '0.85rem', color: 'hsl(var(--text-muted))', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                            {v.hindi_meaning}
                          </div>
                        </div>
                        <button className="btn btn-primary" style={{ fontSize: '0.8rem', padding: '0.5rem 0.75rem' }} onClick={() => startReview(v)}>
                          🔍 Verify & Review
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Verification Side-by-Side Modal */}
      {selectedDraft && (
        <div className="review-modal-overlay">
          <div className="review-modal">
            <div className="review-modal-header">
              <div>
                <span style={{ fontWeight: 600, fontSize: '1.05rem', marginRight: '1rem' }}>Verify Parsed Text</span>
                <span className="meta-badge">Page {selectedDraft.page_number}</span>
                <span className="meta-badge" style={{ marginLeft: '0.5rem' }}>Vachan {selectedDraft.vachan_number}</span>
              </div>
              <button className="btn btn-danger" style={{ padding: '0.4rem 0.8rem' }} onClick={() => setSelectedDraft(null)}>Close</button>
            </div>
            
            <div className="review-modal-body">
              {/* Left Column: Embed PDF scroll to page */}
              <div className="pdf-viewport">
                {activePdfFile ? (
                  <iframe 
                    className="pdf-iframe" 
                    src={`http://localhost:8000/api/admin/pdf/${activePdfFile}#page=${selectedDraft.page_number}`}
                    title="PDF Original Document Viewer"
                  />
                ) : (
                  <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: 'hsl(var(--text-muted))' }}>
                    PDF file path could not be resolved.
                  </div>
                )}
              </div>

              {/* Right Column: Editable Draft properties */}
              <div className="edit-panel">
                <div className="input-group">
                  <label className="input-label">Original Verse (Rajasthani/Marwadi)</label>
                  <textarea 
                    className="textarea-field"
                    value={editOriginal}
                    onChange={(e) => setEditOriginal(e.target.value)}
                  />
                </div>
                <div className="input-group">
                  <label className="input-label">Hindi Explanation/Meaning</label>
                  <textarea 
                    className="textarea-field"
                    value={editMeaning}
                    onChange={(e) => setEditMeaning(e.target.value)}
                  />
                </div>

                <div className="edit-actions">
                  <button className="btn" style={{ flex: 1 }} onClick={() => saveDraftEdits(false)}>
                    💾 Save Draft
                  </button>
                  <button className="btn btn-primary" style={{ flex: 1.5 }} onClick={() => saveDraftEdits(true)}>
                    ✓ Verify & Approve
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
