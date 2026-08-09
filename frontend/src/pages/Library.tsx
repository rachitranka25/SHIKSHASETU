/**
 * Library - browse and search the ingested NCERT curriculum.
 *
 * The corpus had no interface. Textbooks were being ingested, embedded and
 * indexed with nothing able to show or query them, so this page is the first
 * place the ingestion becomes visible.
 *
 * Search is by meaning rather than keyword, and works across languages: a
 * question typed in Hindi finds English chapters, because the query and the
 * passages share one embedding space. The class filter is not decoration —
 * without it a class 6 question can be answered from a class 12 chapter
 * whenever the wording happens to line up.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Search, Loader2, AlertCircle, ExternalLink, X } from 'lucide-react';

import { getLibrary, searchLibrary } from '../api/library';
import type { BookSummary, LibraryResponse, SearchHit } from '../api/library';
import { useThemeStore } from '../store';

const RESULT_LIMIT = 12;

export default function Library() {
  const resolvedTheme = useThemeStore((state) => state.resolvedTheme);
  const isDark = resolvedTheme === 'dark';

  const [catalogue, setCatalogue] = useState<LibraryResponse | null>(null);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [grade, setGrade] = useState<number | null>(null);
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // A superseded search is cancelled rather than left to race the one that
  // replaced it — the first request after a cold start can take 20 seconds.
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    getLibrary(controller.signal)
      .then(setCatalogue)
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setCatalogueError(error.message);
      });

    return () => controller.abort();
  }, []);

  const runSearch = useCallback(
    async (event?: React.FormEvent) => {
      event?.preventDefault();

      const trimmed = query.trim();
      if (trimmed.length < 2) return;

      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;

      setSearching(true);
      setSearchError(null);

      try {
        const response = await searchLibrary(
          trimmed,
          { grade: grade ?? undefined, limit: RESULT_LIMIT },
          controller.signal
        );
        setHits(response.hits);
      } catch (error) {
        if (!controller.signal.aborted) {
          setSearchError((error as Error).message);
          setHits(null);
        }
      } finally {
        if (inFlight.current === controller) setSearching(false);
      }
    },
    [query, grade]
  );

  useEffect(() => () => inFlight.current?.abort(), []);

  const byGrade = useMemo(() => {
    const groups = new Map<number, BookSummary[]>();
    for (const book of catalogue?.books ?? []) {
      const existing = groups.get(book.grade);
      if (existing) existing.push(book);
      else groups.set(book.grade, [book]);
    }
    return [...groups.entries()].sort(([a], [b]) => a - b);
  }, [catalogue]);

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
      <div className="mx-auto w-full max-w-4xl px-4 py-8">
        <header className="mb-8">
          <div className="flex items-center gap-3">
            <BookOpen className="h-6 w-6 text-[#F4D47A]" aria-hidden="true" />
            <h1 className="text-2xl font-semibold">Curriculum Library</h1>
          </div>
          <p className={`mt-2 text-body-sm ${muted}`}>
            NCERT textbooks, searchable by meaning. Ask in any language — Hindi,
            Marathi and Bengali all find English chapters.
          </p>
        </header>

        {/* ---------- search ---------- */}
        <form onSubmit={runSearch} className="mb-6" role="search">
          <label htmlFor="library-search" className="sr-only">
            Search the curriculum
          </label>

          <div className={`flex items-center gap-2 rounded-btn border px-3 ${panel}`}>
            <Search className={`h-4 w-4 shrink-0 ${faint}`} aria-hidden="true" />
            <input
              id="library-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Why does iron rust?"
              minLength={2}
              maxLength={500}
              className={`min-h-touch flex-1 bg-transparent py-2.5 text-body-sm outline-none
                ${isDark ? 'placeholder:text-white/30' : 'placeholder:text-gray-400'}`}
            />
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery('');
                  setHits(null);
                  setSearchError(null);
                }}
                aria-label="Clear search"
                className={`rounded p-1 transition-colors duration-fast ${faint} hover:${muted}`}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
            <button
              type="submit"
              disabled={searching || query.trim().length < 2}
              className={`min-h-touch rounded-btn px-4 text-body-sm font-medium
                transition-all duration-fast active:scale-[0.98] disabled:opacity-40
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F4D47A]
                ${isDark ? 'bg-white/10 hover:bg-white/15' : 'bg-gray-900 text-white hover:bg-gray-800'}`}
            >
              {searching ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-label="Searching" />
              ) : (
                'Search'
              )}
            </button>
          </div>

          {/* class filter */}
          {(catalogue?.grades.length ?? 0) > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2" role="group" aria-label="Filter by class">
              <span className={`text-body-sm ${faint}`}>Class</span>
              <FilterChip label="Any" active={grade === null} isDark={isDark} onClick={() => setGrade(null)} />
              {catalogue!.grades.map((g) => (
                <FilterChip
                  key={g}
                  label={String(g)}
                  active={grade === g}
                  isDark={isDark}
                  onClick={() => setGrade(grade === g ? null : g)}
                />
              ))}
            </div>
          )}
        </form>

        {searchError && <Notice isDark={isDark} message={searchError} />}

        {/* ---------- results ---------- */}
        {hits !== null && !searchError && (
          <section aria-live="polite" aria-label="Search results" className="mb-10">
            <h2 className={`mb-3 text-body-sm ${muted}`}>
              {hits.length === 0
                ? 'Nothing matched. Try different wording, or clear the class filter.'
                : `${hits.length} passage${hits.length === 1 ? '' : 's'}`}
            </h2>

            <ul className="space-y-3">
              {hits.map((hit, index) => (
                <li key={`${hit.book_code}-${hit.chapter}-${index}`} className={`rounded-card border p-4 ${panel}`}>
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-body-sm">
                    <span className="rounded bg-[#F4D47A]/15 px-2 py-0.5 font-medium text-[#F4D47A]">
                      Class {hit.grade}
                    </span>
                    <span className={muted}>{hit.subject}</span>
                    {hit.chapter != null && <span className={faint}>Chapter {hit.chapter}</span>}
                    <span className={`ml-auto tabular-nums ${faint}`}>
                      {(hit.similarity * 100).toFixed(0)}% match
                    </span>
                  </div>

                  <p className={`text-body-sm leading-relaxed ${isDark ? 'text-white/80' : 'text-gray-700'}`}>
                    {hit.text}
                  </p>

                  {hit.source_url && (
                    <a
                      href={hit.source_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className={`mt-3 inline-flex items-center gap-1.5 text-body-sm text-[#F4D47A] hover:underline
                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F4D47A] rounded`}
                    >
                      Open the NCERT chapter
                      <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ---------- what is ingested ---------- */}
        <section aria-labelledby="catalogue-heading">
          <h2 id="catalogue-heading" className="mb-3 text-lg font-medium">
            Available now
          </h2>

          {catalogueError && <Notice isDark={isDark} message={catalogueError} />}

          {!catalogue && !catalogueError && (
            <p className={`text-body-sm ${muted}`}>Loading…</p>
          )}

          {catalogue && catalogue.total_books === 0 && (
            <p className={`text-body-sm ${muted}`}>
              Nothing ingested yet. Run{' '}
              <code className={`rounded px-1 ${isDark ? 'bg-white/10' : 'bg-gray-100'}`}>
                scripts/ingest_ncert_batched.sh
              </code>{' '}
              to populate the library.
            </p>
          )}

          {catalogue && catalogue.total_books > 0 && (
            <>
              <p className={`mb-4 text-body-sm ${muted}`}>
                {catalogue.total_books} book{catalogue.total_books === 1 ? '' : 's'} ·{' '}
                {catalogue.total_chapters} chapters ·{' '}
                {catalogue.total_chunks.toLocaleString()} searchable passages
              </p>

              <div className="space-y-5">
                {byGrade.map(([classNumber, books]) => (
                  <div key={classNumber}>
                    <h3 className={`mb-2 text-body-sm font-medium ${faint}`}>Class {classNumber}</h3>
                    <ul className="grid gap-2 sm:grid-cols-2">
                      {books!.map((book) => (
                        <li key={book.book_code} className={`rounded-card border p-3 ${panel}`}>
                          <p className="text-body-sm font-medium">{book.title}</p>
                          <p className={`mt-0.5 text-body-sm ${faint}`}>
                            {book.medium} · {book.chapters} chapters · {book.chunks} passages
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  isDark,
  onClick,
}: {
  label: string;
  active: boolean;
  isDark: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-h-touch rounded-btn px-3 text-body-sm transition-all duration-fast active:scale-[0.98]
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F4D47A]
        ${
          active
            ? 'bg-[#F4D47A] font-medium text-[#0a0a0a]'
            : isDark
              ? 'bg-white/[0.06] text-white/70 hover:bg-white/[0.12]'
              : 'bg-white text-gray-600 border border-gray-200/80 hover:bg-gray-50'
        }`}
    >
      {label}
    </button>
  );
}

function Notice({ isDark, message }: { isDark: boolean; message: string }) {
  return (
    <div
      role="alert"
      className={`mb-4 flex items-start gap-2 rounded-card border p-3 text-body-sm
        ${isDark ? 'border-red-500/20 bg-red-500/10 text-red-300' : 'border-red-200 bg-red-50 text-red-700'}`}
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
