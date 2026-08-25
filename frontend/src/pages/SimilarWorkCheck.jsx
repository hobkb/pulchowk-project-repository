import { useState } from "react";
import { Link } from "react-router-dom";
import { similarityApi } from "../api/client";
import SharedConcepts from "../components/SharedConcepts";
import {
  Alert,
  Breadcrumb,
  Button,
  Container,
  Crumb,
  ErrorNotice,
  Input,
  SectionHeading,
  Status,
  Textarea,
} from "../components/ui";

/**
 * Similar Work Check.
 *
 * A reader describes an idea they are considering, and the repository reports
 * whether anything close to it already exists.
 *
 * Concept first
 * -------------
 * The only input that matters is a plain description of the idea. The earlier
 * version demanded a title, an abstract and a keyword list, which meant
 * writing most of a proposal before you could ask whether the idea already
 * existed. A title and a fuller description remain, behind a disclosure, for
 * someone who happens to have them.
 *
 * What this is careful not to claim
 * ---------------------------------
 * The comparison is between sentence embeddings, which measure conceptual
 * closeness. That cannot establish copying, so nothing here says "duplicate"
 * or "plagiarised", and no verdict is stronger than that related work exists
 * and a person should read it.
 *
 * Work above the calibrated threshold is listed as related. Below it, at most
 * one project is offered, and only when it stands clear of the rest of the
 * corpus rather than merely being the nearest thing to hand; it is put under
 * its own heading and labelled as possible. The earlier version listed the
 * five nearest neighbours whatever their scores, which put four unrelated
 * projects on screen beside the one real match.
 *
 * No number reaches the reader
 * ----------------------------
 * Not the cosine, and not the percentile that used to sit under each row.
 * Two entirely unrelated projects in this corpus score around 0.64, so the
 * raw value means nothing without its context, and "more similar than 98% of
 * project pairs" reads as a percentage of shared content when it is nothing
 * of the kind. Each result instead carries the subject matter it actually
 * shares with the idea, or nothing at all where the repository holds too
 * little to say.
 */

/**
 * The three outcomes a check can have. Deliberately no finer than this: the
 * previous version keyed off a four-rung band ladder whose labels ("Very high
 * overlap", "High similarity") described how large a cosine was and edged
 * towards a claim about duplication that the measurement cannot support.
 */
function Verdict({ result }) {
  const hasStrong = result.strong.length > 0;
  const hasPossible = result.possible.length > 0;

  const tone = hasStrong ? "warning" : hasPossible ? "neutral" : "success";
  const heading = hasStrong
    ? "Related work already exists"
    : hasPossible
      ? "One project may be related"
      : "No related work found";
  const explanation = hasStrong
    ? "The repository already holds work on this subject. That is not a finding of copying; it means you and your supervisor should read it before the scope is fixed, so the project builds on it rather than repeats it."
    : hasPossible
      ? "Nothing clearly related was found. One project stands out from the rest of the repository by enough of a margin to be worth opening, but it sits below the threshold for related work."
      : "Nothing in the repository is close enough to count as related work. That is a statement about this repository only, not about the field, and not a guarantee that the idea is original.";

  return (
    <div className="mt-6 border border-line bg-white p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Status tone={tone}>{heading}</Status>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink-2">{explanation}</p>
    </div>
  );
}

function MatchRow({ entry, explain = true }) {
  const project = entry.project;
  return (
    <li className="border-b border-line py-4">
      <div className="flex flex-wrap items-center gap-2">
        {project.project_type && (
          <span className="text-xs text-ink-3">{project.project_type}</span>
        )}
        {project.department && (
          <span className="text-xs text-ink-3">{project.department}</span>
        )}
      </div>
      <h3 className="mt-2 text-item">
        <Link to={`/projects/${project.id}`} className="text-link hover:text-link-hover">
          {project.title}
        </Link>
      </h3>
      {explain && (
        <SharedConcepts terms={entry.shared_concepts} className="mt-1.5" />
      )}
    </li>
  );
}

export default function SimilarWorkCheck() {
  const [concept, setConcept] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);

  const canSubmit = concept.trim().length > 0 || title.trim().length > 0;

  async function submit(event) {
    event.preventDefault();
    if (checking || !canSubmit) return;
    setChecking(true);
    setError(null);
    setResult(null);
    try {
      const body = await similarityApi.check({
        concept: concept.trim(),
        title: title.trim(),
        description: description.trim(),
      });
      setResult(body.data);
    } catch (err) {
      setError(err.message || "The check could not be completed.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb last>Similar work check</Crumb>
      </Breadcrumb>

      <Container width="wide" className="px-5 sm:px-8 py-8">
        <h1 className="text-title">Similar work check</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-2">
          Describe an idea you are considering and see whether the repository
          already holds closely related work. A sentence or two is enough. The
          comparison is conceptual, so it finds work on the same subject even
          when the wording is entirely different, and it cannot tell you
          whether anything was copied.
        </p>

        <form onSubmit={submit} className="mt-6 max-w-2xl flex flex-col gap-4">
          <Textarea
            id="swc-concept"
            label="Project idea"
            rows={5}
            value={concept}
            onChange={(event) => setConcept(event.target.value)}
            placeholder="For example: an app that tracks daily calorie intake and recommends meals according to a user's nutritional goals."
            hint="Plain language is fine. You do not need a title or an abstract."
          />

          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced((open) => !open)}
              className="text-sm text-link hover:text-link-hover cursor-pointer"
            >
              {showAdvanced ? "Hide" : "Add"} a title or fuller description (optional)
            </button>
          </div>

          {showAdvanced && (
            <div className="flex flex-col gap-4 border-l-2 border-line pl-4">
              <Input
                id="swc-title"
                label="Working title (optional)"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="If you already have one"
              />
              <Textarea
                id="swc-description"
                label="Fuller description (optional)"
                rows={5}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Any further detail: the approach, the data, the intended outcome."
              />
            </div>
          )}

          <div>
            <Button type="submit" variant="primary" disabled={checking || !canSubmit}>
              {checking ? "Checking…" : "Check the repository"}
            </Button>
          </div>
        </form>

        {error && (
          <div className="mt-6 max-w-2xl">
            <ErrorNotice title="The check did not run" detail={error} />
          </div>
        )}

        {result && (
          <div className="mt-8 max-w-3xl">
            <Verdict result={result} />

            {result.strong.length > 0 && (
              <section className="mt-8">
                <SectionHeading title="Related work you should review" />
                <ul className="mt-2">
                  {result.strong.map((entry) => (
                    <MatchRow key={entry.project.id} entry={entry} />
                  ))}
                </ul>
              </section>
            )}

            {result.possible.length > 0 && (
              <section className="mt-8">
                <SectionHeading title="Possibly related" />
                <p className="mt-2 text-sm leading-relaxed text-ink-2">
                  Below the threshold for related work, but far enough ahead of
                  everything else in the repository to be worth opening. Judge
                  it yourself rather than treating it as a match.
                </p>
                <ul className="mt-2">
                  {result.possible.map((entry) => (
                    <MatchRow key={entry.project.id} entry={entry} />
                  ))}
                </ul>
              </section>
            )}

            {result.strong.length === 0 &&
              result.possible.length === 0 &&
              (result.closest_below_threshold ? (
                <section className="mt-8">
                  <SectionHeading title="Closest candidate" />
                  <p className="mt-2 text-sm leading-relaxed text-ink-2">
                    This is the nearest project in the repository. It scores no
                    better against your idea than the rest of the corpus does,
                    so it is shown for context rather than as a match.
                  </p>
                  <ul className="mt-2">
                    <MatchRow entry={result.closest_below_threshold} explain={false} />
                  </ul>
                </section>
              ) : (
                <div className="mt-8">
                  <Alert>
                    Nothing in the repository could be compared. This happens
                    when no projects have been indexed yet.
                  </Alert>
                </div>
              ))}

            <p className="mt-6 text-xs leading-relaxed text-ink-3">
              Similarity here is measured between meanings, not between
              sentences. It is a prompt to read the projects listed above and
              decide for yourself, not a judgement about originality.
            </p>
          </div>
        )}
      </Container>
    </>
  );
}
