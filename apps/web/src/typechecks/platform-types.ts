/**
 * Compile-time regression for the platform types consumed by Next.js 16.4.
 * This module is not imported by a page and performs no runtime work. The normal
 * tsc check must resolve real URLPattern types, not hide missing names with any
 * or skipLibCheck. Negative assertions must keep failing in the expected way.
 */

/** Reject an assertion at compilation when its condition is not literally true. */
type ExpectTrue<Value extends true> = Value;

/** Detect any without broadening or replacing the platform declaration. */
type IsKnown<Value> = 0 extends (1 & Value) ? false : true;

/** URLPattern must be a real declaration supplied by the compiler's DOM library. */
export type PatternIsKnown = ExpectTrue<IsKnown<URLPattern>>;

/** The constructor input and options must not silently become any. */
export type InputIsKnown = ExpectTrue<IsKnown<URLPatternInput>>;
export type OptionsAreKnown = ExpectTrue<IsKnown<URLPatternOptions>>;

/** A pathname object is a valid, typed constructor input. */
export type AcceptPathname = ExpectTrue<
  { pathname: "/matches/:id" } extends URLPatternInput ? true : false
>;

/** Boolean values are not valid URLPattern input; losing that check must fail CI. */
// @ts-expect-error -- a boolean cannot satisfy the URLPattern input contract.
export type RejectBoolean = ExpectTrue<boolean extends URLPatternInput ? true : false>;

/** The documented case-sensitivity option accepts a boolean. */
export type AcceptIgnoreCase = ExpectTrue<
  { ignoreCase: true } extends URLPatternOptions ? true : false
>;
