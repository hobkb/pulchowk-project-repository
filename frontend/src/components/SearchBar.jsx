import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faMagnifyingGlass } from "@fortawesome/free-solid-svg-icons";

export default function SearchBar({
  variant = "compact",
  placeholder = "Search projects...",
  value = "",
  onChange,
  onFocus,
  onBlur,
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
        className={`flex items-center ${gap} bg-surface-raised border border-border-default hover:border-border-strong focus-within:border-accent-primary ${padding} py-2.5 rounded-md transition-all duration-150 shadow-sm`}
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
      </div>
    </div>
  );
}