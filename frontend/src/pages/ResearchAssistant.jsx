import { Link } from "react-router-dom";
import { faFlask } from "@fortawesome/free-solid-svg-icons";
import {
  Breadcrumb,
  Button,
  Container,
  Crumb,
  PageState,
} from "../components/ui";

/**
 * Research assistant — a placeholder, and nothing more.
 *
 * There is no assistant behind this route: no model call, no retrieval, no
 * conversation store. So this page has no chat interface, no example
 * exchange, and no disabled input box implying one nearly works. It says
 * what is planned and points at the search that does exist.
 */
export default function ResearchAssistant() {
  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb last>Research assistant</Crumb>
      </Breadcrumb>

      <Container width="reading" className="px-5 sm:px-8">
        <PageState
          tone="neutral"
          icon={faFlask}
          eyebrow="Planned feature"
          title="Research assistant"
          description="A way to ask questions of the repository in plain language. It has not been built yet, and there is nothing here to try."
          actions={
            <Button as={Link} to="/projects" variant="primary" size="sm">
              Search projects instead
            </Button>
          }
        >
          <p className="mt-4 max-w-md text-sm text-ink-2">
            Catalogue search already matches your words against project titles, abstracts,
            authors, supervisors, keywords and departments.
          </p>
        </PageState>
      </Container>
    </>
  );
}
