/**
 * Reading controls for learners who find decoding effortful.
 *
 * WHAT THE EVIDENCE ACTUALLY SAYS
 *
 * Letter and word spacing is the one typographic intervention with strong
 * experimental support. Zorzi et al. (PNAS, 2012) found extra-large spacing
 * improved reading speed and halved errors in dyslexic children, with no
 * training, and no equivalent effect in controls. So spacing is the first
 * control, it is on by default in this panel, and it has real range.
 *
 * Dyslexia-specific fonts and coloured overlays are popular and weakly
 * evidenced — controlled studies have not reliably shown them to beat ordinary
 * fonts or plain backgrounds. They are offered because some readers do report
 * benefit, and labelled as preference rather than dressed up as science.
 *
 * The settings live in localStorage rather than on the account: a student
 * should not have to sign in to read comfortably.
 */

import { useEffect, useState } from 'react';
import { Type, RotateCcw } from 'lucide-react';

const STORAGE_KEY = 'shiksha.reading-preferences';

export interface ReadingPreferences {
  /** Extra letter spacing in em. Evidence-backed. */
  letterSpacing: number;
  /** Extra word spacing in em. Evidence-backed. */
  wordSpacing: number;
  /** Line height multiplier. Helps the eye return to the right line. */
  lineHeight: number;
  /** Characters per line. Long lines make return sweeps harder. */
  lineWidth: number;
  fontScale: number;
  /** Preference, not established science. */
  dyslexiaFont: boolean;
  /** Preference, not established science. */
  tintedBackground: boolean;
}

export const DEFAULT_PREFERENCES: ReadingPreferences = {
  letterSpacing: 0.06,
  wordSpacing: 0.16,
  lineHeight: 1.9,
  lineWidth: 62,
  fontScale: 1.1,
  dyslexiaFont: false,
  tintedBackground: false,
};

export function loadPreferences(): ReadingPreferences {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return DEFAULT_PREFERENCES;
    // Merge rather than replace, so a preference added in a later release does
    // not come back undefined for someone who saved settings before it existed.
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function savePreferences(preferences: ReadingPreferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    /* Private browsing, quota — the settings still apply for this session. */
  }
}

/** Inline styles a passage should carry for these preferences. */
export function readingStyle(preferences: ReadingPreferences): React.CSSProperties {
  return {
    letterSpacing: `${preferences.letterSpacing}em`,
    wordSpacing: `${preferences.wordSpacing}em`,
    lineHeight: preferences.lineHeight,
    maxWidth: `${preferences.lineWidth}ch`,
    fontSize: `${preferences.fontScale}rem`,
    fontFamily: preferences.dyslexiaFont
      ? '"OpenDyslexic", "Comic Sans MS", system-ui, sans-serif'
      : undefined,
    // A soft cream ground rather than white. Contested as a dyslexia remedy,
    // but reduced glare is a comfort setting people are entitled to have.
    backgroundColor: preferences.tintedBackground ? '#FBF3E4' : undefined,
    color: preferences.tintedBackground ? '#2B2A26' : undefined,
    padding: preferences.tintedBackground ? '0.75rem' : undefined,
    borderRadius: preferences.tintedBackground ? '0.5rem' : undefined,
  };
}

interface Props {
  preferences: ReadingPreferences;
  onChange: (preferences: ReadingPreferences) => void;
  isDark: boolean;
}

export default function ReadingControls({ preferences, onChange, isDark }: Props) {
  const [local, setLocal] = useState(preferences);

  useEffect(() => setLocal(preferences), [preferences]);

  const update = <K extends keyof ReadingPreferences>(
    key: K,
    value: ReadingPreferences[K]
  ) => {
    const next = { ...local, [key]: value };
    setLocal(next);
    onChange(next);
    savePreferences(next);
  };

  const label = isDark ? 'text-white/60' : 'text-gray-600';
  const faint = isDark ? 'text-white/40' : 'text-gray-400';
  const panel = isDark
    ? 'bg-white/[0.04] border-white/[0.08]'
    : 'bg-white border-gray-200/80 shadow-sm';

  return (
    <section className={`rounded-card border p-4 ${panel}`} aria-labelledby="reading-controls">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="reading-controls" className="flex items-center gap-2 text-body-sm font-medium">
          <Type className="h-4 w-4 text-[#F4D47A]" aria-hidden="true" />
          Reading comfort
        </h2>
        <button
          type="button"
          onClick={() => {
            setLocal(DEFAULT_PREFERENCES);
            onChange(DEFAULT_PREFERENCES);
            savePreferences(DEFAULT_PREFERENCES);
          }}
          className={`flex items-center gap-1 rounded px-2 py-1 text-body-sm ${faint}
            hover:${label} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F4D47A]`}
        >
          <RotateCcw className="h-3 w-3" aria-hidden="true" />
          Reset
        </button>
      </div>

      <div className="space-y-3">
        <Slider
          id="letter-spacing"
          label="Letter spacing"
          hint="Increases reading speed and reduces errors for dyslexic readers (Zorzi et al., 2012)"
          value={local.letterSpacing}
          min={0}
          max={0.25}
          step={0.01}
          onChange={(v) => update('letterSpacing', v)}
          labelClass={label}
          hintClass={faint}
        />
        <Slider
          id="word-spacing"
          label="Word spacing"
          value={local.wordSpacing}
          min={0}
          max={0.6}
          step={0.02}
          onChange={(v) => update('wordSpacing', v)}
          labelClass={label}
          hintClass={faint}
        />
        <Slider
          id="line-height"
          label="Line spacing"
          value={local.lineHeight}
          min={1.2}
          max={2.6}
          step={0.1}
          onChange={(v) => update('lineHeight', v)}
          labelClass={label}
          hintClass={faint}
        />
        <Slider
          id="line-width"
          label="Line width"
          hint="Shorter lines make it easier to find the start of the next one"
          value={local.lineWidth}
          min={35}
          max={90}
          step={1}
          unit=" characters"
          onChange={(v) => update('lineWidth', v)}
          labelClass={label}
          hintClass={faint}
        />
        <Slider
          id="font-scale"
          label="Text size"
          value={local.fontScale}
          min={0.9}
          max={1.8}
          step={0.05}
          unit="×"
          onChange={(v) => update('fontScale', v)}
          labelClass={label}
          hintClass={faint}
        />

        <fieldset className="pt-1">
          <legend className={`mb-1.5 text-body-sm ${faint}`}>
            Preferences — some readers find these help, though studies have not
            shown a reliable benefit
          </legend>
          <div className="flex flex-wrap gap-4">
            <label className={`flex items-center gap-2 text-body-sm ${label}`}>
              <input
                type="checkbox"
                checked={local.dyslexiaFont}
                onChange={(e) => update('dyslexiaFont', e.target.checked)}
                className="h-4 w-4 accent-[#F4D47A]"
              />
              Dyslexia font
            </label>
            <label className={`flex items-center gap-2 text-body-sm ${label}`}>
              <input
                type="checkbox"
                checked={local.tintedBackground}
                onChange={(e) => update('tintedBackground', e.target.checked)}
                className="h-4 w-4 accent-[#F4D47A]"
              />
              Cream background
            </label>
          </div>
        </fieldset>
      </div>
    </section>
  );
}

function Slider({
  id,
  label,
  hint,
  value,
  min,
  max,
  step,
  unit = '',
  onChange,
  labelClass,
  hintClass,
}: {
  id: string;
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (value: number) => void;
  labelClass: string;
  hintClass: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label htmlFor={id} className={`text-body-sm ${labelClass}`}>
          {label}
        </label>
        <span className={`tabular-nums text-body-sm ${hintClass}`}>
          {value}
          {unit}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full accent-[#F4D47A]"
      />
      {hint && <p className={`mt-0.5 text-body-sm ${hintClass}`}>{hint}</p>}
    </div>
  );
}
