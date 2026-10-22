/** Unmounted PostgreSQL step-up state adapter: no login or producer authority.
 *
 * A host must supply a protected AES-256-GCM key, a parameterized autocommit
 * database executor, and a previously verified PENDING session record digest.
 * Fixed SECURITY DEFINER SQL checks that parent row under a lock on both
 * issue and consume, including revocation and expiry. No direct table reads.
 */
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import type { WorkforceSqlExecutor } from "./postgres-oidc";
import {
  workforceStepUpClaimsRequest, type WorkforceStepUpAttempt,
  type WorkforceStepUpPolicy, type WorkforceStepUpStore,
} from "./step-up.ts";

const DIGEST = /^[a-f0-9]{64}$/;
const NONCE = /^[A-Za-z0-9_-]{43}$/;
const CONTEXT = /^c[1-9][0-9]?$/;
const GUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const CREATE = "SELECT public.matchdesk_create_workforce_step_up_challenge(" +
  "$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) AS created";
const CONSUME = "SELECT * FROM public.matchdesk_consume_workforce_step_up_challenge($1,$2)";
const FIELDS = [
  "state_digest", "pending_digest", "tenant_id", "client_id", "object_id",
  "subject", "context_id", "issued_at_ms", "expires_at_ms",
  "nonce_iv", "nonce_ciphertext", "nonce_tag",
] as const;

function deny(): never {
  throw new Error("Workforce step-up persistence denied");
}

function timestamp(value: unknown): number {
  if (typeof value === "number" && Number.isSafeInteger(value) && value > 0) return value;
  if (typeof value === "string" && /^[1-9][0-9]*$/.test(value)) {
    const parsed = Number(value);
    if (Number.isSafeInteger(parsed) && String(parsed) === value) return parsed;
  }
  return deny();
}

function validAttempt(attempt: WorkforceStepUpAttempt, policy: WorkforceStepUpPolicy) {
  return Boolean(attempt && typeof attempt === "object" &&
    DIGEST.test(attempt.stateDigest) && NONCE.test(attempt.nonce) &&
    attempt.tenantId === policy.oidc.tenantId &&
    attempt.clientId === policy.oidc.clientId &&
    GUID.test(attempt.objectId) &&
    typeof attempt.subject === "string" && attempt.subject.length > 0 &&
    attempt.subject.length <= 256 && attempt.contextId === policy.contextId &&
    Number.isSafeInteger(attempt.issuedAtSeconds) && attempt.issuedAtSeconds > 0 &&
    Number.isSafeInteger(attempt.expiresAtSeconds) &&
    attempt.expiresAtSeconds === attempt.issuedAtSeconds + 300 &&
    Number.isSafeInteger(attempt.issuedAtSeconds * 1000) &&
    Number.isSafeInteger(attempt.expiresAtSeconds * 1000));
}

function aad(a: Omit<WorkforceStepUpAttempt, "nonce">, pendingDigest: string): Buffer {
  return Buffer.from(JSON.stringify([
    a.stateDigest, pendingDigest, a.tenantId, a.clientId, a.objectId,
    a.subject, a.contextId, a.issuedAtSeconds, a.expiresAtSeconds,
  ]), "utf8");
}

/** The same parent digest is injected by the trusted host, never by the UI. */
export class PostgresWorkforceStepUpStore implements WorkforceStepUpStore {
  private readonly key: Buffer;
  private readonly sql: WorkforceSqlExecutor;
  private readonly policy: WorkforceStepUpPolicy;
  private readonly pendingDigest: string;

  constructor(sql: WorkforceSqlExecutor, policy: WorkforceStepUpPolicy,
    encryptionKey: Buffer, pendingDigest: string) {
    // Pin the exact reviewed HTTPS origin as well as issuer, resource and context.
    workforceStepUpClaimsRequest(policy);
    if (!sql || typeof sql.query !== "function" ||
        !policy || !policy.oidc || !GUID.test(policy.oidc.tenantId) ||
        !GUID.test(policy.oidc.clientId) || !GUID.test(policy.oidc.apiResourceAppId) ||
        policy.oidc.delegatedApiScope !==
          "api://" + policy.oidc.apiResourceAppId + "/MatchDesk.Producer.Access" ||
        !CONTEXT.test(policy.contextId) ||
        !Buffer.isBuffer(encryptionKey) || encryptionKey.length !== 32 ||
        typeof pendingDigest !== "string" || !DIGEST.test(pendingDigest)) {
      throw new Error("Protected step-up dependencies required");
    }
    this.sql = sql;
    this.policy = policy;
    this.key = Buffer.from(encryptionKey);
    this.pendingDigest = pendingDigest;
  }

  /** DB locks pending parent before creating immutable nonce ciphertext. */
  async create(attempt: WorkforceStepUpAttempt): Promise<boolean> {
    if (!validAttempt(attempt, this.policy)) return deny();
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", this.key, iv);
    cipher.setAAD(aad(attempt, this.pendingDigest));
    const sealed = Buffer.concat([cipher.update(attempt.nonce, "ascii"), cipher.final()]);
    const tag = cipher.getAuthTag();
    try {
      const result = await this.sql.query(CREATE, [
        attempt.stateDigest, this.pendingDigest, attempt.tenantId,
        attempt.clientId, attempt.objectId, attempt.subject, attempt.contextId,
        attempt.issuedAtSeconds * 1000, attempt.expiresAtSeconds * 1000,
        iv, sealed, tag,
      ]);
      if (!result || !Array.isArray(result.rows) || result.rows.length !== 1 ||
          typeof result.rows[0]?.created !== "boolean") return deny();
      return result.rows[0].created === true;
    } catch { return deny(); }
  }

  /** SQL consumes one state before any subsequent token/CA verification. */
  async consume(stateDigest: string): Promise<WorkforceStepUpAttempt | null> {
    if (typeof stateDigest !== "string" || !DIGEST.test(stateDigest)) return deny();
    try {
      const result = await this.sql.query(CONSUME, [stateDigest, this.pendingDigest]);
      if (!result || !Array.isArray(result.rows) || result.rows.length > 1) return deny();
      if (result.rows.length === 0) return null;
      const row = result.rows[0];
      if (Object.keys(row).length !== FIELDS.length ||
          FIELDS.some((field) => !Object.hasOwn(row, field)) ||
          row.state_digest !== stateDigest ||
          row.pending_digest !== this.pendingDigest ||
          row.tenant_id !== this.policy.oidc.tenantId ||
          row.client_id !== this.policy.oidc.clientId ||
          typeof row.object_id !== "string" || !GUID.test(row.object_id) ||
          row.context_id !== this.policy.contextId ||
          typeof row.subject !== "string" ||
          !Buffer.isBuffer(row.nonce_iv) || row.nonce_iv.length !== 12 ||
          !Buffer.isBuffer(row.nonce_ciphertext) || row.nonce_ciphertext.length !== 43 ||
          !Buffer.isBuffer(row.nonce_tag) || row.nonce_tag.length !== 16) return deny();
      const times = {
        issuedAtSeconds: timestamp(row.issued_at_ms) / 1000,
        expiresAtSeconds: timestamp(row.expires_at_ms) / 1000,
      };
      if (!Number.isSafeInteger(times.issuedAtSeconds) ||
          !Number.isSafeInteger(times.expiresAtSeconds)) return deny();
      const attempt: WorkforceStepUpAttempt = {
        stateDigest, tenantId: row.tenant_id as string,
        clientId: row.client_id as string, objectId: row.object_id as string,
        subject: row.subject, contextId: row.context_id as string,
        ...times, nonce: "",
      };
      const decipher = createDecipheriv("aes-256-gcm", this.key, row.nonce_iv);
      decipher.setAAD(aad(attempt, this.pendingDigest));
      decipher.setAuthTag(row.nonce_tag);
      const nonce = Buffer.concat([
        decipher.update(row.nonce_ciphertext), decipher.final(),
      ]).toString("ascii");
      const restored = { ...attempt, nonce };
      if (!validAttempt(restored, this.policy)) return deny();
      return Object.freeze(restored);
    } catch { return deny(); }
  }
}
