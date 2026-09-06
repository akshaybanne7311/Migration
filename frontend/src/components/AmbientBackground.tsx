import { createPortal } from "react-dom";

/**
 * A purely ambient, autonomous background -- a slowly drifting grid plus a
 * couple of soft glow orbs on independent looping paths. Unlike the cursor
 * glow it replaces, nothing here reacts to input; it's meant to sit behind
 * all real content and just feel alive, sci-fi HUD style. Portaled to
 * document.body (not nested under any ancestor) for the same reason the
 * cursor glow was: a `transform` on some unrelated parent can otherwise
 * hijack a `position: fixed` descendant's containing block.
 */
export function AmbientBackground() {
  return createPortal(
    <div className="ambient-bg" aria-hidden="true">
      <div className="ambient-grid" />
      <div className="ambient-orb ambient-orb-1" />
      <div className="ambient-orb ambient-orb-2" />
      <div className="ambient-orbit ambient-orbit-1">
        <span className="ambient-orbit-dot" />
      </div>
      <div className="ambient-orbit ambient-orbit-2">
        <span className="ambient-orbit-dot" />
      </div>
    </div>,
    document.body,
  );
}
