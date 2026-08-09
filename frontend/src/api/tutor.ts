/**
 * Tutor API - grounded explanations from the NCERT corpus.
 *
 * The question's language and the answer's language are independent. Ask in
 * Hinglish, get English back if that is what you picked; retrieval is
 * cross-lingual, so the question never has to declare what it is written in.
 */

const API_BASE = '/api/v2';

// Two model calls, sometimes three with a diagram, and the first request after
// a cold start waits for the embedding model as well.
const EXPLAIN_TIMEOUT_MS = 120_000;

export const ANSWER_LANGUAGES = [
  'English',
  'Hindi',
  'Hinglish',
  'Urdu',
  'Marathi',
  'Bengali',
  'Tamil',
  'Telugu',
  'Gujarati',
  'Kannada',
  'Malayalam',
  'Punjabi',
  'Odia',
] as const;

export type AnswerLanguage = (typeof ANSWER_LANGUAGES)[number];

export interface TutorSource {
  grade: number | null;
  subject: string | null;
  chapter: number | null;
  url: string | null;
  similarity: number;
}

export interface ExplainResponse {
  answer: string;
  answer_language: string;
  grade: number | null;
  grade_was_detected: boolean;
  sources: TutorSource[];
  diagram: string | null;
  diagram_note: string | null;
}

export interface ExplainRequest {
  question: string;
  /** Omit or null to let the tutor work out which class covers the topic. */
  grade?: number | null;
  answer_language: AnswerLanguage;
  diagram?: boolean;
}

export async function explain(
  request: ExplainRequest,
  signal?: AbortSignal
): Promise<ExplainResponse> {
  const controller = new AbortController();

  // A caller's cancellation and this timeout abort the same fetch, so they are
  // tracked apart — reporting a cancellation as a timeout puts a false error
  // on screen every time a question is superseded.
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, EXPLAIN_TIMEOUT_MS);

  signal?.addEventListener('abort', () => controller.abort(), { once: true });

  try {
    const response = await fetch(`${API_BASE}/tutor/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    if (!response.ok) {
      // The endpoint returns a usable sentence for the cases a student will
      // actually hit — nothing ingested on the topic, model unavailable.
      const detail = await response
        .json()
        .then((body) => body?.detail as string | undefined)
        .catch(() => undefined);

      throw new Error(detail || `Request failed (${response.status})`);
    }

    return (await response.json()) as ExplainResponse;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      if (timedOut) throw new Error('That took too long. Try a shorter question.');
      throw error;
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const tutor = { explain };
