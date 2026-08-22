import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ingestionApi } from "../api/client";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCloudArrowUp, faFilePdf, faSpinner, faCircleExclamation, faCheckCircle } from "@fortawesome/free-solid-svg-icons";

export default function AdminUpload() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (selected.type !== "application/pdf" && !selected.name.endsWith(".pdf")) {
        setError("Only PDF files are supported for thesis ingestion.");
        setFile(null);
        return;
      }
      setError(null);
      setFile(selected);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) {
      if (dropped.type !== "application/pdf" && !dropped.name.endsWith(".pdf")) {
        setError("Only PDF files are supported for thesis ingestion.");
        setFile(null);
        return;
      }
      setError(null);
      setFile(dropped);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a thesis PDF file to upload.");
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await ingestionApi.uploadJob(formData);
      const jobId = res?.data?.id;

      if (jobId) {
        navigate(`/admin/jobs/${jobId}`);
      } else {
        throw new Error("Job ID missing from server response.");
      }
    } catch (err) {
      setError(err.message || "Failed to upload project thesis file.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-8 py-4">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="text-micro font-mono uppercase tracking-wider text-accent-primary bg-accent-primary/10 border border-accent-primary/20 px-2 py-0.5 rounded-sm">
            Project Archive
          </span>
        </div>
        <h1 className="text-h1 font-bold tracking-tight text-text-primary">
          Submit Project Report
        </h1>
        <p className="text-body text-text-secondary leading-relaxed">
          Upload an official undergraduate thesis or departmental project PDF for cataloging and digital archive storage.
        </p>
      </div>

      {/* Upload Box */}
      <form onSubmit={handleUpload} className="flex flex-col gap-6">
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center text-center transition-all duration-200 cursor-pointer relative ${
            isDragging
              ? "border-accent-primary bg-accent-primary/5 scale-[1.005]"
              : file
              ? "border-success-emerald/50 bg-success-emerald/5"
              : "border-border-default hover:border-accent-primary/50 bg-surface-raised"
          }`}
        >
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            disabled={uploading}
            className="absolute inset-0 opacity-0 cursor-pointer disabled:cursor-not-allowed"
          />

          {file ? (
            <div className="flex flex-col items-center gap-3">
              <div className="h-16 w-16 rounded-full bg-success-emerald/10 border border-success-emerald/20 flex items-center justify-center text-success-emerald">
                <FontAwesomeIcon icon={faFilePdf} className="h-8 w-8" />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-body font-semibold text-text-primary">
                  {file.name}
                </span>
                <span className="text-micro font-mono text-text-tertiary">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB &middot; PDF Document
                </span>
              </div>
              <span className="text-micro font-mono text-success-emerald flex items-center gap-1.5 bg-success-emerald/10 px-2.5 py-1 rounded-full mt-1">
                <FontAwesomeIcon icon={faCheckCircle} /> Ready for Processing
              </span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="h-16 w-16 rounded-full bg-surface-sunken border border-border-subtle flex items-center justify-center text-text-secondary group-hover:text-accent-primary">
                <FontAwesomeIcon icon={faCloudArrowUp} className="h-8 w-8" />
              </div>
              <div>
                <p className="text-body font-semibold text-text-primary">
                  Click to browse or drop a project report PDF here
                </p>
                <p className="text-body-sm text-text-tertiary mt-1">
                  Supports official undergraduate and graduate project reports (.pdf)
                </p>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="p-4 rounded-md bg-error-red/10 border border-error-red/20 flex items-start gap-3 text-error-red text-body-sm">
            <FontAwesomeIcon icon={faCircleExclamation} className="h-4 w-4 shrink-0 mt-0.5" />
            <div className="flex-1">{error}</div>
          </div>
        )}

        {/* Form Actions */}
        <div className="flex items-center justify-between border-t border-border-subtle pt-6">
          <button
            type="button"
            onClick={() => setFile(null)}
            disabled={!file || uploading}
            className="px-4 py-2 rounded-md border border-border-default bg-surface-raised text-text-secondary text-body-sm hover:text-text-primary disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed transition-all"
          >
            Clear Selection
          </button>

          <button
            type="submit"
            disabled={!file || uploading}
            className="px-6 py-2.5 rounded-md bg-accent-primary hover:bg-accent-primary/90 text-white font-medium text-body-sm flex items-center gap-2 transition-all shadow-sm cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {uploading ? (
              <>
                <FontAwesomeIcon icon={faSpinner} className="animate-spin h-4 w-4" />
                Processing Document...
              </>
            ) : (
              <>
                <FontAwesomeIcon icon={faCloudArrowUp} className="h-4 w-4" />
                Submit Document
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
