import { useState, useEffect, memo, useMemo, lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Sun, Moon, Mic, Languages, Brain, Zap, Camera, Sparkles, Globe } from 'lucide-react';
import { OmLogo } from '../components/landing/OmLogo';
import { useTheme } from '../context/ThemeContext';
import LogoLoop from '../components/LogoLoop';

// Lazy load heavy WebGL component
const LightRays = lazy(() => import('../components/LightRays'));

export const LandingPage = memo(function LandingPage() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const isDark = theme === 'dark';

  // Memoize static language logos data
  const languageLogos = useMemo(() => [
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">हिंदी</span>, title: "Hindi" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">தமிழ்</span>, title: "Tamil" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">తెలుగు</span>, title: "Telugu" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">বাংলা</span>, title: "Bengali" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">मराठी</span>, title: "Marathi" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">ગુજરાતી</span>, title: "Gujarati" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">ಕನ್ನಡ</span>, title: "Kannada" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">മലയാളം</span>, title: "Malayalam" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">ਪੰਜਾਬੀ</span>, title: "Punjabi" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">ଓଡ଼ିଆ</span>, title: "Odia" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">اردو</span>, title: "Urdu" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">অসমীয়া</span>, title: "Assamese" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">संस्कृत</span>, title: "Sanskrit" },
    { node: <span className="text-base sm:text-lg font-normal tracking-wide font-sans">English</span>, title: "English" },
  ], []);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className={`min-h-screen font-sans selection:bg-gray-500/30 ${isDark
      ? 'bg-[#0a0a0a] text-white'
      : 'bg-[#FAFAFA] text-[#111]'}`}
    >
      {/* Ambient Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className={`absolute top-[-20%] left-1/2 -translate-x-1/2 w-[1000px] h-[1000px] rounded-full blur-[120px] opacity-20
          ${isDark ? 'bg-white/5' : 'bg-gray-400/20'}`} />
        <div className={`absolute bottom-[-20%] right-[-10%] w-[800px] h-[800px] rounded-full blur-[100px] opacity-10
          ${isDark ? 'bg-white/5' : 'bg-gray-400/20'}`} />
      </div>

      {/* LightRays Background - Only in dark mode, lazy loaded */}
      {isDark && (
        <Suspense fallback={null}>
          <div className="fixed inset-0 pointer-events-none z-0 opacity-40">
            <LightRays
              raysOrigin="top-center"
              raysColor="#525252"
              raysSpeed={0.2}
              lightSpread={0.6}
              rayLength={1.0}
              followMouse={true}
              mouseInfluence={0.05}
              noiseAmount={0.08}
              distortion={0.05}
              fadeDistance={0.5}
              saturation={0.5}
              pulsating={true}
            />
          </div>
        </Suspense>
      )}

      {/* Header */}
      <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500
        ${isDark ? 'bg-[#0a0a0a]/50 border-b border-white/[0.03]' : 'bg-[#FAFAFA]/70 border-b border-black/[0.03]'} backdrop-blur-xl`}>
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-2 group cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <OmLogo variant="minimal" size={32} color={isDark ? 'dark' : 'light'} animated={false} />
            <span className={`font-bold text-lg tracking-tight ${isDark ? 'text-white' : 'text-black'}`}>Shiksha Setu</span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={toggleTheme}
              className={`p-2.5 rounded-full transition-all duration-300 hover:rotate-12
                ${isDark ? 'hover:bg-white/10 text-white/60 hover:text-white' : 'hover:bg-black/5 text-black/40 hover:text-black'}`}
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <button
              onClick={() => navigate('/auth')}
              className={`px-6 py-2.5 text-sm font-semibold rounded-full transition-all duration-300 hover:scale-105 active:scale-95
                ${isDark
                  ? 'bg-white text-black hover:bg-gray-100 shadow-[0_0_20px_-5px_rgba(255,255,255,0.3)]'
                  : 'bg-[#111] text-white hover:bg-black/90 shadow-[0_4px_15px_-3px_rgba(0,0,0,0.2)]'
                }`}
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="relative pt-32 pb-16 px-6 flex flex-col items-center justify-center min-h-[80vh] animate-enter">
        <div className="max-w-4xl mx-auto text-center relative z-10">
          {/* Badge */}
          <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-medium mb-8 backdrop-blur-md border transition-all duration-300 hover:scale-105 cursor-default
            ${isDark ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-emerald-50 border-emerald-200 text-emerald-700 shadow-sm'
          }`}>
            <Sparkles className={`w-3 h-3`} />
            <span>Open AI • Safe & Unrestricted</span>
          </div>

          {/* Main heading */}
          <h1 className={`text-5xl sm:text-6xl md:text-7xl font-bold tracking-[-0.03em] leading-[1.1] mb-6
            ${isDark ? 'text-white' : 'text-[#111]'}`}>
            AI for <br />
            <span className={`bg-clip-text text-transparent bg-gradient-to-b ${isDark ? 'from-white via-white to-white/50' : 'from-black via-black to-black/40'}`}>
              noble purposes
            </span>
          </h1>

          {/* Subtitle */}
          <p className={`text-lg sm:text-xl font-medium leading-relaxed mb-10 max-w-xl mx-auto tracking-tight
            ${isDark ? 'text-white/50' : 'text-black/60'}`}>
            Safe AI without restrictions. <br className="hidden sm:block" />
            Built for education, research, and beyond — in 22 Indian languages.
          </p>

          {/* CTA */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => navigate('/chat')}
              className={`group relative inline-flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold tracking-tight transition-all duration-300 hover:scale-105 hover:shadow-lg
                ${isDark
                  ? 'bg-white text-black shadow-[0_0_20px_-5px_rgba(255,255,255,0.3)]'
                  : 'bg-[#111] text-white shadow-[0_10px_20px_-5px_rgba(0,0,0,0.2)]'
                }`}
            >
              Get Started
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </button>

            <button
              onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
              className={`px-6 py-3 rounded-full text-sm font-medium transition-all duration-300 hover:scale-105
                ${isDark
                  ? 'text-white/70 hover:text-white bg-white/[0.05] hover:bg-white/[0.1]'
                  : 'text-black/70 hover:text-black bg-white shadow-sm border border-black/[0.05] hover:bg-gray-50'
                }`}
            >
              How it works
            </button>
          </div>
        </div>

        {/* Language Loop */}
        <div className="absolute bottom-8 left-0 right-0 opacity-60 hover:opacity-100 transition-opacity duration-500">
          <LogoLoop
            logos={languageLogos}
            speed={40}
            direction="left"
            logoHeight={24}
            gap={48}
            hoverSpeed={10}
            fadeOut
            fadeOutColor={isDark ? '#0a0a0a' : '#ffffff'}
            className={isDark ? 'text-white/40' : 'text-black/40'}
          />
        </div>
      </main>

      {/* Bento Grid Features - All 8 AI Models */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className={`text-3xl md:text-4xl font-bold tracking-tight mb-4 ${isDark ? 'text-white' : 'text-black'}`}>
              Powered by 8 AI Models
            </h2>
            <p className={`text-lg font-medium max-w-xl mx-auto ${isDark ? 'text-white/50' : 'text-black/50'}`}>
              Enterprise-grade technology, 100% local, zero data leaves your device.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. LLM - Qwen */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-violet-500/20 text-violet-400' : 'bg-violet-100 text-violet-600'}`}>
                  <Brain className="w-5 h-5" />
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>LLM</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>Qwen2.5-3B</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                Advanced reasoning engine, INT4 quantized for 50+ tok/s on Apple Silicon.
              </p>
            </div>

            {/* 2. Translation - IndicTrans2 */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600'}`}>
                  <Languages className="w-5 h-5" />
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>Translation</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>IndicTrans2-1B</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                22 Indian languages with cultural context preserved. 1B parameter model.
              </p>
            </div>

            {/* 3. Embeddings - BGE-M3 */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-600'}`}>
                  <Zap className="w-5 h-5" />
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>Embeddings</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>BGE-M3</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                1024-dim vectors at 348 texts/sec for semantic search and RAG retrieval.
              </p>
            </div>

            {/* 4. Reranking - BGE Reranker */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-600'}`}>
                  <Sparkles className="w-5 h-5" />
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>Reranker</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>BGE-Reranker-v2</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                Cross-encoder reranking at 2.6ms/doc for pinpoint-accurate search results.
              </p>
            </div>

            {/* 5. TTS - MMS */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-pink-500/20 text-pink-400' : 'bg-pink-100 text-pink-600'}`}>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>TTS</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>MMS-TTS</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                Natural text-to-speech at 31x realtime. Read-aloud in multiple languages.
              </p>
            </div>

            {/* 6. STT - Whisper */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-cyan-500/20 text-cyan-400' : 'bg-cyan-100 text-cyan-600'}`}>
                  <Mic className="w-5 h-5" />
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>STT</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>Whisper V3 Turbo</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                Voice-to-text with 99% accuracy. Record lectures, get instant notes.
              </p>
            </div>

            {/* 7. OCR - GOT-OCR2 */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-orange-500/20 text-orange-400' : 'bg-orange-100 text-orange-600'}`}>
                  <Camera className="w-5 h-5" />
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>OCR</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>GOT-OCR2</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                Upload handwritten notes, diagrams, or textbook pages — instant extraction.
              </p>
            </div>

            {/* 8. Safety Pipeline */}
            <div className={`p-6 rounded-[1.5rem] border transition-all duration-500 hover:scale-[1.02] group
              ${isDark ? 'bg-[#111] border-white/[0.05] hover:border-white/[0.1]' : 'bg-white border-black/[0.04] shadow-[0_2px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_10px_30px_rgba(0,0,0,0.06)]'}`}>
              <div className="flex items-start justify-between mb-4">
                <div className={`p-2.5 rounded-xl ${isDark ? 'bg-red-500/20 text-red-400' : 'bg-red-100 text-red-600'}`}>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${isDark ? 'bg-white/10 text-white/50' : 'bg-black/5 text-black/50'}`}>Safety</span>
              </div>
              <h3 className={`text-lg font-bold mb-1.5 ${isDark ? 'text-white' : 'text-black'}`}>3-Pass Safety</h3>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-white/50' : 'text-black/50'}`}>
                Semantic + logical + safety verification on every response. Always safe.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section - Minimal */}
      <section className={`py-24 px-6 border-y ${isDark ? 'border-white/[0.05]' : 'border-black/[0.05]'}`}>
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { label: 'Languages', value: '22', icon: <Globe className="w-4 h-4" /> },
              { label: 'AI Models', value: '8', icon: <Brain className="w-4 h-4" /> },
              { label: 'Latency', value: '<2s', icon: <Zap className="w-4 h-4" /> },
              { label: 'Cost', value: '₹0', icon: <Sparkles className="w-4 h-4" /> },
            ].map((stat) => (
              <div key={stat.label} className="text-center group">
                <div className={`flex items-center justify-center gap-2 mb-3 opacity-50 group-hover:opacity-100 transition-opacity ${isDark ? 'text-white' : 'text-black'}`}>
                  {stat.icon}
                  <span className="text-xs font-bold uppercase tracking-wider">{stat.label}</span>
                </div>
                <div className={`text-4xl md:text-5xl font-bold tracking-tighter ${isDark ? 'text-white' : 'text-black'}`}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-32 px-6 text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className={`text-4xl md:text-5xl font-bold tracking-tighter mb-6 ${isDark ? 'text-white' : 'text-black'}`}>
            Knowledge is a right.
          </h2>
          <p className={`text-lg md:text-xl font-medium mb-10 ${isDark ? 'text-white/50' : 'text-black/50'}`}>
            No paywalls. No restrictions. Just possibilities.
          </p>
          <button
            onClick={() => navigate('/auth')}
            className={`group inline-flex items-center gap-2 px-8 py-4 rounded-full text-base font-semibold tracking-tight transition-all duration-300 hover:scale-105
              ${isDark
                ? 'bg-white text-black hover:bg-gray-100'
                : 'bg-black text-white hover:bg-gray-900'
              }`}
          >
            Get Started Free
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className={`py-12 px-6 ${isDark ? 'border-t border-white/[0.05]' : 'border-t border-black/[0.05]'}`}>
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="flex items-center gap-3 opacity-50 hover:opacity-100 transition-opacity">
            <OmLogo variant="minimal" size={24} color={isDark ? 'dark' : 'light'} animated={false} />
            <span className={`text-sm font-medium ${isDark ? 'text-white' : 'text-black'}`}>© 2025 Shiksha Setu</span>
          </div>

          <div className="flex gap-8">
            {['Privacy', 'Terms', 'Contact'].map((link) => (
              <a key={link} href="#" className={`text-sm font-medium transition-colors ${isDark ? 'text-white/40 hover:text-white' : 'text-black/40 hover:text-black'}`}>
                {link}
              </a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
});

export default LandingPage;
