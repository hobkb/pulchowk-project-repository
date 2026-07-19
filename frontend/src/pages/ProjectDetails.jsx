import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { getProjectById, mockProjects } from "../api/mockProjects";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { 
  faEnvelope, 
  faQuoteLeft, 
  faShareNodes, 
  faDownload, 
  faCheck, 
  faXmark, 
  faUser, 
  faFileLines, 
  faCode, 
  faArrowUpRightFromSquare, 
  faChevronRight, 
  faCircleInfo, 
  faCheckCircle, 
  faCircleXmark, 
  faCopy 
} from "@fortawesome/free-solid-svg-icons";

export default function ProjectDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [project, setProject] = useState(null);
  const [similarProjects, setSimilarProjects] = useState([]);
  const [loadingSimilar, setLoadingSimilar] = useState(true);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isCiteOpen, setIsCiteOpen] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);
  const [copiedCitation, setCopiedCitation] = useState(false);
  
  // Custom states for admin reviews
  const [reviewStatus, setReviewStatus] = useState(null);

  useEffect(() => {
    const proj = getProjectById(id);
    if (!proj) {
      navigate("/dashboard");
      return;
    }
    setProject(proj);
    setReviewStatus(proj.status);
    setIsCiteOpen(false);
    
    // Simulate loading similar projects rail
    setLoadingSimilar(true);
    const timer = setTimeout(() => {
      const filtered = mockProjects.filter((p) => p.id !== id).slice(0, 2);
      setSimilarProjects(filtered);
      setLoadingSimilar(false);
    }, 600);

    return () => clearTimeout(timer);
  }, [id, navigate]);

  if (!project) return null;

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopiedShare(true);
    setTimeout(() => setCopiedShare(false), 2000);
  };

  const bibtex = `@thesis{pulchowk_${project.id},
  title = {${project.title}},
  author = {${project.authors.map(a => a.name).join(' and ')}},
  school = {Institute of Engineering, Pulchowk Campus},
  year = {${project.year}},
  department = {${project.department}}
}`;

  const handleCopyCitation = () => {
    navigator.clipboard.writeText(bibtex);
    setCopiedCitation(true);
    setTimeout(() => setCopiedCitation(false), 2000);
  };

  const handleApprove = () => {
    setReviewStatus("approved");
    // Show success alert/toast locally
  };

  const handleReject = () => {
    setReviewStatus("rejected");
  };

  // Generate mailto link
  const validAuthorsWithEmails = project.authors.filter(a => a.email);
  const mailtoEmails = validAuthorsWithEmails.map(a => a.email).join(",");
  const mailtoSubject = encodeURIComponent(`[Pulchowk Repository] Request for Project Report: ${project.title}`);
  const mailtoBody = encodeURIComponent(
    `Dear Authors,\n\nI am interested in your project titled "${project.title}" and would like to request a copy of the final project report PDF for academic reference.\n\nThank you!\n\nName:\nDepartment:\nRoll Number:`
  );
  const mailtoLink = `mailto:${mailtoEmails}?subject=${mailtoSubject}&body=${mailtoBody}`;

  return (
    <div className="flex flex-col gap-6">
      
      {/* Breadcrumb Navigation per Chapter 17.1 */}
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary">
        <Link to="/dashboard" className="hover:text-text-secondary transition-colors">
          Browse Projects
        </Link>
        <FontAwesomeIcon icon={faChevronRight} className="h-3.5 w-3.5 text-text-tertiary/60" />
        <span className="font-mono">{project.department}</span>
        <FontAwesomeIcon icon={faChevronRight} className="h-3.5 w-3.5 text-text-tertiary/60" />
        <span className="text-text-secondary truncate max-w-[200px] sm:max-w-xs">{project.title}</span>
      </nav>

      {/* Admin review toolbar per Chapter 21 */}
      {isAdmin && reviewStatus === "pending" && (
        <div className="bg-warning-amber/10 border border-warning-amber/20 rounded-md p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-2.5">
            <FontAwesomeIcon icon={faCircleInfo} className="h-5 w-5 text-warning-amber shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-text-primary">Project Pending Approval</p>
              <p className="text-[11px] text-text-secondary mt-0.5">
                This project has been submitted and is awaiting administrative approval before it appears in public catalog searches.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleApprove}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-success-emerald text-text-inverse hover:bg-success-emerald/90 text-xs font-semibold rounded-sm transition-colors cursor-pointer"
            >
              <FontAwesomeIcon icon={faCheck} className="h-3.5 w-3.5" /> Approve
            </button>
            <button
              onClick={handleReject}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-error-red text-text-primary hover:bg-error-red/90 text-xs font-semibold rounded-sm transition-colors cursor-pointer"
            >
              <FontAwesomeIcon icon={faXmark} className="h-3.5 w-3.5" /> Reject
            </button>
          </div>
        </div>
      )}

      {/* Main Grid Layout: left 2 columns, right 1 column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Side: Title, Info, Abstract, Preview, Similar Projects */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          
          {/* Header Title Section */}
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="bg-surface-raised border border-border-default px-2 py-0.5 rounded-sm text-xs font-mono text-text-secondary">
                {project.year}
              </span>
              <span className="bg-surface-raised border border-border-default px-2 py-0.5 rounded-sm text-xs font-mono text-text-secondary">
                {project.cluster}
              </span>
              <span className={`border px-2 py-0.5 rounded-sm text-xs font-mono capitalize ${
                reviewStatus === "approved"
                  ? "bg-success-emerald/10 border-success-emerald/20 text-success-emerald"
                  : reviewStatus === "pending"
                  ? "bg-warning-amber/10 border-warning-amber/20 text-warning-amber"
                  : "bg-error-red/10 border-error-red/20 text-error-red"
              }`}>
                {reviewStatus}
              </span>
            </div>

            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary leading-tight">
              {project.title}
            </h1>

            {/* Author list under title */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-text-secondary">
              <div className="flex items-center gap-1">
                <span className="font-semibold text-text-primary">Authors:</span>
                {project.authors.map((a, idx) => (
                  <span key={a.rollNumber}>
                    {a.name} <span className="font-mono text-text-tertiary text-[10px]">({a.rollNumber})</span>
                    {idx < project.authors.length - 1 ? ", " : ""}
                  </span>
                ))}
              </div>
              <div>•</div>
              <div>
                <span className="font-semibold text-text-primary">Supervisor:</span> {project.supervisor}
              </div>
            </div>
          </div>

          {/* Abstract Block */}
          <div className="bg-surface-raised border border-border-subtle rounded-md p-6 flex flex-col gap-4">
            <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Abstract</h2>
            <p className="text-sm text-text-secondary leading-relaxed max-w-prose whitespace-pre-line">
              {project.abstract}
            </p>
          </div>

          {/* Results Block */}
          {project.resultsSummary && (
            <div className="bg-surface-raised border border-border-subtle rounded-md p-6 flex flex-col gap-4">
              <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Key Findings & Results</h2>
              <div className="text-sm text-text-secondary leading-relaxed space-y-2">
                {project.resultsSummary.split('\n').map((line, idx) => (
                  <p key={idx} className="pl-4 border-l border-accent-primary/40">{line}</p>
                ))}
              </div>
            </div>
          )}

          {/* PDF Viewer Area - Gated by Role per Chapter 17.5 */}
          <div className="bg-surface-raised border border-border-subtle rounded-md overflow-hidden flex flex-col">
            <div className="border-b border-border-subtle px-6 py-4 flex items-center justify-between bg-surface-raised/60">
              <div className="flex items-center gap-2">
                <FontAwesomeIcon icon={faFileLines} className="h-4 w-4 text-accent-primary" />
                <span className="text-xs font-semibold text-text-primary uppercase tracking-wider">Project Document Preview</span>
              </div>
              <span className="text-[10px] font-mono text-text-tertiary">
                {isAdmin ? "Admin PDF Access" : "Secure Metadata View"}
              </span>
            </div>

            {isAdmin ? (
              /* Full interactive PDF viewer strictly for Admins */
              <div className="aspect-[4/5] sm:aspect-[16/10] bg-surface-sunken w-full relative">
                <iframe
                  src={`${project.pdfUrl}#toolbar=1`}
                  className="w-full h-full border-0"
                  title="Project Document"
                />
              </div>
            ) : (
              /* Static cover preview only for general users, no PDF extraction */
              <div className="flex flex-col md:flex-row items-center justify-center p-8 bg-surface-sunken gap-8 border-t border-border-subtle">
                <div className="w-44 h-56 bg-surface-raised border border-border-default rounded-sm overflow-hidden shadow-md flex-shrink-0 relative group select-none">
                  {project.coverImage ? (
                    <img src={project.coverImage} alt="Cover Preview" className="w-full h-full object-cover opacity-80" />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center bg-surface-sunken p-4 text-center">
                      <FontAwesomeIcon icon={faFileLines} className="h-10 w-10 text-text-tertiary mb-2" />
                      <span className="text-[10px] font-mono text-text-tertiary uppercase">No Preview</span>
                    </div>
                  )}
                  <div className="absolute inset-0 bg-surface-canvas/40 backdrop-blur-[1px] flex items-center justify-center">
                    <span className="bg-surface-canvas/90 text-text-secondary text-[9px] font-mono uppercase tracking-wider px-2 py-1 border border-border-subtle rounded-sm">
                      First Page Preview
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-4 max-w-sm text-center md:text-left">
                  <h3 className="text-sm font-semibold text-text-primary">Looking for the full report?</h3>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    General user access is restricted to title details and abstracts. If you need the full PDF for academic use, you can send an email request directly to the authors.
                  </p>
                  <div>
                    <button
                      onClick={() => setIsReportModalOpen(true)}
                      className="inline-flex items-center gap-2 px-4 py-2 bg-accent-primary text-text-inverse hover:bg-accent-primary-hover text-xs font-semibold rounded-sm transition-colors cursor-pointer"
                    >
                      <FontAwesomeIcon icon={faEnvelope} className="h-3.5 w-3.5" /> Request Full Report
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Similar Projects Rail per Chapter 17.6 */}
          <div className="flex flex-col gap-4">
            <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Similar Projects</h3>
            {loadingSimilar ? (
              /* Loading Skeletons */
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[1, 2].map((i) => (
                  <div key={i} className="bg-surface-raised border border-border-subtle rounded-md p-4 h-32 animate-pulse flex flex-col gap-3">
                    <div className="h-2 bg-border-default rounded w-1/4"></div>
                    <div className="h-4 bg-border-default rounded w-3/4"></div>
                    <div className="h-3 bg-border-default rounded w-1/2 mt-auto"></div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {similarProjects.map((p) => (
                  <Link
                    key={p.id}
                    to={`/projects/${p.id}`}
                    className="bg-surface-raised border border-border-subtle hover:border-border-default rounded-md p-4 flex flex-col gap-2 hover:bg-surface-hover/30 transition-all duration-150 group"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-text-tertiary uppercase">{p.department}</span>
                      <span className="text-[10px] text-text-tertiary">•</span>
                      <span className="text-[10px] font-mono text-text-tertiary">{p.year}</span>
                    </div>
                    <h4 className="text-xs font-semibold text-text-primary line-clamp-2 leading-snug group-hover:text-accent-primary transition-colors">
                      {p.title}
                    </h4>
                    <div className="text-[10px] text-text-secondary mt-auto">
                      Supervisor: {p.supervisor}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Right Side: Quick Actions Panel & Metadata Detail Table */}
        <div className="flex flex-col gap-6">
          
          {/* Actions Card */}
          <div className="bg-surface-raised border border-border-subtle rounded-md p-6 flex flex-col gap-4">
            <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">Actions</h3>
            
            <div className="flex flex-col gap-2">
              {!isAdmin && (
                <button
                  onClick={() => setIsReportModalOpen(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent-primary text-text-inverse hover:bg-accent-primary-hover text-xs font-semibold rounded-sm transition-colors cursor-pointer"
                >
                  <FontAwesomeIcon icon={faEnvelope} className="h-4 w-4" /> Request Report
                </button>
              )}

              {isAdmin && (
                <a
                  href={project.pdfUrl}
                  download
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent-primary text-text-inverse hover:bg-accent-primary-hover text-xs font-semibold rounded-sm transition-colors text-center cursor-pointer"
                >
                  <FontAwesomeIcon icon={faDownload} className="h-4 w-4" /> Download PDF
                </a>
              )}

              <button
                onClick={handleShare}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-surface-sunken hover:bg-surface-hover border border-border-default hover:border-border-strong text-text-primary text-xs font-semibold rounded-sm transition-all cursor-pointer"
              >
                <FontAwesomeIcon icon={faShareNodes} className="h-4 w-4" /> 
                {copiedShare ? "URL Copied!" : "Share Link"}
              </button>

              <div className="relative">
                <button
                  onClick={() => setIsCiteOpen(!isCiteOpen)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-surface-sunken hover:bg-surface-hover border border-border-default hover:border-border-strong text-text-primary text-xs font-semibold rounded-sm transition-all cursor-pointer"
                >
                  <FontAwesomeIcon icon={faQuoteLeft} className="h-4 w-4" /> Cite Project
                </button>

                {/* Citation Popover Dropdown */}
                {isCiteOpen && (
                  <div className="absolute right-0 left-0 mt-2 bg-surface-overlay border border-border-strong rounded-md p-4 shadow-xl z-20 flex flex-col gap-3">
                    <div className="flex items-center justify-between border-b border-border-subtle pb-2">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">BibTeX Citation</span>
                      <button 
                        onClick={handleCopyCitation}
                        className="text-[10px] font-mono text-accent-primary hover:underline flex items-center gap-1 cursor-pointer"
                      >
                        <FontAwesomeIcon icon={faCopy} className="h-3 w-3" /> {copiedCitation ? "Copied!" : "Copy"}
                      </button>
                    </div>
                    <pre className="text-[10px] font-mono bg-surface-sunken border border-border-subtle p-2 rounded text-text-secondary overflow-x-auto whitespace-pre-wrap select-all">
                      {bibtex}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Metadata Card Table */}
          <div className="bg-surface-raised border border-border-subtle rounded-md p-6 flex flex-col gap-4">
            <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">Metadata Details</h3>
            
            <div className="divide-y divide-border-subtle text-xs">
              <div className="py-2.5 flex justify-between">
                <span className="text-text-secondary">Department</span>
                <span className="font-mono text-text-primary uppercase">{project.department}</span>
              </div>
              <div className="py-2.5 flex justify-between">
                <span className="text-text-secondary">Cluster</span>
                <span className="text-text-primary font-medium">{project.cluster}</span>
              </div>
              <div className="py-2.5 flex justify-between">
                <span className="text-text-secondary">Year</span>
                <span className="font-mono text-text-primary">{project.year}</span>
              </div>
              <div className="py-2.5 flex flex-col gap-1.5">
                <span className="text-text-secondary">Technologies</span>
                <div className="flex flex-wrap gap-1.5 mt-0.5">
                  {project.technologies.map((t) => (
                    <span 
                      key={t}
                      className="bg-surface-sunken border border-border-default px-2 py-0.5 rounded-sm text-[10px] font-mono text-text-secondary"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
              <div className="py-2.5 flex flex-col gap-1.5">
                <span className="text-text-secondary">Roll Numbers</span>
                <div className="flex flex-col gap-1 font-mono text-[11px] text-text-primary mt-0.5">
                  {project.authors.map((a) => (
                    <div key={a.rollNumber} className="flex justify-between items-center bg-surface-sunken/40 px-2 py-1 border border-border-subtle/50 rounded-sm">
                      <span>{a.name}</span>
                      <span className="text-text-secondary">{a.rollNumber}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

        </div>

      </div>

      {/* Request Report Modal Dialog per Chapter 17.5 */}
      {isReportModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-canvas/80 backdrop-blur-sm p-4">
          <div 
            className="bg-surface-raised border border-border-strong rounded-md w-full max-w-lg shadow-2xl relative overflow-hidden flex flex-col animate-fade-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-accent-primary"></div>
            
            {/* Modal Header */}
            <div className="border-b border-border-subtle px-6 py-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Request Report Access</h3>
              <button 
                onClick={() => setIsReportModalOpen(false)}
                className="text-text-secondary hover:text-text-primary p-1 rounded-md hover:bg-surface-hover transition-colors cursor-pointer"
              >
                <FontAwesomeIcon icon={faXmark} className="h-4 w-4" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 flex flex-col gap-4 text-xs sm:text-sm">
              <p className="text-text-secondary leading-relaxed">
                Contact the authors of this project directly. You can copy their email addresses below or click the button to draft a pre-formatted request mail directly in your default mail client.
              </p>

              {/* Author Emails List */}
              <div className="flex flex-col gap-2.5">
                {project.authors.map((a) => (
                  <div key={a.rollNumber} className="flex flex-col sm:flex-row sm:items-center justify-between bg-surface-sunken border border-border-default rounded p-3 gap-2">
                    <div>
                      <p className="font-semibold text-text-primary text-xs">{a.name}</p>
                      <p className="font-mono text-text-tertiary text-[10px] mt-0.5">{a.rollNumber}</p>
                    </div>
                    {a.email ? (
                      <a 
                        href={`mailto:${a.email}`}
                        className="text-xs font-mono text-accent-primary hover:underline flex items-center gap-1"
                      >
                        {a.email} <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="h-3 w-3" />
                      </a>
                    ) : (
                      <span className="text-[10px] text-text-tertiary font-mono italic">No email registered</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Modal Footer / Composer Action */}
            <div className="border-t border-border-subtle px-6 py-4 bg-surface-sunken/45 flex flex-col sm:flex-row sm:items-center justify-end gap-3">
              <button
                onClick={() => setIsReportModalOpen(false)}
                className="px-4 py-2 bg-surface-raised border border-border-default hover:border-border-strong text-text-primary text-xs font-semibold rounded-sm transition-all cursor-pointer text-center"
              >
                Cancel
              </button>
              {mailtoEmails.length > 0 ? (
                <a
                  href={mailtoLink}
                  onClick={() => setIsReportModalOpen(false)}
                  className="px-4 py-2 bg-accent-primary text-text-inverse hover:bg-accent-primary-hover text-xs font-semibold rounded-sm transition-colors inline-flex items-center justify-center gap-2 text-center cursor-pointer"
                >
                  <FontAwesomeIcon icon={faEnvelope} className="h-4 w-4" /> Compose Request Email
                </a>
              ) : (
                <button
                  disabled
                  className="px-4 py-2 bg-surface-hover text-text-tertiary text-xs font-semibold rounded-sm cursor-not-allowed border border-border-subtle"
                >
                  Request Disabled (No Emails)
                </button>
              )}
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
