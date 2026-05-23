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
          background: "#0d0c0a",
          backgroundImage: [
            "radial-gradient(ellipse 75% 60% at 50% -8%, rgba(201, 169, 110, 0.32), transparent 64%)",
            "radial-gradient(ellipse 55% 50% at 92% 18%, rgba(122, 184, 160, 0.20), transparent 64%)",
            "radial-gradient(ellipse 65% 55% at 8% 102%, rgba(201, 169, 110, 0.14), transparent 62%)",
          ].join(", "),
          color: "#f2efe9",
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
            color: "#9e9890",
            fontWeight: 500,
          }}
        >
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: 999,
              background: "#c9a96e",
              boxShadow: "0 0 18px rgba(201,169,110,0.55)",
            }}
          />
          Sentiment
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
              color: "#c9a96e",
              fontWeight: 500,
              marginBottom: 28,
            }}
          >
            <div
              style={{
                width: 56,
                height: 1,
                background:
                  "linear-gradient(90deg, #c9a96e, rgba(201,169,110,0))",
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
              color: "#f2efe9",
            }}
          >
            <div style={{ display: "flex" }}>Read the market</div>
            <div style={{ display: "flex", gap: 28 }}>
              <span>before it</span>
              <span
                style={{
                  fontStyle: "italic",
                  color: "#c9a96e",
                  fontWeight: 500,
                }}
              >
                moves.
              </span>
            </div>
          </div>

          <div
            style={{
              marginTop: 38,
              fontSize: 30,
              lineHeight: 1.4,
              color: "#9e9890",
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
            color: "#6b6560",
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
                  border: "1px solid rgba(242,239,233,0.18)",
                  background: "rgba(242,239,233,0.04)",
                  color: "#f2efe9",
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
