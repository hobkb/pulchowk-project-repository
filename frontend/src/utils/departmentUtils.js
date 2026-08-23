export const DEPARTMENT_ACRONYMS = {
  "department of architecture": "DoARCH",
  "department of architecture and urban planning": "DoARCH",
  "department of civil engineering": "DoCE",
  "department of electrical engineering": "DoEE",
  "department of electronics and computer engineering": "DoECE",
  "department of mechanical and aerospace engineering": "DoME",
  "department of mechanical engineering": "DoME",
  "department of applied sciences and chemical engineering": "DoAS",
  "department of chemical engineering": "DoAS",
};

export function getDepartmentAcronym(deptName) {
  if (!deptName) return "DoECE";
  const key = String(deptName).trim().toLowerCase();
  
  if (DEPARTMENT_ACRONYMS[key]) return DEPARTMENT_ACRONYMS[key];
  
  // Partial matching fallback
  if (key.includes("architecture")) return "DoARCH";
  if (key.includes("civil")) return "DoCE";
  if (key.includes("electrical") && !key.includes("electronics")) return "DoEE";
  if (key.includes("electronics") || key.includes("computer")) return "DoECE";
  if (key.includes("mechanical") || key.includes("aerospace")) return "DoME";
  if (key.includes("chemical") || key.includes("applied sciences")) return "DoAS";
  
  return deptName;
}
