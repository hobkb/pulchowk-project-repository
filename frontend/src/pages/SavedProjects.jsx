import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { faBookmark } from "@fortawesome/free-regular-svg-icons";
import { bookmarksApi } from "../api/client";
import { ProjectRecord } from "../components/ProjectRecord";
import {
  Breadcrumb,
  Button,
  Container,
  Crumb,
  EmptyState,
  Pagination,
  ErrorNotice,
  LoadingRows,
  PageHeading,
} from "../components/ui";

/**
 * Saved projects — the signed-in user's bookmarks.
 *
 * Backed by the repository bookmarks API, which is scoped to the
 * requesting user. A project that has since been unpublished drops out of
 * the list rather than appearing and then failing to open.
 */
export default function SavedProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    bookmarksApi
      .list({ page })
      .then((body) => {
        if (cancelled) return;
        setProjects(body.data || []);
        setPagination(body.pagination || null);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page]);

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb last>Saved projects</Crumb>
      </Breadcrumb>

      <Container width="normal" className="px-5 sm:px-8 py-8">
        <PageHeading
          title="Saved projects"
        />

        <div className="mt-6">
          {loading && <LoadingRows rows={3} />}

          {!loading && error && (
            <ErrorNotice title="Saved projects could not be loaded" detail={error} />
          )}

          {!loading && !error && projects.length === 0 && (
            <EmptyState
              icon={faBookmark}
              title="Nothing saved yet"
              description="Use Save on any project record to keep it here."
              action={
                <Button as={Link} to="/projects" variant="secondary" size="sm">
                  Browse projects
                </Button>
              }
            />
          )}

          {!loading && !error && projects.length > 0 && (
            <div className="border-t border-line">
              {projects.map((project) => (
                <ProjectRecord key={project.id} project={project} />
              ))}
            </div>
          )}

          {!loading && !error && pagination && (
            <Pagination
              page={pagination.page}
              totalPages={pagination.total_pages}
              totalCount={pagination.total_count}
              label="saved"
              onChange={(next) => {
                setPage(next);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            />
          )}
        </div>
      </Container>
    </>
  );
}
