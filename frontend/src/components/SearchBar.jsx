import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMagnifyingGlass } from "@fortawesome/free-solid-svg-icons";

export default function SearchBar({
  variant = "compact",
  placeholder = "Search projects...",
  value = "",
  onChange,
  onFocus,
  onBlur,
  mode = "keyword",
  onModeChange,
  showModeToggle = false,
  className = "",
  ...props
}) {
  const isHero = variant === "hero";

  const inputTextSize = isHero ? "text-h2" : "text-body";
  const placeholderSize = isHero ? "text-body" : "text-body-sm";
  const iconSize = isHero ? "h-5 w-5" : "h-4 w-4";
  const padding = isHero ? "px-6" : "px-3.5";
  const gap = isHero ? "gap-3" : "gap-2";

return (
    <div
      className={`relative w-full ${isHero ? "max-w-[680px] mx-auto" : "max-w-[480px]"} ${className}`}
    >
      <div
        className={`flex items-center ${gap} bg-surface-raised border border-border-default hover:border-border-strong focus-within:border-accent-primary ${padding} py-2 rounded-md transition-all duration-150`}
      >
        <FontAwesomeIcon icon={faMagnifyingGlass} className={`${iconSize} text-text-tertiary shrink-0`} aria-hidden="true" />

        <input
          type="text"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          onFocus={onFocus}
          onBlur={onBlur}
          className={`bg-transparent border-0 outline-none w-full min-w-0 ${inputTextSize} text-text-primary placeholder:text-text-tertiary ${placeholderSize}`}
          {...props}
        />

        {showModeToggle && (
          <div className="relative shrink-0 ml-2">
            <select
              value={mode}
              onChange={(e) => onModeChange?.(e.target.value)}
              className={`appearance-none bg-transparent border-0 outline-none ${isHero ? "text-body" : "text-body-sm"} text-text-primary cursor-pointer pr-9 py-1.5 border-l border-border-subtle pl-3 min-w-[110px] max-w-[140px]`}
              aria-label="Search mode"
            >
              <option value="keyword">Keyword</option>
              <option value="semantic">Semantic</option>
            </select>
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-text-tertiary">
              <svg className={`${iconSize}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}