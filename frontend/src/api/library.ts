/**
 * Library API - browse and search the ingested NCERT curriculum.
 *
 * Both endpoints are public: shared curriculum carries no organization, so
 * reading it needs no account. No auth header is sent, deliberately — the
 * response cache on the backend is keyed by the caller's Authorization header,
 * and sending one would give every signed-in user their own cache entry for
 * identical public content.
 */

const API_BASE = '/api/v2';

// The first search after a cold start waits for a 2.5 GB embedding model to
// load. Later ones return in about a second.
const SEARCH_TIMEOUT_MS = 45_000;
const LIST_TIMEOUT_MS = 15_000;

export interface BookSummary {
  book_code: string;
  title: string;
  grade: number;
  medium: string;
  chapters: number;
  chunks: number;
}

export interface LibraryResponse {
  books: BookSummary[];
  total_books: number;
  total_chapters: number;
  total_chunks: number;
  grades: number[];
  subjects: string[];
}

export interface SearchHit {
  text: string;
  similarity: number;
  grade: number | null;
  subject: string | null;
  medium: string | null;
  chapter: number | null;
  book_code: string | null;
  source_url: string | null;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  count: number;
}

export interface SearchFilters {
  grade?: number;
  subject?: string;
  medium?: string;
  limit?: number;
}

async function request<T>(path: string, timeoutMs: number, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();

  // A caller's cancellation and our own timeout both abort the same fetch, so
  // they have to be told apart afterwards. Reporting a cancellation as a
  // timeout puts a false "the model may still be loading" error on screen
  // every time an effect is cleaned up — which React StrictMode does on every
  // mount in development, and which happens for real whenever a user navigates
  // away or types a second search.
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  signal?.addEventListener('abort', () => controller.abort(), { once: true });

  try {
    const response = await fetch(`${API_BASE}${path}`, { signal: controller.signal });

    if (!response.ok) {
      const detail = await response.text().catch(() => '');
      throw new Error(
        response.status === 503
          ? 'Search is warming up. Try again in a moment.'
          : `Request failed (${response.status})${detail ? `: ${detail.slice(0, 120)}` : ''}`
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      if (timedOut) {
        throw new Error('Timed out. The model may still be loading.');
      }
      // Cancelled by the caller. Re-thrown with the name intact so callers can
      // recognise it and stay silent — a superseded request is not a failure.
      throw error;
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

/** Everything currently ingested, grouped by textbook. */
export function getLibrary(signal?: AbortSignal): Promise<LibraryResponse> {
  return request<LibraryResponse>('/library', LIST_TIMEOUT_MS, signal);
}

/**
 * Search the curriculum by meaning.
 *
 * Cross-lingual: a question in Hindi or Marathi retrieves English chapters,
 * because query and passages share one embedding space.
 */
export function searchLibrary(
  query: string,
  filters: SearchFilters = {},
  signal?: AbortSignal
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });

  if (filters.grade != null) params.set('grade', String(filters.grade));
  if (filters.subject) params.set('subject', filters.subject);
  if (filters.medium) params.set('medium', filters.medium);
  if (filters.limit != null) params.set('limit', String(filters.limit));

  return request<SearchResponse>(`/library/search?${params}`, SEARCH_TIMEOUT_MS, signal);
}

export const library = { getLibrary, searchLibrary };
