import { useState, useEffect } from "react";
import { Link } from "react-router";
import { Flame, AlertCircle } from "lucide-react";
import { Spinner, StateBox, PageContainer, SectionLabel } from "./shared";

interface ArticleSnippet {
  snippet: string;
  url: string;
  source: string;
  title?: string;
}

interface TermOfDay {
  term: string;
  definition: string;
  category?: string;
  in_news: boolean;
  article_snippets?: ArticleSnippet[];
}

interface QuizOption {
  text: string;
  correct: boolean;
}

interface QuizQuestion {
  prompt: string;
  term: string;
  options: QuizOption[];
  explanation?: string;
  article_snippet?: ArticleSnippet;
}

interface QuizState {
  questions: QuizQuestion[];
  index: number;
  score: number;
  answers: Array<{
    prompt: string;
    term: string;
    correct: boolean;
    chosenIdx: number;
    chosen: string;
    actual: string;
  }>;
}

const STREAK_KEY = "politerate_streak";
const LAST_PLAY_KEY = "politerate_last_play";
const HIGH_SCORE_KEY = "politerate_high_score";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function loadStreak(): number {
  return parseInt(localStorage.getItem(STREAK_KEY) ?? "0", 10);
}

function bumpStreak(): number {
  const last = localStorage.getItem(LAST_PLAY_KEY);
  const today = todayStr();
  if (last === today) return loadStreak();
  let count = parseInt(localStorage.getItem(STREAK_KEY) ?? "0", 10);
  if (last) {
    const d = Math.round((new Date(today + "T00:00:00").getTime() - new Date(last + "T00:00:00").getTime()) / 86400000);
    count = d === 1 ? count + 1 : 1;
  } else {
    count = 1;
  }
  localStorage.setItem(STREAK_KEY, String(count));
  localStorage.setItem(LAST_PLAY_KEY, today);
  return count;
}

function TermOfDayCard({ term, loading }: { term: TermOfDay | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="bg-card border border-border rounded p-6 shadow-sm flex justify-center py-12">
        <Spinner />
      </div>
    );
  }
  // /api/term-of-day returns {} when the term pool is empty.
  if (!term?.term) {
    return (
      <div className="bg-card border border-border rounded p-6 shadow-sm">
        <SectionLabel>Term of the Day</SectionLabel>
        <p className="text-sm text-muted-foreground">
          Come back once today's news has loaded.
        </p>
      </div>
    );
  }
  return (
    <div className="bg-card border border-border rounded p-6 shadow-sm space-y-3">
      <SectionLabel>Term of the Day</SectionLabel>
      <div className="space-y-1">
        <h2
          className="tracking-tight"
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "1.9rem",
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
          }}
        >
          {term.term}
          {term.in_news && (
            <span
              className="ml-2 align-middle inline-flex px-2 py-0.5 rounded-full text-xs font-semibold"
              style={{ background: "var(--accent)", color: "#fff", fontSize: "0.7rem" }}
            >
              In today's news
            </span>
          )}
        </h2>
        {term.category && (
          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-secondary text-muted-foreground">
            {term.category}
          </span>
        )}
      </div>
      <p className="text-sm text-foreground leading-relaxed">{term.definition}</p>
      {term.article_snippets?.map((s, i) => (
        <blockquote
          key={i}
          className="border-l-2 pl-4 py-1 bg-secondary rounded-r text-sm italic text-foreground"
          style={{ borderLeftColor: "var(--accent)" }}
        >
          "{s.snippet}"
          <footer className="mt-1 text-xs text-muted-foreground not-italic">
            —{" "}
            <a
              href={s.url}
              target="_blank"
              rel="noopener"
              className="hover:underline"
              style={{ color: "var(--accent)" }}
            >
              {s.source}
            </a>
            {s.title && ` · ${s.title}`}
          </footer>
        </blockquote>
      ))}
    </div>
  );
}

function QuizCard({ streak, onStreak }: { streak: number; onStreak: (n: number) => void }) {
  const [state, setState] = useState<QuizState | null>(null);
  const [loading, setLoading] = useState(true);

  async function startQuiz() {
    setLoading(true);
    setState({ questions: [], index: 0, score: 0, answers: [] });
    try {
      const res = await fetch("/api/quiz?count=5");
      const data = await res.json();
      setState({ questions: data.questions ?? [], index: 0, score: 0, answers: [] });
    } catch {
      setState({ questions: [], index: 0, score: 0, answers: [] });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { startQuiz(); }, []);

  function handleAnswer(chosenIdx: number) {
    if (!state) return;
    const q = state.questions[state.index];
    const chosen = q.options[chosenIdx];
    const correctIdx = q.options.findIndex(o => o.correct);
    const correct = chosen.correct;
    setState(s => s ? {
      ...s,
      score: correct ? s.score + 1 : s.score,
      answers: [...s.answers, {
        prompt: q.prompt,
        term: q.term,
        correct,
        chosenIdx,
        chosen: chosen.text,
        actual: q.options[correctIdx].text,
      }],
    } : s);
  }

  function next() {
    if (!state) return;
    // Finishing a round counts toward the daily streak, regardless of score.
    if (state.index + 1 >= state.questions.length) onStreak(bumpStreak());
    setState(s => s ? { ...s, index: s.index + 1 } : s);
  }

  if (loading) {
    return (
      <div className="bg-card border border-border rounded p-6 shadow-sm flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (!state || state.questions.length === 0) {
    return (
      <div className="bg-card border border-border rounded p-6 shadow-sm">
        <SectionLabel>Quick Quiz</SectionLabel>
        <p className="text-sm text-muted-foreground">
          No quiz available yet. Try refreshing once today's news has loaded.
        </p>
      </div>
    );
  }

  const answered = state.answers.length > 0 && state.answers.length > state.index;
  const done = state.index >= state.questions.length;

  if (done) {
    const total = state.questions.length;
    const pct = total > 0 ? Math.round((state.score / total) * 100) : 0;
    const prevHigh = parseInt(localStorage.getItem(HIGH_SCORE_KEY) ?? "0", 10);
    if (pct > prevHigh) localStorage.setItem(HIGH_SCORE_KEY, String(pct));

    let message = "Keep going — every term you learn makes headlines easier to decode.";
    if (pct === 100) message = "Perfect score. You're fluent in political jargon.";
    else if (pct >= 80) message = "Strong work. A couple more rounds and you'll have this down.";
    else if (pct >= 50) message = "Solid start. Review the glossary and try again.";

    return (
      <div className="bg-card border border-border rounded p-6 sm:p-8 shadow-sm text-center space-y-4">
        <SectionLabel>Quick Quiz</SectionLabel>
        <div
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            fontSize: "3.5rem",
            lineHeight: 1,
            color: "var(--accent)",
            letterSpacing: "-0.02em",
          }}
        >
          {state.score}/{total}
        </div>
        <p className="text-sm text-muted-foreground">{message}</p>

        <div className="bg-secondary rounded p-4 text-left space-y-2">
          <SectionLabel>Recap</SectionLabel>
          <ul className="space-y-2">
            {state.answers.map((a, i) => (
              <li key={i} className="text-sm flex gap-2 items-start pb-2 border-b border-border last:border-0">
                <span
                  className="font-bold shrink-0 mt-0.5"
                  style={{ color: a.correct ? "#15803d" : "var(--destructive)" }}
                >
                  {a.correct ? "✓" : "✗"}
                </span>
                <span>
                  <strong>{a.term}</strong> —{" "}
                  {a.correct
                    ? "Correct"
                    : `You picked "${a.chosen.slice(0, 50)}…". Correct: "${a.actual.slice(0, 50)}…"`}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex justify-center gap-3 flex-wrap">
          <button
            onClick={startQuiz}
            className="px-5 py-2 bg-primary text-primary-foreground rounded text-sm font-semibold hover:opacity-90 transition-opacity"
          >
            Play again
          </button>
          <Link
            to="/glossary"
            className="px-5 py-2 bg-secondary text-secondary-foreground rounded text-sm font-medium hover:bg-muted transition-colors"
          >
            Browse glossary
          </Link>
        </div>
        <p
          className="text-xs text-muted-foreground"
          style={{ fontFamily: "var(--font-data)" }}
        >
          Day streak: {streak} · Best score: {Math.max(prevHigh, pct)}%
        </p>
      </div>
    );
  }

  const q = state.questions[state.index];
  const lastAnswer = answered ? state.answers[state.answers.length - 1] : null;
  const correctIdx = q.options.findIndex(o => o.correct);

  return (
    <div className="bg-card border border-border rounded p-6 shadow-sm space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <SectionLabel>Quick Quiz</SectionLabel>
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "1.15rem",
            }}
          >
            Test Your Political Literacy
          </h2>
        </div>
        <span
          className="shrink-0 px-3 py-1 rounded-full bg-secondary text-muted-foreground text-xs font-semibold"
          style={{ fontFamily: "var(--font-data)" }}
        >
          {state.index + 1}/{state.questions.length} · Score {state.score}
        </span>
      </div>

      {q.article_snippet && (
        <blockquote
          className="border-l-2 pl-4 py-1 bg-secondary rounded-r text-sm italic"
          style={{ borderLeftColor: "var(--accent)" }}
        >
          "{q.article_snippet.snippet}"
          <footer className="text-xs text-muted-foreground not-italic mt-1">
            —{" "}
            <a href={q.article_snippet.url} target="_blank" rel="noopener" className="hover:underline" style={{ color: "var(--accent)" }}>
              {q.article_snippet.source}
            </a>
          </footer>
        </blockquote>
      )}

      <p className="text-sm leading-relaxed whitespace-pre-line">{q.prompt}</p>

      <div className="space-y-2">
        {q.options.map((opt, i) => {
          let cls = "w-full text-left px-4 py-3 rounded border text-sm transition-colors ";
          if (!answered) {
            cls += "border-border bg-card hover:border-[var(--accent)] hover:bg-secondary";
          } else if (i === correctIdx) {
            cls += "border-green-400 bg-green-50 text-green-800 font-medium";
          } else if (lastAnswer && i === lastAnswer.chosenIdx) {
            cls += "border-destructive bg-red-50 text-red-800";
          } else {
            cls += "border-border bg-card opacity-50";
          }
          return (
            <button
              key={i}
              disabled={answered}
              onClick={() => handleAnswer(i)}
              className={cls}
            >
              {opt.text}
            </button>
          );
        })}
      </div>

      {answered && lastAnswer && (
        <div className="p-4 bg-secondary rounded text-sm">
          <strong style={{ color: lastAnswer.correct ? "#15803d" : "var(--destructive)" }}>
            {lastAnswer.correct ? "Correct!" : "Not quite."}
          </strong>{" "}
          {q.explanation ?? ""}
        </div>
      )}

      {answered && (
        <div className="flex justify-end">
          <button
            onClick={next}
            className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm font-semibold hover:opacity-90 transition-opacity"
          >
            {state.index === state.questions.length - 1 ? "See results →" : "Next question →"}
          </button>
        </div>
      )}
    </div>
  );
}

export function LearnPage() {
  const [term, setTerm] = useState<TermOfDay | null>(null);
  const [termLoading, setTermLoading] = useState(true);
  const [streak, setStreak] = useState(loadStreak());

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/term-of-day");
        setTerm(await res.json());
      } catch {
        setTerm(null);
      } finally {
        setTermLoading(false);
      }
    })();
  }, []);

  return (
    <PageContainer narrow>
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-8 pb-6 border-b border-border flex-wrap">
        <div>
          <h1
            style={{
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: "2rem",
              lineHeight: 1.15,
            }}
          >
            Learn Political Literacy
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">Grounded in today's headlines.</p>
        </div>
        <span
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary border border-border text-sm font-semibold"
          style={{ color: "var(--accent)" }}
        >
          <Flame size={14} />
          {streak}-day streak
        </span>
      </div>

      <div className="space-y-6">
        <TermOfDayCard term={term} loading={termLoading} />
        <QuizCard streak={streak} onStreak={setStreak} />
      </div>
    </PageContainer>
  );
}
