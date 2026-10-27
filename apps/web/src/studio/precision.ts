/** Round half up exactly as matchdesk.domain.models.round_half_up does, on decimal digits.
 *
 * Kept apart from the verifier so screens that only format a figure do not load the whole
 * verifier up front.
 */

/** Plain decimal digits of a number's shortest round-trip form (JS and Python agree on it). */
function plainDecimal(value: number): { negative: boolean; int: string; frac: string } {
  const text = String(Math.abs(value));
  const [mantissa, exp = "0"] = text.split(/e/i);
  const [whole, fraction = ""] = mantissa.split(".");
  let digits = whole + fraction;
  let point = whole.length + Number(exp);
  if (point <= 0) { digits = "0".repeat(1 - point) + digits; point = 1; }
  if (point > digits.length) digits += "0".repeat(point - digits.length);
  return { negative: value < 0, int: digits.slice(0, point).replace(/^0+(?=\d)/, ""), frac: digits.slice(point) };
}

/** Round half up (away from zero on ties) at `decimals` places; returns a canonical string. */
export function roundHalfUp(value: number, decimals: number): string {
  const { negative, int, frac } = plainDecimal(value);
  const padded = (frac + "0".repeat(decimals + 1)).slice(0, decimals + 1);
  let kept = (int + padded.slice(0, decimals)).split("").map(Number);
  if (padded[decimals] >= "5") {
    let i = kept.length - 1;
    while (i >= 0 && kept[i] === 9) { kept[i] = 0; i -= 1; }
    if (i < 0) kept = [1, ...kept]; else kept[i] += 1;
  }
  const digits = kept.join("");
  const whole = digits.slice(0, digits.length - decimals).replace(/^0+(?=\d)/, "") || "0";
  const rounded = decimals ? `${whole}.${digits.slice(digits.length - decimals)}` : whole;
  return negative && /[1-9]/.test(rounded) ? `-${rounded}` : rounded;
}

