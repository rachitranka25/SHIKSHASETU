/**
 * Learn - ask a question, get taught from the NCERT textbooks.
 *
 * The two selectors carry the whole idea:
 *
 * - Class may be left on "Find it for me". A student who does not know which
 *   year covers Pythagoras should not have to; the tutor reads the class off
 *   the material that matches and says which one it picked.
 *
 * - Answer language is independent of the question's. Type in Hinglish and
 *   pick English, and the explanation comes back in English. Nothing asks what
 *   language the question is in, because retrieval does not need to be told.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  GraduationCap,
  Languages,
  Loader2,
  AlertCircle,
  ExternalLink,
  Sparkles,
  BookOpenCheck,
} from 'lucide-react';

import { explain, ANSWER_LANGUAGES } from '../api/tutor';
import type { AnswerLanguage, ExplainResponse } from '../api/tutor';
import { getLibrary } from '../api/library';
import { useThemeStore } from '../store';
import ReadingControls, {
  loadPreferences,
  readingStyle,
} from '../components/ReadingControls';
import type { ReadingPreferences } from '../components/ReadingControls';

const EXAMPLES = [
  'Can you teach me the Pythagoras theorem?',
  'Prakash sanshleshan kya hai aur kaise hota hai?',
  'Why does iron rust, and how do we stop it?',
];

export default function Learn() {
  const resolvedTheme = useThemeStore((state) => state.resolvedTheme);
  const isDark = resolvedTheme === 'dark';

  const [question, setQuestion] = useState('');
  const [grade, setGrade] = useState<number | null>(null);
  const [language, setLanguage] = useState<AnswerLanguage>('English');
  const [wantDiagram, setWantDiagram] = useState(true);
  const [readingSupport, setReadingSupport] = useState(false);
  const [preferences, setPreferences] = useState<ReadingPreferences>(loadPreferences);

  const [availableGrades, setAvailableGrades] = useState<number[]>([]);
  const [result, setResult] = useState<ExplainResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getLibrary(controller.signal)
      .then((library) => setAvailableGrades(library.grades))
      .catch(() => {
        /* The class picker is a convenience; the tutor works without it. */
      });
    return () => controller.abort();
  }, []);

  useEffect(() => () => inFlight.current?.abort(), []);

  const ask = useCallback(
    async (event?: React.FormEvent, override?: string) => {
      event?.preventDefault();

      const text = (override ?? question).trim();
      if (text.length < 3) return;
      if (override) setQuestion(override);

      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;

      setPending(true);
      setError(null);
      setResult(null);

      try {
        const response = await explain(
          {
            question: text,
            grade,
            answer_language: language,
            diagram: wantDiagram,
            reading_support: readingSupport,
          },
          controller.signal
        );
        setResult(response);
      } catch (caught) {
        if (!controller.signal.aborted) setError((caught as Error).message);
      } finally {
        if (inFlight.current === controller) setPending(false);
      }
    },
    [question, grade, language, wantDiagram, readingSupport]
  );

  const panel = isDark
    ? 'bg-white/[0.04] border-white/[0.08]'
    : 'bg-white border-gray-200/80 shadow-sm';
  const muted = isDark ? 'text-white/60' : 'text-gray-600';
  const faint = isDark ? 'text-white/40' : 'text-gray-400';

  return (
    <div
      className={`h-full overflow-y-auto ${isDark ? 'bg-[#0a0a0a] text-white' : 'bg-[#fafafa] text-gray-900'}`}
      id="main-content"
    >
      <div className="mx-auto w-full max-w-3xl px-4 py-8">
        <header className="mb-6">
          <div className="flex items-center gap-3">
            <GraduationCap className="h-6 w-6 text-[#F4D47A]" aria-hidden="true" />
            <h1 className="text-2xl font-semibold">Learn</h1>
          </div>
          <p className={`mt-2 text-body-sm ${muted}`}>
            Ask in any language — English, Hindi, Hinglish, whatever is easiest.
            The answer comes back in the language you pick, taught from the NCERT
            textbooks.
          </p>
        </header>

        <form onSubmit={ask} className="mb-6 space-y-3">
          <label htmlFor="tutor-question" className="sr-only">
            Your question
          </label>
          <textarea
            id="tutor-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              // Enter asks; Shift+Enter is a newline, as in every chat box.
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void ask();
              }
            }}
            rows={3}
            maxLength={1000}
            placeholder="Can you teach me the Pythagoras theorem?"
            className={`w-full resize-y rounded-card border px-3 py-2.5 text-body-sm outline-none
              focus-visible:ring-2 focus-visible:ring-[#F4D47A] ${panel}
              ${isDark ? 'placeholder:text-white/30' : 'placeholder:text-gray-400'}`}
          />

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label htmlFor="tutor-grade" className={`mb-1 block text-body-sm ${faint}`}>
                Class
              </label>
              <select
                id="tutor-grade"
                value={grade ?? ''}
                onChange={(e) => setGrade(e.target.value ? Number(e.target.value) : null)}
                className={`min-h-touch rounded-btn border px-3 text-body-sm outline-none
                  focus-visible:ring-2 focus-visible:ring-[#F4D47A] ${panel}`}
              >
                <option value="">Find it for me</option>
                {availableGrades.map((g) => (
                  <option key={g} value={g}>
                    Class {g}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="tutor-language"
                className={`mb-1 flex items-center gap-1 text-body-sm ${faint}`}
              >
                <Languages className="h-3 w-3" aria-hidden="true" />
                Answer in
              </label>
              <select
                id="tutor-language"
                value={language}
                onChange={(e) => setLanguage(e.target.value as AnswerLanguage)}
                className={`min-h-touch rounded-btn border px-3 text-body-sm outline-none
                  focus-visible:ring-2 focus-visible:ring-[#F4D47A] ${panel}`}
              >
                {ANSWER_LANGUAGES.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            <label className={`flex min-h-touch items-center gap-2 text-body-sm ${muted}`}>
              <input
                type="checkbox"
                checked={wantDiagram}
                onChange={(e) => setWantDiagram(e.target.checked)}
                className="h-4 w-4 accent-[#F4D47A]"
              />
              Diagram
            </label>

            <label
              className={`flex min-h-touch items-center gap-2 text-body-sm ${muted}`}
              title="Shorter sentences and commoner words, with the hard words broken into syllables"
            >
              <input
                type="checkbox"
                checked={readingSupport}
                onChange={(e) => setReadingSupport(e.target.checked)}
                className="h-4 w-4 accent-[#F4D47A]"
              />
              <BookOpenCheck className="h-4 w-4" aria-hidden="true" />
              Easier reading
            </label>

            <button
              type="submit"
              disabled={pending || question.trim().length < 3}
              className={`ml-auto min-h-touch rounded-btn px-5 text-body-sm font-medium
                transition-all duration-fast active:scale-[0.98] disabled:opacity-40
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F4D47A]
                ${isDark ? 'bg-[#F4D47A] text-[#0a0a0a] hover:bg-[#f7dd96]' : 'bg-gray-900 text-white hover:bg-gray-800'}`}
            >
              {pending ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Teaching…
                </span>
              ) : (
                'Teach me'
              )}
            </button>
          </div>
        </form>

        {!result && !pending && !error && (
          <div className="mb-8">
            <p className={`mb-2 text-body-sm ${faint}`}>Try one of these</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => void ask(undefined, example)}
                  className={`min-h-touch rounded-btn border px-3 text-body-sm
                    transition-all duration-fast active:scale-[0.98] ${panel}
                    focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F4D47A]`}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className={`mb-6 flex items-start gap-2 rounded-card border p-3 text-body-sm
              ${isDark ? 'border-red-500/20 bg-red-500/10 text-red-300' : 'border-red-200 bg-red-50 text-red-700'}`}
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {result && (
          <article className="space-y-5">
            <div className={`flex flex-wrap items-center gap-2 text-body-sm ${muted}`}>
              {result.grade != null && (
                <span className="rounded bg-[#F4D47A]/15 px-2 py-0.5 font-medium text-[#F4D47A]">
                  Class {result.grade}
                </span>
              )}
              {result.grade_was_detected && (
                <span className={`flex items-center gap-1 ${faint}`}>
                  <Sparkles className="h-3 w-3" aria-hidden="true" />
                  class found from the textbooks
                </span>
              )}
              <span className={`ml-auto ${faint}`}>in {result.answer_language}</span>
            </div>

            <div className={`rounded-card border p-4 ${panel}`}>
              <p
                className="whitespace-pre-wrap text-body"
                style={readingSupport ? readingStyle(preferences) : undefined}
              >
                {result.answer}
              </p>
            </div>

            {readingSupport && (
              <ReadingControls
                preferences={preferences}
                onChange={setPreferences}
                isDark={isDark}
              />
            )}

            {result.readability && (
              <section className={`rounded-card border p-4 ${panel}`} aria-label="Reading measurements">
                <h2 className={`mb-2 text-body-sm font-medium ${faint}`}>
                  How this compares with the textbook
                </h2>
                <dl className={`grid grid-cols-2 gap-x-6 gap-y-1 text-body-sm ${muted}`}>
                  <dt>Words per sentence</dt>
                  <dd className="tabular-nums">
                    {result.readability.source.words_per_sentence} &rarr;{' '}
                    <strong>{result.readability.answer.words_per_sentence}</strong>
                  </dd>
                  <dt>
                    {result.readability.answer.script === 'Latin' ? 'Syllables' : 'Aksharas'} per word
                  </dt>
                  <dd className="tabular-nums">
                    {result.readability.source.units_per_word} &rarr;{' '}
                    <strong>{result.readability.answer.units_per_word}</strong>
                  </dd>
                  {result.readability.answer.grade_estimate != null && (
                    <>
                      <dt>Reading grade</dt>
                      <dd className="tabular-nums">
                        {result.readability.source.grade_estimate} &rarr;{' '}
                        <strong>{result.readability.answer.grade_estimate}</strong>
                      </dd>
                    </>
                  )}
                </dl>

                {Object.keys(result.readability.segmented_words).length > 0 && (
                  <div className="mt-3">
                    <p className={`mb-1 text-body-sm ${faint}`}>
                      Longer words, split the way they are read
                    </p>
                    <ul className="flex flex-wrap gap-2">
                      {Object.entries(result.readability.segmented_words)
                        .slice(0, 10)
                        .map(([word, units]) => (
                          <li
                            key={word}
                            className={`rounded-btn border px-2 py-1 text-body-sm ${panel}`}
                          >
                            {units.join('\u00b7')}
                          </li>
                        ))}
                    </ul>
                  </div>
                )}
              </section>
            )}

            {result.diagram && (
              <figure className={`rounded-card border p-4 ${panel}`}>
                {/* A data: URI holding a PNG, rendered as an image. The earlier
                    version injected model-authored SVG with
                    dangerouslySetInnerHTML; an <img> cannot execute anything,
                    so the whole class of injection goes away with it. */}
                <img
                  src={result.diagram}
                  alt={`Illustration for: ${question.trim()}`}
                  className="mx-auto w-full max-w-lg rounded"
                  loading="lazy"
                />
                {result.diagram_note && (
                  <figcaption className={`mt-3 text-body-sm ${faint}`}>
                    {result.diagram_note}
                  </figcaption>
                )}
              </figure>
            )}

            {result.sources.length > 0 && (
              <section>
                <h2 className={`mb-2 text-body-sm font-medium ${faint}`}>
                  Taught from
                </h2>
                <ul className="space-y-1.5">
                  {result.sources.slice(0, 4).map((source, index) => (
                    <li
                      key={`${source.url}-${index}`}
                      className={`flex flex-wrap items-center gap-2 text-body-sm ${muted}`}
                    >
                      <span>
                        Class {source.grade} {source.subject}
                        {source.chapter != null && `, chapter ${source.chapter}`}
                      </span>
                      {source.url && (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="inline-flex items-center gap-1 rounded text-[#F4D47A] hover:underline
                            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F4D47A]"
                        >
                          open
                          <ExternalLink className="h-3 w-3" aria-hidden="true" />
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </article>
        )}
      </div>
    </div>
  );
}
