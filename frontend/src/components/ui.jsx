/**
 * The design system's public surface. Pages import from here so the
 * vocabulary stays small and visible in one place.
 *
 * The trailing block are compatibility aliases kept so the large,
 * behaviourally load-bearing ingestion pages keep working while the
 * things behind those names were replaced outright.
 */
export {
  // Actions and forms
  Button,
  Input,
  Select,
  Textarea,
  FieldLabel,
  SearchField,
  // Surfaces
  Card,
  CardHeader,
  SectionHeading,
  Container,
  PageHeading,
  // Status and metadata
  Status,
  statusRowAccent,
  Count,
  Term,
  Meta,
  TONE,
  // Feedback
  Alert,
  ErrorNotice,
  EmptyState,
  PageState,
  LoadingRows,
  // Navigation
  Breadcrumb,
  Crumb,
  Pagination,
  // Tables
  Table,
  TableHead,
  TableBody,
  Th,
  Td,
  Tr,
  // Aliases retained for the ingestion pages
  StatusTag,
  StatusMark,
  StatusSplash,
  EmptyNotice,
  LoadingLines,
  MetaEntry,
  IndexTerm,
  PageColumn,
  PageMasthead,
  SectionHead,
  Sheet,
  Eyebrow,
  Prose,
} from "./ui/primitives";

export { Dialog, Dialog as Modal } from "./ui/Dialog";
