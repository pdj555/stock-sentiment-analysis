import { initBotId } from "botid/client/core";

initBotId({
  protect: [{ path: "/api/analyze", method: "POST" }],
});
