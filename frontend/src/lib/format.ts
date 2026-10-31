// Display-only formatting. Money strings are formatted textually (no float math).

function groupIndian(intPart: string): string {
  if (intPart.length <= 3) return intPart;
  const last3 = intPart.slice(-3);
  const rest = intPart.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${rest},${last3}`;
}

function groupWestern(intPart: string): string {
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

const SYMBOLS: Record<string, string> = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

/** Format a decimal money string such as "-1100.00" → "−₹1,100.00". */
export function formatMoney(value: string, currency = "INR", opts?: { signed?: boolean }): string {
  const s = value.trim();
  const negative = s.startsWith("-");
  const unsigned = s.replace(/^[-+]/, "");
  const [i = "0", d = "00"] = unsigned.split(".");
  const grouped = currency === "INR" ? groupIndian(i) : groupWestern(i);
  const sym = SYMBOLS[currency] ?? `${currency} `;
  const isZero = /^0*\.?0*$/.test(unsigned);
  const sign = negative && !isZero ? "−" : opts?.signed && !isZero ? "+" : "";
  return `${sign}${sym}${grouped}.${d.padEnd(2, "0").slice(0, 2)}`;
}

export function formatQty(n: number, unit?: string): string {
  const s = groupIndian(String(Math.trunc(Math.abs(n))));
  return `${n < 0 ? "−" : ""}${s}${unit ? ` ${unit}` : ""}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2025-05-14" → "14 May 2025" (string-based, timezone-safe). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  const mi = Number(m) - 1;
  if (!y || Number.isNaN(mi) || !d) return iso;
  return `${Number(d)} ${MONTHS[mi]} ${y}`;
}

export function isNegative(value: string) {
  return value.trim().startsWith("-") && !/^-0*\.?0*$/.test(value.trim());
}
