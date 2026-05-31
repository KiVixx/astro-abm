const legendItems = [
  ["agent", "Agent group"],
  ["astro", "Astro context"],
  ["market", "Market context"],
  ["asset", "Asset"],
  ["risk", "Risk theme"],
  ["data", "Data quality"],
];

export function GraphLegend() {
  return (
    <div className="workbench-legend" aria-label="Graph legend">
      {legendItems.map(([kind, label]) => (
        <span className="workbench-legend-item" key={kind}>
          <span className={`legend-dot legend-dot-${kind}`} />
          {label}
        </span>
      ))}
      <span className="muted">
        Scenario visualization only; not a causal graph or trading signal.
      </span>
    </div>
  );
}

