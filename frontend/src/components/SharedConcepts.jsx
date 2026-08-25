/**
 * Why a project was recommended.
 *
 * Every surface that recommends a project renders this, so the explanation
 * reads the same way whether it appears under a Similar Projects card or a
 * Similar Work Check result.
 *
 * What it replaces
 * ----------------
 * A band ("High similarity", "Related work exists") and a percentile ("More
 * similar than 98% of project pairs"). Both described the strength of a
 * number rather than the relationship, and the percentile in particular reads
 * as a percentage of shared content, which is not what it measures. Neither
 * told a student anything they could act on.
 *
 * The terms here are the subject matter the two pieces of work actually have
 * in common, taken from the projects' own titles and keywords. Nothing is
 * inferred and nothing is generated.
 *
 * Silence is deliberate
 * ---------------------
 * The server sends an empty list when the repository does not hold enough
 * recorded subject matter to explain a pairing in a few words, which happens
 * for roughly a quarter of recommendations. This renders nothing at all in
 * that case. The recommendation still stands on the similarity that produced
 * it; what would be wrong is to manufacture a reason for it.
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
