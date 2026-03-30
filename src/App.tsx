import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown, ExternalLink, MessageSquare, Send, User, Bot, Lock, Loader2 } from 'lucide-react';
import axios from 'axios';

// --- Types ---
type ViewState = 'login' | 'dashboard' | 'chat';
type TabType = 'temp' | '戦型別' | 'themes';

interface ReportDetails {
  reUrl: string;
  banmenImageUrl: string;
  summary: string;
  responseText: string;
  rawKif: string;
}

interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
  thoughts?: string;
}

export default function App() {
  // --- State ---
  const [view, setView] = useState<ViewState>('login');
  const [passcode, setPasscode] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const [activeTab, setActiveTab] = useState<TabType>('temp');
  const [dirs, setDirs] = useState<string[]>([]);
  const [selectedDir, setSelectedDir] = useState<string>('');
  const [battles, setBattles] = useState<string[]>([]);
  const [selectedBattle, setSelectedBattle] = useState<string>('');
  
  const [reportDetails, setReportDetails] = useState<ReportDetails | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // --- API Base URL ---
  // In development, Vite proxies API requests. In production, it's the same origin.
  const apiBase = '';

  // --- Effects ---
  // 1. Fetch directories when tab changes
  useEffect(() => {
    if (view !== 'dashboard') return;
    
    const fetchDirs = async () => {
      try {
        const res = await axios.get(`${apiBase}/api/github/categories/${activeTab}`);
        const data = res.data as any;
        setDirs(data.dirs || []);
        if (data.dirs && data.dirs.length > 0) {
          setSelectedDir(data.dirs[0]);
        } else {
          setSelectedDir('');
          setBattles([]);
          setSelectedBattle('');
          setReportDetails(null);
        }
      } catch (error) {
        console.error("Failed to fetch dirs", error);
        setDirs([]);
      }
    };
    fetchDirs();
  }, [activeTab, view]);

  // 2. Fetch battles when directory changes
  useEffect(() => {
    if (view !== 'dashboard' || !selectedDir) return;

    const fetchBattles = async () => {
      try {
        const res = await axios.get(`${apiBase}/api/github/battles/${activeTab}/${selectedDir}`);
        const data = res.data as any;
        setBattles(data.battles || []);
        if (data.battles && data.battles.length > 0) {
          setSelectedBattle(data.battles[0]);
        } else {
          setSelectedBattle('');
          setReportDetails(null);
        }
      } catch (error) {
        console.error("Failed to fetch battles", error);
        setBattles([]);
      }
    };
    fetchBattles();
  }, [selectedDir, activeTab, view]);

  // 3. Fetch report details when battle changes
  useEffect(() => {
    if (view !== 'dashboard' || !selectedBattle) return;

    const fetchDetails = async () => {
      setIsLoadingDetails(true);
      try {
        const res = await axios.get(`${apiBase}/api/github/report/${activeTab}/${selectedDir}/${selectedBattle}`);
        setReportDetails(res.data);
      } catch (error) {
        console.error("Failed to fetch details", error);
        setReportDetails(null);
      } finally {
        setIsLoadingDetails(false);
      }
    };
    fetchDetails();
  }, [selectedBattle, selectedDir, activeTab, view]);

  // 4. Scroll to bottom of chat
  useEffect(() => {
    if (view === 'chat') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, view]);

  // --- Handlers ---
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoggingIn(true);
    setLoginError('');
    try {
      const res = await axios.post(`${apiBase}/api/auth`, { passcode });
      const data = res.data as any;
      if (data.success) {
        setView('dashboard');
      }
    } catch (error: any) {
      setLoginError(error.response?.data?.message || '認証に失敗しました');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleStartChat = () => {
    if (!reportDetails) return;
    setChatMessages([
      {
        role: 'ai',
        text: 'お疲れ様です。この対局について、どの局面が気になりますか？'
      }
    ]);
    setView('chat');
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatting || !reportDetails) return;

    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setIsChatting(true);

    try {
      // TODO: Pass history if needed for multi-turn conversation
      const res = await axios.post(`${apiBase}/api/chat`, {
        message: userMsg,
        rawKif: reportDetails.rawKif,
        responseText: reportDetails.responseText,
        history: chatMessages
      });
      const data = res.data as any;

      setChatMessages(prev => [
        ...prev,
        { role: 'ai', text: data.text, thoughts: data.thoughts }
      ]);
    } catch (error: any) {
      console.error("Chat error", error);
      setChatMessages(prev => [
        ...prev,
        { role: 'ai', text: `エラーが発生しました: ${error.response?.data?.error || error.message}` }
      ]);
    } finally {
      setIsChatting(false);
    }
  };

  // --- Renderers ---
  if (view === 'login') {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="bg-white p-8 rounded-2xl shadow-lg max-w-sm w-full border border-slate-100">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center">
              <Lock size={32} className="text-indigo-600" />
            </div>
          </div>
          <h1 className="text-xl font-bold text-center text-slate-800 mb-2">将棋パイプライン</h1>
          <p className="text-sm text-center text-slate-500 mb-6">パスコードを入力してロックを解除してください</p>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <input
                type="password"
                value={passcode}
                onChange={(e) => setPasscode(e.target.value)}
                placeholder="パスコード"
                className="w-full px-4 py-3 rounded-xl border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all text-center tracking-widest text-lg"
                autoFocus
              />
            </div>
            {loginError && <p className="text-red-500 text-xs text-center">{loginError}</p>}
            <button
              type="submit"
              disabled={isLoggingIn || !passcode}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white py-3 rounded-xl font-bold shadow-md transition-all flex justify-center items-center"
            >
              {isLoggingIn ? <Loader2 className="animate-spin" size={20} /> : 'ロック解除'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (view === 'chat') {
    return (
      <div className="flex flex-col h-screen bg-slate-50">
        {/* ヘッダー */}
        <header className="bg-slate-900 text-white p-4 flex items-center shadow-md">
          <button onClick={() => setView('dashboard')} className="mr-4 text-slate-300 hover:text-white">
            ← 戻る
          </button>
          <div className="flex-1 truncate">
            <h1 className="text-sm font-semibold truncate">{selectedBattle}</h1>
            <p className="text-xs text-slate-400">Gemini 専属コーチ</p>
          </div>
        </header>

        {/* チャットエリア */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {chatMessages.map((msg, idx) => (
            <div key={idx} className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-slate-300' : 'bg-indigo-600'}`}>
                {msg.role === 'user' ? <User size={18} className="text-slate-600" /> : <Bot size={18} className="text-white" />}
              </div>
              <div className={`p-3 rounded-2xl shadow-sm max-w-[85%] ${
                msg.role === 'user' 
                  ? 'bg-indigo-600 text-white rounded-tr-none' 
                  : 'bg-white text-slate-700 border border-slate-100 rounded-tl-none'
              }`}>
                {msg.thoughts && (
                  <details className="mb-2 group">
                    <summary className="text-xs text-slate-500 cursor-pointer hover:text-indigo-600 flex items-center gap-1">
                      <ChevronDown size={14} className="group-open:rotate-180 transition-transform" />
                      思考プロセスを表示
                    </summary>
                    <div className="mt-2 p-2 bg-slate-50 rounded text-xs text-slate-600 border border-slate-100 whitespace-pre-wrap">
                      {msg.thoughts}
                    </div>
                  </details>
                )}
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.text}
                </p>
              </div>
            </div>
          ))}
          {isChatting && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
                <Bot size={18} className="text-white" />
              </div>
              <div className="bg-white p-3 rounded-2xl rounded-tl-none shadow-sm border border-slate-100">
                <Loader2 className="animate-spin text-indigo-600" size={20} />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* 入力エリア */}
        <div className="bg-white p-3 border-t border-slate-200">
          <form onSubmit={handleSendMessage} className="flex items-center gap-2 bg-slate-100 rounded-full px-4 py-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="メッセージを入力..."
              className="flex-1 bg-transparent outline-none text-sm"
              disabled={isChatting}
            />
            <button 
              type="submit"
              disabled={!chatInput.trim() || isChatting}
              className="text-indigo-600 p-1 hover:bg-indigo-50 rounded-full transition-colors disabled:text-slate-400"
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-8">
      <header className="bg-slate-900 text-white p-4 shadow-md flex justify-between items-center">
        <h1 className="text-lg font-bold tracking-tight">将棋パイプライン WebUI</h1>
        <button onClick={() => setView('login')} className="text-xs text-slate-400 hover:text-white">
          ロック
        </button>
      </header>

      <main className="max-w-md mx-auto p-4 space-y-6">
        {/* 1. タブ選択 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-1 flex">
          {(['temp', '戦型別', 'themes'] as TabType[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeTab === tab
                  ? 'bg-indigo-50 text-indigo-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              {tab === 'themes' ? 'テーマ別' : tab}
            </button>
          ))}
        </div>

        {/* 2. ディレクトリ選択 */}
        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">
            ディレクトリを選択
          </label>
          <div className="relative">
            <select
              value={selectedDir}
              onChange={(e) => setSelectedDir(e.target.value)}
              className="w-full appearance-none bg-white border border-slate-300 text-slate-700 py-3 px-4 pr-8 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              disabled={dirs.length === 0}
            >
              {dirs.length === 0 && <option value="">ディレクトリがありません</option>}
              {dirs.map((dir) => (
                <option key={dir} value={dir}>{dir}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-500">
              <ChevronDown size={16} />
            </div>
          </div>
        </div>

        {/* 3. 対局 (battle_id) 選択 */}
        <div className="space-y-1">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider ml-1">
            対局を選択
          </label>
          <div className="relative">
            <select
              value={selectedBattle}
              onChange={(e) => setSelectedBattle(e.target.value)}
              className="w-full appearance-none bg-white border border-slate-300 text-slate-700 py-3 px-4 pr-8 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              disabled={battles.length === 0}
            >
              {battles.length === 0 && <option value="">対局がありません</option>}
              {battles.map((battle) => (
                <option key={battle} value={battle}>{battle}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-500">
              <ChevronDown size={16} />
            </div>
          </div>
        </div>

        {/* 4. プレビュー欄 */}
        {selectedBattle && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden min-h-[300px] relative">
            {isLoadingDetails ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 z-10">
                <Loader2 className="animate-spin text-indigo-600 mb-2" size={32} />
                <p className="text-sm text-slate-500">データを取得中...</p>
              </div>
            ) : reportDetails ? (
              <>
                <div className="p-4 border-b border-slate-100 bg-slate-50/50">
                  <h2 className="text-sm font-bold text-slate-800 mb-3 truncate">
                    {selectedBattle}
                  </h2>
                  
                  {/* 盤面図画像 */}
                  {reportDetails.banmenImageUrl ? (
                    <div className="mb-4 flex justify-center bg-slate-100 rounded-lg overflow-hidden border border-slate-200">
                      <img 
                        src={reportDetails.banmenImageUrl} 
                        alt="盤面図" 
                        className="max-h-[300px] object-contain"
                        referrerPolicy="no-referrer"
                      />
                    </div>
                  ) : (
                    <div className="mb-4 flex justify-center items-center bg-slate-100 rounded-lg h-32 border border-slate-200">
                      <p className="text-xs text-slate-400">盤面図画像がありません</p>
                    </div>
                  )}

                  {/* ビジュアル（別タブで開くボタン） */}
                  {reportDetails.reUrl && (
                    <a
                      href={reportDetails.reUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-2 w-full bg-slate-800 hover:bg-slate-700 text-white py-2.5 px-4 rounded-lg text-sm font-medium transition-colors"
                    >
                      <ExternalLink size={16} />
                      解析結果を見る（別タブで開く）
                    </a>
                  )}
                </div>

                {/* サマリー */}
                <div className="p-4">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    対局の流れ・総評
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
                    {reportDetails.summary || "サマリーデータがありません"}
                  </p>
                </div>
              </>
            ) : (
              <div className="p-8 text-center text-slate-500 text-sm">
                データが見つかりませんでした
              </div>
            )}
          </div>
        )}

        {/* 5. アクションボタン */}
        <button
          onClick={handleStartChat}
          disabled={!reportDetails || isLoadingDetails}
          className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white py-4 px-6 rounded-xl font-bold shadow-md shadow-indigo-200 transition-all active:scale-[0.98]"
        >
          <MessageSquare size={20} />
          Geminiと深く分析する
        </button>
      </main>
    </div>
  );
}
