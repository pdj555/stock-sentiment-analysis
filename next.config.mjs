/** @type {import('next').NextConfig} */
const nextConfig = {
  // Export a fully static client-side app. This lets Vercel treat the project
  // as "Other" (framework: null in vercel.json) so the root api/ directory is
  // scanned for the Python Serverless Function — Next.js projects only scan
  // app/api and pages/api, which cannot host Python.
  output: "export",
};

export default nextConfig;
