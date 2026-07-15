import { request } from "../request";
import type { MemoryEvalReport, MemoryEvalRequest } from "../types/eval";

export const evalApi = {
  runMemoryEval: (body: MemoryEvalRequest = {}) =>
    request<MemoryEvalReport>("/evals/memory", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

