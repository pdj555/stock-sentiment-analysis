import { ImageResponse } from "next/og";

export const alt = "Sentiment — Read the market before it moves";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "84px 96px",
          background: "#05080c",
          backgroundImage:
            "linear-gradient(rgba(60,60,60,0.35) 1px, transparent 1px), linear-gradient(90deg, rgba(60,60,60,0.35) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          color: "#f5f5f5",
          fontFamily: "sans-serif",
          position: "relative",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            fontSize: 22,
            letterSpacing: "0.32em",
            textTransform: "uppercase",
            color: "#8b949e",
            fontWeight: 500,
          }}
        >
          <div style={{ display: "flex", fontWeight: 600, color: "#a9daf7" }}>
            Sentiment
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 18,
              fontSize: 22,
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              color: "#5c6370",
              fontWeight: 500,
              marginBottom: 28,
            }}
          >
            <div
              style={{
                width: 56,
                height: 1,
                background: "rgba(169,218,247,0.4)",
              }}
            />
            Market intelligence
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontSize: 132,
              fontWeight: 600,
              lineHeight: 0.96,
              letterSpacing: "-0.035em",
              color: "#f5f5f5",
            }}
          >
            <div style={{ display: "flex" }}>Read the market</div>
            <div style={{ display: "flex", gap: 28 }}>
              <span>before it</span>
              <span style={{ color: "#a9daf7" }}>moves.</span>
            </div>
          </div>

          <div
            style={{
              marginTop: 38,
              fontSize: 30,
              lineHeight: 1.4,
              color: "#8b949e",
              maxWidth: 760,
              display: "flex",
            }}
          >
            Every recent headline read, scored by AI, distilled into one clear
            signal.
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            color: "#5c6370",
            fontSize: 22,
            letterSpacing: "0.04em",
          }}
        >
          <div style={{ display: "flex", gap: 14 }}>
            {["AAPL", "NVDA", "TSLA", "AMD"].map((symbol) => (
              <div
                key={symbol}
                style={{
                  display: "flex",
                  padding: "10px 18px",
                  borderRadius: 999,
                  border: "1px solid rgba(169,218,247,0.2)",
                  background: "rgba(169,218,247,0.04)",
                  color: "#1769ff",
                  fontWeight: 500,
                  letterSpacing: "0.08em",
                }}
              >
                {symbol}
              </div>
            ))}
          </div>
          <div style={{ display: "flex" }}>For research only.</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
