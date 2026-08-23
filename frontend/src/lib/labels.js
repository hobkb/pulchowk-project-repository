/**
 * Presentation labels for values stored as short codes.
 *
 * The database keeps the code ("UG", "078") because that is what the rest
 * of the system matches on. Nothing a reader sees should be a code, so the
 * mapping happens here, in one place, rather than being re-invented per
 * page with slightly different wording each time.
 */

export const ACADEMIC_LEVELS = [
  { value: "UG", label: "Undergraduate" },
  { value: "Masters", label: "Masters" },
  { value: "PhD", label: "Doctor of Philosophy" },
];

export function academicLevelLabel(value) {
  if (!value) return "Not recorded";
  return ACADEMIC_LEVELS.find((level) => level.value === value)?.label || value;
}

/**
 * Batches are stored as the three-digit admission code ("078"); readers
 * know them as the four-digit Bikram Sambat year.
 */
export function batchLabel(code) {
  const text = String(code ?? "").trim();
  return /^\d{3}$/.test(text) ? `20${text.slice(-2)}` : text;
}

/**
 * A supervisor as a reader would see them named: any academic title in
 * front, the designation after. Stored separately, so a record with only
 * one of them still reads correctly rather than leaving a stray comma.
 */
export function personDisplayName(person) {
  if (!person) return "";
  const name = String(person.name || person.full_name || "").trim();
  const title = String(person.title || "").trim();
  return title && !name.toLowerCase().startsWith(title.toLowerCase())
    ? `${title} ${name}`
    : name;
}

export function personWithDesignation(person) {
  const name = personDisplayName(person);
  const designation = String(person?.designation || "").trim();
  return designation ? `${name}, ${designation}` : name;
}
