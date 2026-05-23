"use client";

export default function Nav() {
  return (
    <header className="nav">
      <div className="nav-bar">
        <div className="nav-left">
          <span className="nav-meta">lookback: 3d</span>
          <span className="nav-meta-sep" aria-hidden>
            ·
          </span>
          <span className="nav-meta">news + rss</span>
        </div>
        <a href="/" className="nav-center" aria-label="Sentiment home">
          Sentiment
        </a>
        <div className="nav-right">
          <span className="nav-tag">research preview</span>
        </div>
      </div>
    </header>
  );
}
