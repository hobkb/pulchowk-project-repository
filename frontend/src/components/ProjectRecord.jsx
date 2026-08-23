import { Link } from "react-router-dom";
import { Term } from "./ui";

/**
 * One project in a result list.
 *
 * A catalogue record, not a product tile: the title is the link and the
 * strongest element, the responsibility statement (authors, supervisor)
 * sits directly beneath it, then a short abstract extract, then the
 * classification data as a single quiet line. Rows are separated by a
 * 1px rule only — no card, no shadow, no thumbnail, no price-tag layout.
 */

/** "078" -> "2078". The stored admission code is what filters use; the
 *  year is what readers recognise. */
function batchYear(code) {
  const text = String(code ?? "").trim();
  return /^\d{3}$/.test(text) ? `20${text.slice(-2)}` : text;
}

function names(people, limit = 4) {
  const list = (people || []).map((p) => p.name).filter(Boolean);
  if (!list.length) return null;
  if (list.length <= limit) return list.join(", ");
  return `${list.slice(0, limit).join(", ")} and ${list.length - limit} more`;
}

export function ProjectRecord({ project, showAbstract = true }) {
  const authors = names(project.authors);
  const supervisors = (project.supervisors || []).filter(Boolean);
  const keywords = (project.keywords || project.technologies || []).filter(Boolean);

  const facts = [
    project.department,
    project.academic_level,
    (project.batch || project.year) && `Batch ${batchYear(project.batch || project.year)}`,
    project.project_type,
  ].filter(Boolean);

  return (
    <article className="border-b border-line py-5">
      <h3 className="text-item">
        <Link to={`/projects/${project.id}`} className="text-link hover:text-link-hover">
          {project.title}
        </Link>
      </h3>

      <div className="mt-1.5 space-y-0.5">
        {authors && (
          <p className="text-sm text-ink-2">
            <span className="text-ink-3">Authors: </span>
            {authors}
          </p>
        )}
        <p className="text-sm text-ink-2">
          <span className="text-ink-3">
            {supervisors.length > 1 ? "Supervisors: " : "Supervisor: "}
          </span>
          {supervisors.length > 0 ? (
            supervisors.join("; ")
          ) : (
            // Never invented, and never silently dropped — an absent
            // supervisor is stated as absent.
            <span className="text-ink-3 italic">Not available</span>
          )}
        </p>
      </div>

      {showAbstract && project.abstract && (
        <p className="mt-2 text-sm text-ink-2 line-clamp-2 measure">{project.abstract}</p>
      )}

      {facts.length > 0 && (
        <p className="mt-2 text-xs text-ink-3">
          {facts.map((fact, index) => (
            <span key={`${fact}-${index}`}>
              {index > 0 && <span aria-hidden="true" className="px-1.5">·</span>}
              <span className={fact?.toString().startsWith("Batch") ? "tnum" : undefined}>{fact}</span>
            </span>
          ))}
        </p>
      )}

      {keywords.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {keywords.slice(0, 6).map((keyword) => (
            <Term key={keyword}>{keyword}</Term>
          ))}
          {keywords.length > 6 && (
            <span className="self-center text-xs text-ink-3">+{keywords.length - 6} more</span>
          )}
        </div>
      )}
    </article>
  );
}
