import { Link, useLocation } from "react-router-dom";
import { faCircleQuestion } from "@fortawesome/free-solid-svg-icons";
import { Button, Container, PageState } from "../components/ui";

/**
 * A real 404. Unknown routes used to be redirected to the landing page,
 * which made a mistyped link indistinguishable from being signed out.
 * This states what happened, shows the address that failed, and offers the
 * two places worth going next.
 */
export default function NotFound() {
  const location = useLocation();

  return (
    <Container width="reading" className="px-5 sm:px-8">
      <PageState
        tone="neutral"
        icon={faCircleQuestion}
        eyebrow="Error 404"
        title="Page not found"
        description="The address may be mistyped, or it may point to something that has been moved or removed from the repository."
        actions={
          <>
            <Button as={Link} to="/projects" variant="primary" size="sm">
              Browse projects
            </Button>
            <Button as={Link} to="/dashboard" variant="secondary" size="sm">
              Go to home
            </Button>
          </>
        }
      >
        <p className="mt-5 w-full break-all border-y border-line bg-band px-4 py-2 text-xs text-ink-3 tnum">
          {location.pathname}
          {location.search}
        </p>
      </PageState>
    </Container>
  );
}
