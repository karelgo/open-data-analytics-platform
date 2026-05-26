"""Nanitics Observatory wired to Azure AI Foundry, deployed on the UWV
data platform.

Exposes four agent types behind individual endpoints so the Observatory
trace viewer can render its agent-specific views (ReAct, ReWOO plan,
Reflexion retry, LATS MCTS tree):

    POST /run                  — legacy alias for /run/react
    POST /run/react            — ReActAgent
    POST /run/rewoo            — ReWOOAgent (plan-first, parallel steps)
    POST /run/reflexion        — ReflexionAgent (evaluate-reflect-retry)
    POST /run/lats             — LATSAgent (MCTS tree search)
    GET  /agents               — list available agent types
    GET  /health               — liveness probe

LLM provider modes (LLM_PROVIDER env):

    azure-foundry (default)   — Azure AI Foundry serverless /openai/v1/
    mock                      — scripted MockLLMClient (key-free smoke)

The Observatory UI is served at /api/observatory/ from the embedded
React bundle baked into the image at /srv/observatory-ui.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from nanitics import (
    EvaluationCheck,
    EvaluationContext,
    EvaluationResult,
    EvaluationVerdict,
    InMemoryEmitter,
    InMemoryEpisodeStore,
    InMemoryPersistentTraceStore,
    InMemoryPlanStore,
    LATSAgent,
    LLMClient,
    LLMResponse,
    MockEmbeddingClient,
    MockLLMClient,
    OpenAILLMClient,
    ProgrammaticEvaluator,
    ReActAgent,
    ReflexionAgent,
    ReWOOAgent,
    ToolCall,
    TraceCollector,
    TracedExecutor,
    Usage,
    tool,
)
from nanitics.observatory import create_observatory_router

from watcher import WATCHER_DEFAULT_TASK, WATCHER_SYSTEM_PROMPT, WATCHER_TOOLS

LOG = logging.getLogger("nanitics-observatory")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

UI_DIR = Path("/srv/observatory-ui")
# Image lays out static next to app.py at /srv/static (see Dockerfile).
# Fall back to local-dev path next to app.py for non-container runs.
STATIC_DIR = Path("/srv/static") if Path("/srv/static").exists() else Path(__file__).parent / "static"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "azure-foundry").lower()
MODEL = os.environ.get("LLM_MODEL", "gpt-4o")


# ---------------------------------------------------------------------------
# Tools — generic enough for every agent type to use.
# ---------------------------------------------------------------------------


@tool("greet", "Greet someone or some team by name.")
async def greet(name: str) -> str:
    return f"Hallo, {name}!"


@tool("describe_platform", "Describe the UWV reference data platform layout.")
async def describe_platform() -> str:
    return (
        "UWV reference data platform on k3d. Namespaces: odap-platform "
        "(portal, ingress), odap-data (Trino/Spark/Hive), odap-meta "
        "(metastore, catalogs), odap-monitoring, odap-auth (Keycloak). "
        "Storage: MinIO S3. Auth: Keycloak via oauth2-proxy."
    )


@tool("search", "Search a topic and return short notes.")
async def search(query: str) -> str:
    """Stub — replace with a real source (web, docs, internal wiki)."""
    return f"Notes on '{query}': key facts, definitions, relevant context."


@tool("summarize", "Summarize the given text into one sentence.")
async def summarize(text: str) -> str:
    """Stub — in production this would call a tool/library, not the LLM."""
    snippet = text.strip().replace("\n", " ")[:80]
    return f"Summary: {snippet}..."


@tool("analyze", "Analyze the given data and report findings.")
async def analyze(data: str) -> str:
    """Stub — replace with real analytics (DataFrame ops, SQL aggregates)."""
    return f"Analysis: data appears coherent. Sample: {data[:60]}"


ALL_TOOLS = [greet, describe_platform, search, summarize, analyze]


# ---------------------------------------------------------------------------
# Evaluators — used by Reflexion and LATS to score outputs.
# ---------------------------------------------------------------------------


class LATSNodeEvaluator:
    """OutputEvaluator for LATS — accepts on DONE, rejects on dead-end markers.

    Implements the OutputEvaluator protocol directly because LATS depends
    on all three verdicts (ACCEPT, REVISE, REJECT) and score granularity.
    """

    max_revisions = 0  # LATS doesn't use the revision loop.

    async def evaluate(self, output: str, context: EvaluationContext) -> EvaluationResult:
        del context  # unused
        lower = output.lower()
        if "done." in lower or "final answer:" in lower or "## answer" in lower:
            return EvaluationResult(
                verdict=EvaluationVerdict.ACCEPT,
                score=1.0,
                evaluator_name="lats",
            )
        if "dead end" in lower or "stuck" in lower or "cannot proceed" in lower:
            return EvaluationResult(
                verdict=EvaluationVerdict.REJECT,
                score=0.0,
                evaluator_name="lats",
            )
        return EvaluationResult(
            verdict=EvaluationVerdict.REVISE,
            score=0.6,
            evaluator_name="lats",
        )


def _make_reflexion_evaluator() -> ProgrammaticEvaluator:
    """Hard requirement: output must be substantive (>= 60 chars).

    Forces at least one reflection-and-retry on lazy LLM responses.
    """
    return ProgrammaticEvaluator(
        checks=[
            EvaluationCheck(
                name="substantive_output",
                check=lambda output: len(output.strip()) >= 60,
                feedback="Output must be at least 60 characters of useful content.",
            )
        ],
    )


# ---------------------------------------------------------------------------
# LLM client factory.
# ---------------------------------------------------------------------------


def _make_mock_client() -> MockLLMClient:
    """Two-turn ReAct script — used only when LLM_PROVIDER=mock."""
    usage = Usage(input_tokens=0, output_tokens=0)
    return MockLLMClient(
        responses=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="call-1", name="greet", arguments={"name": "UWV"})],
                usage=usage,
                model="mock",
                stop_reason="tool_use",
            ),
            LLMResponse(
                content="Hallo, UWV!",
                usage=usage,
                model="mock",
                stop_reason="end_turn",
            ),
        ]
    )


def _make_azure_foundry_client() -> OpenAILLMClient:
    endpoint = os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT", "").rstrip("/")
    api_key = os.environ.get("AZURE_AI_FOUNDRY_API_KEY")
    if not endpoint:
        raise RuntimeError(
            "LLM_PROVIDER=azure-foundry but AZURE_AI_FOUNDRY_ENDPOINT is unset."
        )
    if not api_key:
        raise RuntimeError(
            "LLM_PROVIDER=azure-foundry but AZURE_AI_FOUNDRY_API_KEY is unset."
        )
    if not endpoint.endswith("/openai/v1") and not endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/openai/v1"
    return OpenAILLMClient(model=MODEL, api_key=api_key, base_url=endpoint)


def _make_llm_client() -> LLMClient:
    if LLM_PROVIDER == "mock":
        return _make_mock_client()
    if LLM_PROVIDER == "azure-foundry":
        return _make_azure_foundry_client()
    raise RuntimeError(
        f"Unknown LLM_PROVIDER={LLM_PROVIDER!r}. Supported: azure-foundry, mock."
    )


# ---------------------------------------------------------------------------
# FastAPI shell.
# ---------------------------------------------------------------------------

store = InMemoryPersistentTraceStore()
executor = TracedExecutor(store)
app = FastAPI(title="Nanitics Observatory — UWV data platform")
app.include_router(
    create_observatory_router(store, static_dir=UI_DIR if UI_DIR.exists() else None),
    prefix="/api/observatory",
)


class RunRequest(BaseModel):
    task: str = "Greet the UWV team and describe the platform briefly."


SYSTEM_PROMPT = (
    "You are an assistant for the UWV data platform. "
    "Use the available tools when relevant. Be concise."
)


# ---------------------------------------------------------------------------
# Per-agent run helpers.
# ---------------------------------------------------------------------------


async def _run_react(emitter: Any, task: str) -> str:
    agent = ReActAgent(
        name="react",
        llm_client=_make_llm_client(),
        emitter=emitter,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
    return (await agent.run(task)).output


async def _run_rewoo(emitter: Any, task: str) -> str:
    agent = ReWOOAgent(
        name="rewoo",
        llm_client=_make_llm_client(),
        emitter=emitter,
        tools=[search, summarize, analyze, describe_platform],
        plan_store=InMemoryPlanStore(),
        system_prompt=(
            SYSTEM_PROMPT
            + " First plan the steps, then execute them. "
            "Independent steps will run in parallel."
        ),
    )
    return (await agent.run(task)).output


async def _run_reflexion(emitter: Any, task: str) -> str:
    inner = ReActAgent(
        name="reflexion-inner",
        llm_client=_make_llm_client(),
        emitter=emitter,  # rebound by Reflexion at attempt start
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )
    agent = ReflexionAgent(
        name="reflexion",
        llm_client=_make_llm_client(),
        emitter=emitter,
        system_prompt=SYSTEM_PROMPT + " Use reflection between attempts.",
        inner_agent=inner,
        evaluator=_make_reflexion_evaluator(),
        episode_store=InMemoryEpisodeStore(embedding_client=MockEmbeddingClient()),
        max_attempts=3,
    )
    return (await agent.run(task)).output


async def _run_lats(emitter: Any, task: str) -> str:
    agent = LATSAgent(
        name="lats",
        llm_client=_make_llm_client(),
        emitter=emitter,
        tools=[search, summarize, analyze, describe_platform],
        node_evaluator=LATSNodeEvaluator(),
        # Small values keep the demo cheap (gpt-4o calls cost real money).
        max_iterations=2,
        max_depth=2,
        branching_factor=2,
        system_prompt=(
            SYSTEM_PROMPT
            + " Explore multiple solution paths. End your final answer with 'DONE.'"
        ),
    )
    return (await agent.run(task)).output


async def _run_watcher(emitter: Any, task: str) -> str:
    agent = ReActAgent(
        name="odap-platform-watcher",
        llm_client=_make_llm_client(),
        emitter=emitter,
        tools=[describe_platform, *WATCHER_TOOLS],
        system_prompt=WATCHER_SYSTEM_PROMPT,
    )
    return (await agent.run(task)).output


AGENTS: dict[str, dict[str, Any]] = {
    "react": {
        "label": "ReAct",
        "description": "Reason → Act → Observe loop. Single linear path.",
        "default_task": "Greet the UWV team and describe the platform.",
        "run": _run_react,
    },
    "rewoo": {
        "label": "ReWOO",
        "description": "Plan-first with parallel execution. Only 2 LLM calls.",
        "default_task": (
            "Search for 'data lakehouse' and 'data warehouse', summarize each, "
            "then write one sentence comparing them."
        ),
        "run": _run_rewoo,
    },
    "reflexion": {
        "label": "Reflexion",
        "description": "Evaluate → reflect → retry loop with episodic memory.",
        "default_task": (
            "Describe the UWV data platform's storage layer in at least one paragraph."
        ),
        "run": _run_reflexion,
    },
    "lats": {
        "label": "LATS (MCTS)",
        "description": "Monte-Carlo Tree Search with UCB1 selection and pruning.",
        "default_task": (
            "Find the most useful tool to introspect the UWV platform. "
            "End with DONE."
        ),
        "run": _run_lats,
    },
    "watcher": {
        "label": "Platform watcher",
        "description": (
            "Investigates platform health signals and files a Multica task "
            "in the platform-ops workspace when a real issue is found. "
            "Tasks are filed without the 'approved' label — a human must "
            "approve before any coding agent can claim the work."
        ),
        "default_task": WATCHER_DEFAULT_TASK,
        "run": _run_watcher,
    },
}


# ---------------------------------------------------------------------------
# HTTP endpoints.
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Bare hostname → chat UI. Avoids the 'nginx 404' confusion when
    someone opens https://nanitics.odap.local:8443/ without
    knowing the right path."""
    return RedirectResponse(url="/chat", status_code=307)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm_provider": LLM_PROVIDER,
        "model": MODEL,
        "agents": ",".join(AGENTS.keys()),
    }


@app.get("/agents")
async def list_agents() -> list[dict[str, str]]:
    return [
        {
            "slug": slug,
            "label": meta["label"],
            "description": meta["description"],
            "default_task": meta["default_task"],
            "endpoint": f"/run/{slug}",
        }
        for slug, meta in AGENTS.items()
    ]


async def _execute(agent_slug: str, body: RunRequest) -> dict[str, str]:
    if agent_slug not in AGENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent {agent_slug!r}. Available: {','.join(AGENTS.keys())}",
        )

    runner = AGENTS[agent_slug]["run"]

    async def _work(emitter, run_id):  # type: ignore[no-untyped-def]
        del run_id
        return await runner(emitter, body.task)

    run_id, result = await executor.execute(
        _work,
        metadata={
            "source": "odap-platform",
            "provider": LLM_PROVIDER,
            "agent_type": agent_slug,
        },
    )
    return {"run_id": run_id, "agent_type": agent_slug, "result": str(result)}


@app.post("/run")
async def run_legacy(body: RunRequest) -> dict[str, str]:
    """Legacy endpoint — defaults to ReAct for backward compatibility."""
    return await _execute("react", body)


@app.post("/run/{agent_slug}")
async def run_agent(agent_slug: str, body: RunRequest) -> dict[str, str]:
    return await _execute(agent_slug, body)


# ---------------------------------------------------------------------------
# Async run + chat UI — streaming surface for /chat.
#
# The synchronous /run/{slug} above blocks until the agent finishes. For the
# chat UI we need real-time event streaming, so we kick the run off as a
# background task, return run_id immediately, and let the client tail the
# existing Observatory SSE endpoint at /api/observatory/runs/{id}/stream.
# ---------------------------------------------------------------------------


async def _execute_in_background(agent_slug: str, body: RunRequest) -> str:
    """Mimic TracedExecutor.execute() but return run_id BEFORE work completes.

    The agent runs as an asyncio.Task; events stream into the trace store
    through TraceCollector exactly as in the synchronous path. The Observatory
    SSE endpoint can then tail the store and surface events live to a browser.
    """
    if agent_slug not in AGENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent {agent_slug!r}. Available: {','.join(AGENTS.keys())}",
        )
    runner = AGENTS[agent_slug]["run"]

    run_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    metadata = {
        "source": "odap-platform",
        "provider": LLM_PROVIDER,
        "agent_type": agent_slug,
        "surface": "chat-stream",
    }
    await store.register_run(run_id, trace_id, metadata)

    emitter = InMemoryEmitter(trace_id=trace_id)
    collector = TraceCollector(store=store, parent_id=run_id)
    emitter.add_listener(collector.handle)

    async def _runner() -> None:
        try:
            result = await runner(emitter, body.task)
            await collector.close()
            await store.update_run_status(run_id, "completed", result=str(result))
        except Exception as exc:  # noqa: BLE001
            LOG.exception("Agent run %s failed", run_id)
            try:
                await collector.close()
            finally:
                await store.update_run_status(run_id, "failed", error=str(exc))

    asyncio.create_task(_runner())  # noqa: RUF006 — fire-and-forget by design
    return run_id


@app.post("/run/{agent_slug}/stream")
async def run_agent_streaming(agent_slug: str, body: RunRequest) -> dict[str, str]:
    """Kick off an agent run asynchronously; return run_id immediately.

    Pair with: GET /api/observatory/runs/{run_id}/stream  (SSE)
              GET /api/observatory/runs?limit=1            (final result)
    """
    run_id = await _execute_in_background(agent_slug, body)
    return {
        "run_id": run_id,
        "agent_type": agent_slug,
        "status": "running",
        "stream_url": f"/api/observatory/runs/{run_id}/stream",
    }


@app.get("/chat", response_class=HTMLResponse)
async def chat_ui() -> HTMLResponse:
    """Serve the SSE-streaming chat page baked into the image."""
    chat_html = STATIC_DIR / "chat.html"
    if not chat_html.exists():
        raise HTTPException(status_code=500, detail="chat.html not bundled into image")
    return HTMLResponse(content=chat_html.read_text(encoding="utf-8"))
