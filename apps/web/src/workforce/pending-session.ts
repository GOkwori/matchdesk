/** Disabled-by-design, encrypted PostgreSQL vault for PENDING workforce sessions.
 *
 * A verified code exchange is NOT an authentication session and cannot assert
 * recent MFA, operator entitlements, case authority or publication rights.
 * This class stores only a pending encrypted delegated token, permits explicit
 * revocation, and intentionally returns null on every BFF resolve(). There is
 * no activation or token-reading database function in this migration.
 *
 * An independently accepted phase must add authenticated step-up, fresh
 * entitlements, a protected cookie/CSRF issuance lifecycle, a separate audited
 * activation transaction and server-side expiry/revocation enforcement.
 */
import { createCipheriv, createHash, randomBytes } from "node:crypto";
import type { VerifiedWorkforceCodeExchange } from "./entra";
import type { WorkforceSessionResolver } from "./bff";
import type { WorkforceOidcPolicy } from "./oidc";
import type { WorkforceSqlExecutor } from "./postgres-oidc";

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DIGEST = /^[0-9a-f]{64}$/;
const JWT = /^[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}$/;
const MAX_TOKEN_BYTES = 8192;
const MAX_PENDING_MS = 15 * 60_000;
const PREPARE_SQL = "SELECT public.matchdesk_prepare_workforce_session(" +
  "$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) AS prepared";
const REVOKE_SQL = "SELECT public.matchdesk_revoke_workforce_session($1) AS revoked";

export type PendingSessionReceipt = Readonly<{
  /** Host-only administrative digest. NOT a login cookie or bearer credential. */
  recordDigest: string;
  expiresAtMs: number;
}>;

function denied(): never {
  throw new Error("Workforce pending session denied");
}

/** Application role never receives raw session or token, only fixed SQL outputs. */
export class PostgresPendingWorkforceSessions implements WorkforceSessionResolver {
  private readonly sql: WorkforceSqlExecutor;
  private readonly key: Buffer;
  private readonly policy: WorkforceOidcPolicy;

  /** An injection of a real DB driver does not activate any workforce HTTP route. */
  constructor(sql: WorkforceSqlExecutor, policy: WorkforceOidcPolicy, encryptionKey: Buffer) {
    if (!sql || typeof sql.query !== "function" ||
        !Buffer.isBuffer(encryptionKey) || encryptionKey.length !== 32 ||
        !policy || !GUID.test(policy.tenantId) ||
        !GUID.test(policy.clientId) || !GUID.test(policy.apiResourceAppId) ||
        policy.delegatedApiScope !==
          "api://" + policy.apiResourceAppId + "/MatchDesk.Producer.Access") {
      throw new Error("Workforce session vault requires approved host dependencies");
    }
    // The pending vault must independently enforce the canonical HTTPS origin.
    // Do not rely on an upstream OIDC adapter to validate host configuration.
    let origin: URL;
    try {
      origin = new URL(policy.publicOrigin);
    } catch {
      throw new Error("Workforce session vault requires approved host dependencies");
    }
    if (origin.protocol !== "https:" || origin.origin !== policy.publicOrigin ||
        origin.pathname !== "/" || origin.search !== "" || origin.hash !== "" ||
        origin.username !== "" || origin.password !== "") {
      throw new Error("Workforce session vault requires approved host dependencies");
    }
    this.sql = sql;
    this.policy = policy;
    this.key = Buffer.from(encryptionKey);
  }

  /** Encrypt one already-verified exchange as unactivated, without cookies.
   *
   * The host is responsible for trusted Entra verification. No call to this
   * method proves MFA or establishes a browser session.
   */
  async prepare(
    exchange: VerifiedWorkforceCodeExchange, nowMs: number,
  ): Promise<PendingSessionReceipt> {
    const p = this.policy;
    const issuer = "https://login.microsoftonline.com/" + p.tenantId.toLowerCase() + "/v2.0";
    if (!exchange || typeof exchange !== "object" ||
        exchange.tenantId !== p.tenantId ||
        exchange.issuer !== issuer || exchange.clientId !== p.clientId ||
        typeof exchange.subject !== "string" ||
        exchange.subject.length < 1 || exchange.subject.length > 256 ||
        !GUID.test(exchange.objectId) ||
        typeof exchange.delegatedAccessToken !== "string" ||
        exchange.delegatedAccessToken.length > MAX_TOKEN_BYTES ||
        !JWT.test(exchange.delegatedAccessToken) ||
        !Number.isSafeInteger(exchange.expiresAtSeconds) ||
        !Number.isSafeInteger(nowMs) || nowMs < 1 ||
        nowMs > Number.MAX_SAFE_INTEGER - MAX_PENDING_MS ||
        // The signed API token is already capped to 3600 seconds. Refuse
        // implausibly long or future forged claims rather than truncating them.
        exchange.expiresAtSeconds > Math.floor(nowMs / 1000) + 3600) return denied();

    const expiresAtMs = Math.min(
      nowMs + MAX_PENDING_MS, exchange.expiresAtSeconds * 1000,
    );
    if (!Number.isSafeInteger(expiresAtMs) || expiresAtMs <= nowMs + 5000) return denied();

    // A digest is a non-credential row identifier. No raw identifier or cookie
    // is issued, and the only application-role lookup is revocation by digest.
    const recordDigest = createHash("sha256").update(randomBytes(32)).digest("hex");
    const iv = randomBytes(12);
    const aad = Buffer.from(JSON.stringify([
      recordDigest, p.tenantId, issuer, exchange.subject, exchange.objectId,
      p.clientId, nowMs, expiresAtMs,
    ]), "utf8");
    const cipher = createCipheriv("aes-256-gcm", this.key, iv);
    cipher.setAAD(aad);
    const ciphertext = Buffer.concat([
      cipher.update(exchange.delegatedAccessToken, "ascii"), cipher.final(),
    ]);
    const tag = cipher.getAuthTag();
    try {
      const result = await this.sql.query(PREPARE_SQL, [
        recordDigest, p.tenantId, issuer, exchange.subject, exchange.objectId,
        p.clientId, nowMs, expiresAtMs, iv, ciphertext, tag,
      ]);
      if (!result || !Array.isArray(result.rows) || result.rows.length !== 1 ||
          result.rows[0]?.prepared !== true) return denied();
      return { recordDigest, expiresAtMs };
    } catch {
      return denied();
    }
  }

  /** Revoke a pending record once; never delete its replay tombstone. */
  async revoke(recordDigest: string): Promise<boolean> {
    if (typeof recordDigest !== "string" || !DIGEST.test(recordDigest)) return denied();
    try {
      const result = await this.sql.query(REVOKE_SQL, [recordDigest]);
      if (!result || !Array.isArray(result.rows) || result.rows.length !== 1 ||
          typeof result.rows[0]?.revoked !== "boolean") return denied();
      return result.rows[0].revoked;
    } catch {
      return denied();
    }
  }

  /** Hard safety boundary: pending state can NEVER authenticate the BFF. */
  async resolve(_opaqueSessionId: string): Promise<null> {
    return null;
  }
}
