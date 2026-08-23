/**
 * The site footer — a primary band closing the page, carrying the
 * institution's own imprint. Deliberately plain: no link farm, no
 * newsletter, no social row.
 */
export default function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-line bg-deep text-on-dark">
      <div className="mx-auto max-w-[1180px] px-5 sm:px-8 py-7">
        <div className="flex flex-wrap items-start justify-between gap-x-10 gap-y-5">
          <div className="min-w-0">
            <p className="text-sm font-semibold">Pulchowk Project Repository</p>
            <p className="mt-1 text-xs text-white/70">
              Institute of Engineering, Pulchowk Campus
              <br />
              Tribhuvan University, Lalitpur, Nepal
            </p>
          </div>
          <p className="text-xs text-white/60">
            © {new Date().getFullYear()} Institute of Engineering, Tribhuvan University
          </p>
        </div>
      </div>
    </footer>
  );
}
