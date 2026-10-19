/** Encrypted, single-use workforce OIDC attempts for a future trusted Next.js host.
 *
 * This adapter implements the offline WorkforceOidcAttemptStore contract with
 * an injected parameterized PostgreSQL query executor. It does NOT open a
 * database connection, provision a key, register Entra, redeem authorization
 * codes, create workforce sessions or mount any privileged HTTP route.
 *
 * Only two fixed, owner-controlled SECURITY DEFINER functions are callable by
 * the future least-privilege state role. No direct table privileges are needed.
 * The executor MUST resolve its query only after each statement commits;
 * consuming state is an atomic UPDATE with a durable replay tombstone.
 */
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import type {
  WorkforceOidcAttempt, WorkforceOidcAttemptStore, WorkforceOidcPolicy,
} from "./oidc";

const DIGEST = /^[a-f0-9]{64}$/;
const SECRET = /^[A-Za-z0-9_-]{43}$/;
const GUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const EXPIRY_MS = 300_000;
const CREATE_SQL = "SELECT public.matchdesk_create_workforce_oidc_attempt(" +
  "$1,$2,$3,$4,$5,$6,$7,$8,$9,$10) AS created";
const CONSUME_SQL = "SELECT * FROM public.matchdesk_consume_workforce_oidc_attempt($1)";
const FIELDS = [
  "state_digest", "binding_digest", "issuer", "client_id", "redirect_uri",
  "issued_at_ms", "expires_at_ms", "secret_iv", "secret_ciphertext", "secret_tag",
] as const;

export type WorkforceSqlResult = Readonly<{
  rows: readonly Readonly<Record<string, unknown>>[];
}>;

/** Trusted database driver adapter: parameter binding and autocommit required. */
export type WorkforceSqlExecutor = Readonly<{
  query(sql: string, parameters: readonly unknown[]): Promise<WorkforceSqlResult>;
}>;

function invalid(): never {
  throw new Error("Workforce OIDC state denied");
}

function validatePolicy(policy: WorkforceOidcPolicy): void {
  if (!policy || typeof policy !== "object" ||
      !GUID.test(policy.tenantId) || !GUID.test(policy.clientId) ||
      !GUID.test(policy.apiResourceAppId) ||
      policy.delegatedApiScope !==
        "api://" + policy.apiResourceAppId + "/MatchDesk.Producer.Access") {
    throw new ValueError("Invalid workforce OIDC persistence policy");
  }
  try {
    const url = new URL(policy.publicOrigin);
    if (url.protocol !== "https:" || policy.publicOrigin !== url.origin ||
        url.pathname !== "/" || url.search !== "" || url.hash !== "" ||
        url.username || url.password) {
      throw new Error("Invalid HTTPS origin");
    }
  } catch {
    throw new Error("Invalid workforce OIDC persistence origin");
  }
}

/** Fixed serialization also authenticates issuer, client, target and expiry. */
function aad(values: WorkforceOidcAttempt): Buffer {
  return Buffer.from(JSON.stringify([
    values.stateDigest, values.bindingDigest, values.issuer,
    values.clientId, values.redirectUri, values.issuedAtMs, values.expiresAtMs,
  ]), "utf8");
}

function validAttempt(attempt: WorkforceOidcAttempt, policy: WorkforceOidcPolicy): boolean {
  return Boolean(
    attempt && typeof attempt === "object" &&
    DIGEST.test(attempt.stateDigest) && DIGEST.test(attempt.bindingDigest) &&
    attempt.issuer === "https://login.microsoftonline.com/" +
      policy.tenantId.toLowerCase() + "/v2.0" &&
    attempt.clientId === policy.clientId &&
    attempt.redirectUri === policy.publicOrigin + "/api/workforce/oidc/callback" &&
    Number.isSafeInteger(attempt.issuedAtMs) && attempt.issuedAtMs > 0 &&
    Number.isSafeInteger(attempt.expiresAtMs) &&
    attempt.expiresAtMs - attempt.issuedAtMs === EXPIRY_MS &&
    SECRET.test(attempt.nonce) && SECRET.test(attempt.codeVerifier)
  );
}

/** pg returns BIGINT as a string by default; reject precision loss or coercion. */
function timestamp(value: unknown): number {
  if (typeof value === "number" && Number.isSafeInteger(value) && value > 0) return value;
  if (typeof value === "string" && /^[1-9][0-9]*$/.test(value)) {
    const parsed = Number(value);
    if (Number.isSafeInteger(parsed) && parsed > 0 && String(parsed) === value) return parsed;
  }
  return invalid();
}

/** A database row can never add arbitrary fields or override host policy. */
function unpack(row: Readonly<Record<string, unknown>>, key: Buffer,
  policy: WorkforceOidcPolicy, expectedDigest: string): WorkforceOidcAttempt {
  if (Object.keys(row).length !== FIELDS.length ||
      FIELDS.some((name) => !Object.hasOwn(row, name))) return invalid();
  const values: WorkforceOidcAttempt = {
    stateDigest: row.state_digest as string,
    bindingDigest: row.binding_digest as string,
    issuer: row.issuer as string,
    clientId: row.client_id as string,
    redirectUri: row.redirect_uri as string,
    issuedAtMs: timestamp(row.issued_at_ms),
    expiresAtMs: timestamp(row.expires_at_ms),
    nonce: "", codeVerifier: "",
  };
  if (values.stateDigest !== expectedDigest ||
      !DIGEST.test(values.stateDigest) || !DIGEST.test(values.bindingDigest) ||
      !Buffer.isBuffer(row.secret_iv) ||
      !Buffer.isBuffer(row.secret_ciphertext) ||
      !Buffer.isBuffer(row.secret_tag) ||
      row.secret_iv.length !== 12 || row.secret_ciphertext.length !== 87 ||
      row.secret_tag.length !== 16) return invalid();
  try {
    const decipher = createDecipheriv("aes-256-gcm", key, row.secret_iv);
    decipher.setAAD(aad(values));
    decipher.setAuthTag(row.secret_tag);
    const plaintext = Buffer.concat([
      decipher.update(row.secret_ciphertext), decipher.final(),
    ]).toString("ascii");
    const sections = plaintext.split(":");
    if (sections.length !== 2) return invalid();
    const restored = {
      ...values, nonce: sections[0], codeVerifier: sections[1],
    };
    if (!validAttempt(restored, policy)) return invalid();
    return restored;
  } catch {
    return invalid();
  }
}

export class PostgresWorkforceOidcAttemptStore implements WorkforceOidcAttemptStore {
  private readonly key: Buffer;
  private readonly sql: WorkforceSqlExecutor;
  private readonly policy: WorkforceOidcPolicy;

  /** The protected host owns the AES-256 key and configured DB driver. */
  constructor(sql: WorkforceSqlExecutor, policy: WorkforceOidcPolicy, encryptionKey: Buffer) {
    validatePolicy(policy);
    if (!sql || typeof sql.query !== "function" ||
        !Buffer.isBuffer(encryptionKey) || encryptionKey.length !== 32) {
      throw new Error("A trusted executor and 256-bit host encryption key are required");
    }
    this.sql = sql;
    this.policy = policy;
    this.key = Buffer.from(encryptionKey);
  }

  /** Persist encrypted secrets; a state hash collision is never overwritten. */
  async create(attempt: WorkforceOidcAttempt): Promise<boolean> {
    if (!validAttempt(attempt, this.policy)) return invalid();
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", this.key, iv);
    cipher.setAAD(aad(attempt));
    const data = Buffer.from(attempt.nonce + ":" + attempt.codeVerifier, "ascii");
    const ciphertext = Buffer.concat([cipher.update(data), cipher.final()]);
    const tag = cipher.getAuthTag();
    try {
      const result = await this.sql.query(CREATE_SQL, [
        attempt.stateDigest, attempt.bindingDigest, attempt.issuer,
        attempt.clientId, attempt.redirectUri, attempt.issuedAtMs,
        attempt.expiresAtMs, iv, ciphertext, tag,
      ]);
      if (!result || !Array.isArray(result.rows) ||
          result.rows.length !== 1 ||
          typeof result.rows[0]?.created !== "boolean") return invalid();
      return result.rows[0].created === true;
    } catch {
      return invalid();
    }
  }

  /** Atomic conditional claim: expired/consumed rows can never be replayed. */
  async consume(stateDigest: string): Promise<WorkforceOidcAttempt | null> {
    if (typeof stateDigest !== "string" || !DIGEST.test(stateDigest)) return invalid();
    try {
      const result = await this.sql.query(CONSUME_SQL, [stateDigest]);
      if (!result || !Array.isArray(result.rows) || result.rows.length > 1) return invalid();
      if (result.rows.length === 0) return null;
      return unpack(result.rows[0], this.key, this.policy, stateDigest);
    } catch {
      return invalid();
    }
  }
}
