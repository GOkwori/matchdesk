/** Shared 1200x630 social card renderer (build-time, static) used by the studio OG image routes. */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const ogSize = { width: 1200, height: 630 } as const;

/** Render a branded card: panther mark, eyebrow, headline and a one-line footer. */
export async function renderCard({ eyebrow, title, footer }: { eyebrow: string; title: string; footer: string }) {
  const dir = join(process.cwd(), "src/studio");
  const [mark, regular, bold] = await Promise.all([
    readFile(join(dir, "assets/matchdesk-mark-256.png")),
    readFile(join(dir, "og/fonts/plus-jakarta-sans-500.ttf")),
    readFile(join(dir, "og/fonts/plus-jakarta-sans-800.ttf")),
  ]);
  const src = `data:image/png;base64,${mark.toString("base64")}`;
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 72, background: "linear-gradient(135deg, #0e1319 0%, #151c25 60%, #3a1c12 100%)", color: "#f5f7fa", fontFamily: "Jakarta" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <img src={src} width={84} height={84} alt="" />
          <div style={{ display: "flex", fontSize: 44, fontWeight: 800 }}>Match<span style={{ color: "#ff7a3d" }}>Desk</span></div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: 4, textTransform: "uppercase", color: "#ffb38a" }}>{eyebrow}</div>
          <div style={{ fontSize: 68, fontWeight: 800, lineHeight: 1.1, maxWidth: 1000 }}>{title}</div>
        </div>
        <div style={{ display: "flex", fontSize: 26, color: "#a7b4c2" }}>{footer}</div>
      </div>
    ),
    {
      ...ogSize,
      fonts: [
        { name: "Jakarta", data: regular, weight: 500, style: "normal" },
        { name: "Jakarta", data: bold, weight: 800, style: "normal" },
      ],
    },
  );
}
