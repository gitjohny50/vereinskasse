import { useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "../api";
import type { Tab } from "../App";
import { STEPS, type TourStep } from "./TutorialData";

type Rect = { top: number; left: number; width: number; height: number };

export function Tutorial({
  session,
  open,
  onClose,
  onTabChange,
}: {
  session: Session;
  open: boolean;
  onClose: (gesehen: boolean) => void;
  onTabChange: (tab: Tab) => void;
}) {
  const steps = useMemo(() => STEPS.filter((s) => !s.minStufe || session.stufe >= s.minStufe), [session.stufe]);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);

  const step = steps[index] ?? steps[0];

  const findTarget = useCallback((tourStep: TourStep) => {
    if (!tourStep.anchor) return null;
    return document.querySelector<HTMLElement>(`[data-tour="${tourStep.anchor}"]`);
  }, []);

  const syncRect = useCallback(() => {
    const el = findTarget(step);
    if (!el) {
      setRect(null);
      return;
    }
    el.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    const next = el.getBoundingClientRect();
    setRect({ top: next.top, left: next.left, width: next.width, height: next.height });
  }, [findTarget, step]);

  const goToUsableStep = useCallback((start: number, dir: 1 | -1) => {
    let next = start;
    while (next >= 0 && next < steps.length) {
      const candidate = steps[next];
      if (!candidate.tab) {
        if (!candidate.anchor || findTarget(candidate)) return next;
      } else {
        onTabChange(candidate.tab);
        return next;
      }
      next += dir;
    }
    return Math.max(0, Math.min(steps.length - 1, start));
  }, [findTarget, onTabChange, steps]);

  useEffect(() => {
    if (!open) return;
    setIndex(0);
  }, [open]);

  useEffect(() => {
    if (!open || !step) return;
    if (step.tab) onTabChange(step.tab);
    const timeout = window.setTimeout(() => {
      syncRect();
      if (step.anchor && !findTarget(step)) setIndex((cur) => goToUsableStep(cur + 1, 1));
    }, 220);
    window.addEventListener("resize", syncRect);
    window.addEventListener("scroll", syncRect, true);
    return () => {
      window.clearTimeout(timeout);
      window.removeEventListener("resize", syncRect);
      window.removeEventListener("scroll", syncRect, true);
    };
  }, [findTarget, goToUsableStep, onTabChange, open, step, syncRect]);

  useEffect(() => {
    if (!open || !step?.anchor || step.tab) return;
    if (!findTarget(step)) setIndex((cur) => goToUsableStep(cur + 1, 1));
  }, [findTarget, goToUsableStep, open, step]);

  if (!open) return null;

  const isWelcome = index === 0;
  const isFinish = index === steps.length - 1;
  const progress = Math.round(((index + 1) / steps.length) * 100);
  const cardStyle = popoverStyle(rect);

  return (
    <div className="tutorial-layer" data-has-target={rect ? "true" : "false"} role="dialog" aria-modal="true" aria-label="Tutorial">
      <div className="tutorial-dim" />
      {rect && (
        <div
          className="tutorial-spotlight"
          style={{
            top: rect.top - 8,
            left: rect.left - 8,
            width: rect.width + 16,
            height: rect.height + 16,
          }}
        />
      )}
      <div className={`tutorial-card ${rect ? "tutorial-popover" : "tutorial-center"}`} style={cardStyle}>
        <div className="tutorial-progress" aria-hidden="true"><span style={{ width: `${progress}%` }} /></div>
        <div className="eyebrow">Schritt {index + 1} von {steps.length}</div>
        <h2>{step.title}</h2>
        <p>{step.text}</p>
        <div className="tutorial-actions">
          {!isWelcome && !isFinish && (
            <button type="button" className="btn" onClick={() => setIndex((cur) => goToUsableStep(cur - 1, -1))}>Zurück</button>
          )}
          <button type="button" className="btn" onClick={() => onClose(true)}>Überspringen</button>
          {isFinish ? (
            <button type="button" className="btn btn-primary" onClick={() => onClose(true)}>Fertig</button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={() => setIndex((cur) => goToUsableStep(cur + 1, 1))}>
              {isWelcome ? "Los geht's" : "Weiter"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function popoverStyle(rect: Rect | null) {
  if (!rect) return undefined;
  const width = Math.min(420, window.innerWidth - 32);
  const left = Math.max(16, Math.min(window.innerWidth - width - 16, rect.left + rect.width / 2 - width / 2));
  const below = rect.top + rect.height + 18;
  const top = below + 260 < window.innerHeight ? below : Math.max(16, rect.top - 278);
  return { width, left, top };
}