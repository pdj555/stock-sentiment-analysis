import {
  evidenceDirectionLabel,
  evidenceGradeLabel,
  formatConfidence,
  SIGNAL_COPY,
} from "@/lib/format";
import type { EvidenceProfile, Signal } from "@/lib/types";

interface EvidenceBriefProps {
  evidence: EvidenceProfile;
  signal: Signal;
}

export default function EvidenceBrief({ evidence, signal }: EvidenceBriefProps) {
  return (
    <section className="evidence-brief nous-panel" aria-labelledby="evidence-title">
      <header className="evidence-head">
        <div>
          <span className="panel-legend">Decision brief</span>
          <h3 id="evidence-title">{SIGNAL_COPY[signal].word}</h3>
          <p>{SIGNAL_COPY[signal].line}</p>
        </div>
        <span className={`evidence-grade grade-${evidence.grade}`}>
          {evidenceGradeLabel(evidence.grade)} evidence
        </span>
      </header>
      <dl className="evidence-metrics">
        <div>
          <dt>Coverage</dt>
          <dd>{formatConfidence(evidence.coverage)}</dd>
        </div>
        <div>
          <dt>Agreement</dt>
          <dd>{formatConfidence(evidence.agreement)}</dd>
        </div>
        <div>
          <dt>Classified</dt>
          <dd>
            {evidence.classified_articles}/{evidence.total_articles}
          </dd>
        </div>
      </dl>
      {evidence.drivers.length > 0 && (
        <div className="evidence-driver-wrap">
          <h4>Key drivers</h4>
          <ol className="evidence-drivers">
            {evidence.drivers.map((driver) => (
              <li key={driver.article_id} className={`driver-${driver.direction}`}>
                <span className="driver-direction">
                  {evidenceDirectionLabel(driver.direction)}
                </span>
                <div>
                  <h5>
                    {driver.url ? (
                      <a href={driver.url} target="_blank" rel="noreferrer noopener">
                        {driver.title}
                      </a>
                    ) : (
                      driver.title
                    )}
                  </h5>
                  <p>{[driver.source, driver.reason].filter(Boolean).join(" · ")}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
