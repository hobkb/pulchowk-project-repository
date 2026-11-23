/**
 * Why a project was recommended, shown wherever one is.
 *
 * Replaces a band ("High similarity") and a percentile ("More similar than
 * 98% of project pairs"), both of which described the size of a number rather
 * than the relationship. The terms are subject matter the two pieces of work
 * share, taken from their own titles and keywords.
 *
 * Renders nothing when the server sends an empty list, which happens when the
 * repository holds too little recorded subject matter to explain a pairing.
 */
export default function SharedConcepts({ terms, className = "" }) {
  if (!terms || terms.length === 0) return null;

  return (
    <p className={`text-xs leading-relaxed text-ink-3 ${className}`}>
      <span className="text-ink-2">Similar because:</span>{" "}
      {terms.map((term, index) => (
        <span key={term}>
          {index > 0 && <span aria-hidden="true"> · </span>}
          <span className="text-ink-2">{term}</span>
        </span>
      ))}
    </p>
  );
}
