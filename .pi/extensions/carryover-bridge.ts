import { type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import { Type } from "typebox";
import { StringEnum } from "@earendil-works/pi-ai";

export default function (pi: ExtensionAPI) {
  const evaluateFullness = (ctx: any) => {
    const entries = ctx.sessionManager.getEntries();
    return entries.length > 2000; // arbitrary threshold, increased to prevent annoying warnings
  };

  pi.on("session_start", async (event, ctx) => {
    const paneId = process.env.HERDR_PANE_ID || "";
    const tabId = process.env.HERDR_TAB_ID || "";
    const sessionId = process.env.PI_SESSION_ID || "default";
    const agentId = process.env.PI_AGENT_ID || "default";
    
    if (paneId && tabId) {
      spawn("bash", ["scripts/bin/pi-carryover-loader.sh", paneId, tabId, sessionId, agentId], {
        stdio: "ignore",
        detached: true
      }).unref();
    }
  });

  pi.on("turn_end", async (event, ctx) => {
    if (evaluateFullness(ctx)) {
      if (ctx.hasUI) {
         ctx.ui.notify("Session full. Please run /carryover to rotate context.", "warning");
      }
    }
  });

  pi.registerTool({
    name: "execute_carryover",
    label: "Execute Carryover",
    description: "Rotate the terminal pane to a new session after writing the carryover document.",
    parameters: Type.Object({
      mode: Type.Optional(StringEnum(["live", "sealed"] as const)),
      carryoverPath: Type.Optional(Type.String({ description: "Path to the written carryover markdown file" }))
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const paneId = process.env.HERDR_PANE_ID || "";
      const tabId = process.env.HERDR_TAB_ID || "";
      const sessionId = process.env.PI_SESSION_ID || "default";
      const agentId = process.env.PI_AGENT_ID || "default";

      if (!paneId || !tabId) {
        return { content: [{ type: "text", text: "Error: Not running in Herdr pane." }] };
      }

      const isSealed = params.mode === "sealed";
      
      if (isSealed) {
        spawn("bash", ["scripts/bin/pi-carryover-seal.sh", paneId, tabId, sessionId, agentId, params.carryoverPath || ""], {
          stdio: "ignore",
          detached: true
        }).unref();
      } else {
        spawn("python3", ["scripts/bin/pi-carryover-rotate.py", paneId, tabId, sessionId, agentId, params.carryoverPath || ""], {
          stdio: "ignore",
          detached: true
        }).unref();
      }

      return {
        content: [{ type: "text", text: isSealed ? "Session sealed." : "Carryover triggered. Pane will rotate shortly." }],
        details: {},
        terminate: true
      };
    }
  });

  pi.registerCommand("carryover", {
    description: "Carry over context to a new session (optional arg: sealed)",
    handler: async (args, ctx) => {
      if (!ctx.isIdle()) {
        ctx.ui.notify("Agent is busy.", "warning");
        return;
      }
      
      const mode = args.trim().toLowerCase() === "sealed" ? "sealed" : "live";
      const sessionId = process.env.PI_SESSION_ID || "default";
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

      const prompt = `We are doing a context carryover. 

1. Generate a descriptive, session-scoped filename for the carryover document, formatted like \`context-carryover-<branch-or-topic>-${sessionId}.md\` (do NOT use a flat \`baton.md\` name). 
2. Write a comprehensive carryover document to that file using the battle-tested Claude carryover template. It MUST include:
   - Date, Branch, Feature/Topic
   - Current Round / Next Round
   - Spec Metrics & File Paths
   - Exact Active State & Progress (What was just done, what broke)
   - Exact Next Steps (What the next session needs to do immediately)
3. After successfully writing the file using the \`write\` tool, call the \`execute_carryover\` tool with \`{ "mode": "${mode}", "carryoverPath": "<the-file-you-wrote>" }\`.`;

      pi.sendUserMessage(prompt);
    }
  });
}
