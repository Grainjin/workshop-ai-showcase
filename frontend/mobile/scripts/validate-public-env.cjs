// Expo bundles client modules without executing them. Fail public exports before
// bundling as well as validating again in src/config/env.ts at runtime.
if (process.env.EXPO_PUBLIC_PUBLIC_DEPLOYMENT === "true") {
  const origins = [
    ["EXPO_PUBLIC_API_BASE_URL", "https:"],
    ["EXPO_PUBLIC_WS_BASE_URL", "wss:"],
  ];
  try {
    if (process.env.EXPO_PUBLIC_DEMO_MODE !== "true") throw new Error();
    for (const [name, protocol] of origins) {
      const url = new URL(process.env[name] ?? "");
      if (url.protocol !== protocol || !url.hostname || url.username || url.password ||
          !["", "/"].includes(url.pathname) || url.search || url.hash) throw new Error();
    }
  } catch {
    console.error("Public Web export requires EXPO_PUBLIC_DEMO_MODE=true and explicit HTTPS API / WSS origins.");
    process.exit(1);
  }
}
