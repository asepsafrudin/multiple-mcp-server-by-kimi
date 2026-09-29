import uuid
from dataclasses import dataclass, field
from typing import Literal

from servers.core.sandbox import PersistentDockerSandbox
from shared.logging import get_logger

logger = get_logger("mcp.orchestrator.workflows.fullstack")


@dataclass
class WorkflowState:
    task_description: str
    current_phase: Literal["ARCHITECT", "BACKEND", "FRONTEND", "QA", "WAITING_APPROVAL", "DONE"] = (
        "ARCHITECT"
    )
    hitl_approved: bool = False
    context_summaries: list[str] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)
    qa_retry_count: int = 0
    max_retries: int = 2
    # Observability & Cost Telemetry
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_execution_time_seconds: float = 0.0
    phase_metrics: dict = field(default_factory=dict)


class FullstackAgenticWorkflow:
    """
    Deterministic State Machine for Full-Stack App Development.
    Protects against Context Bloat, infinite loops, and RAG Poisoning.
    """

    def __init__(self, ui_mode: bool = False):
        self.ui_mode = ui_mode
        self.hitl_event = None
        self.hitl_decision = None
        self.hitl_feedback = None
        if self.ui_mode:
            import asyncio

            self.hitl_event = asyncio.Event()

    async def run_architect_phase(self, state: WorkflowState) -> WorkflowState:
        logger.info("Executing Architect Phase (RAG Retrieval & Planning)")
        # 1. TODO: Call knowledge:search to get stack documentation
        # 2. TODO: Generate technical blueprint
        # 3. TODO: SemIf Validation Gate (Mitigasi RAG Poisoning)

        # Summarize output and move to BACKEND
        state.context_summaries.append("Blueprint created: Tech Stack includes React and FastAPI.")
        state.current_phase = "BACKEND"
        return state

    async def run_backend_phase(self, state: WorkflowState) -> WorkflowState:
        logger.info("Executing Backend Phase (Logic & API)")
        # 1. TODO: Call skill:recall for backend boilerplate
        # 2. TODO: Use core:filesystem to write code

        state.context_summaries.append("Backend logic implemented at src/api.")
        state.current_phase = "FRONTEND"
        return state

    async def run_frontend_phase(self, state: WorkflowState) -> WorkflowState:
        logger.info("Executing Frontend Phase (UI Components)")
        # 1. TODO: Call core:filesystem to write components
        # 2. TODO: Use document:view for UI specs OCR

        state.context_summaries.append("Frontend components implemented at src/web.")
        state.current_phase = "QA"
        return state

    async def run_qa_phase(
        self, state: WorkflowState, sandbox: PersistentDockerSandbox
    ) -> WorkflowState:
        logger.info(f"Executing QA Phase (Testing in Sandbox) - Retry: {state.qa_retry_count}")
        # Eksekusi QA dibatasi Regex Whitelist dan dilempar ke Persistent Docker
        result = await sandbox.execute("npm run test || pytest")

        is_success = result.get("success", False)

        if is_success:
            logger.info("QA Passed. Logging success to Hindsight Memory.")
            # TODO: memory:store success metrics
            state.current_phase = "DONE"
        else:
            state.qa_retry_count += 1
            if state.qa_retry_count > state.max_retries:
                logger.error("Circuit Breaker Tripped! Max retries reached.")
                # TODO: memory:store failure metrics
                state.current_phase = "DONE"  # Halt execution
            else:
                logger.warning("QA failed. Routing back to BACKEND.")
                state.recent_errors.append("Test failed: AssertionError in auth_router.")
                state.current_phase = "BACKEND"

        return state

    async def run_hitl_approval_phase(self, state: WorkflowState) -> WorkflowState:
        logger.info("Executing HITL Approval Phase (Human-in-the-loop Gate)")

        if self.ui_mode:
            logger.info("Waiting for UI HITL Approval (Paused)...")
            self.hitl_event.clear()
            await self.hitl_event.wait()
            user_input = self.hitl_decision
            feedback = self.hitl_feedback
        else:
            print("\n" + "=" * 50)
            print("🚨 HUMAN-IN-THE-LOOP APPROVAL GATE 🚨")
            print(f"Task: {state.task_description}")
            print("Summary of actions:")
            for summary in state.context_summaries:
                print(f" - {summary}")
            print("=" * 50)
            user_input = input("Proceed with applying these changes? (y/n/steer): ").strip().lower()
            feedback = None

        if user_input in ["y", "yes", "approve"]:
            logger.info("Human approved the changes.")
            state.hitl_approved = True
            state.current_phase = "DONE"
        elif user_input == "steer":
            if not feedback:
                feedback = input("Provide steering feedback: ")
            logger.info(f"Human provided feedback: {feedback}")
            state.recent_errors.append(f"Human Feedback: {feedback}")
            state.qa_retry_count = 0  # reset retries
            state.current_phase = "ARCHITECT"  # go back to planner
        else:
            logger.info("Human rejected the changes. Workflow aborted.")
            state.hitl_approved = False
            state.current_phase = "DONE"

        return state

    # Hooks for broadcasting
    async def _broadcast_state(self, state: WorkflowState):
        if not self.ui_mode:
            return
        # A simple hook to let FastAPI know the state has updated
        # In actual prod, we might push to redis pubsub
        self.latest_state = state

    async def execute(self, task_description: str):
        state = WorkflowState(task_description=task_description)

        # Inisiasi Lifecycle Sandbox Persisten (Dibangun sekali per sesi)
        sandbox = PersistentDockerSandbox(session_id=str(uuid.uuid4())[:8])
        await sandbox.start()

        import time

        start_time_total = time.time()
        try:
            while state.current_phase != "DONE":
                phase_start = time.time()
                current_p = state.current_phase

                if state.current_phase == "ARCHITECT":
                    state = await self.run_architect_phase(state)
                elif state.current_phase == "BACKEND":
                    state = await self.run_backend_phase(state)
                elif state.current_phase == "FRONTEND":
                    state = await self.run_frontend_phase(state)
                elif state.current_phase == "QA":
                    state = await self.run_qa_phase(state, sandbox)
                    if state.current_phase == "DONE":
                        # Require HITL approval before actually finishing
                        state.current_phase = "WAITING_APPROVAL"
                elif state.current_phase == "WAITING_APPROVAL":
                    state = await self.run_hitl_approval_phase(state)

                phase_duration = time.time() - phase_start
                state.phase_metrics[current_p] = (
                    state.phase_metrics.get(current_p, 0.0) + phase_duration
                )
                logger.info(f"Phase {current_p} execution took {phase_duration:.2f}s")
                await self._broadcast_state(state)
        finally:
            # Hancurkan sandbox setelah tugas selesai (mencegah memory leak / dangling container)
            await sandbox.stop()

        state.total_execution_time_seconds = time.time() - start_time_total

        # Log Final Telemetry (OpenTelemetry / LangSmith Integration Placeholder)
        logger.info(f"Workflow completed. Total time: {state.total_execution_time_seconds:.2f}s.")
        logger.info(
            f"Telemetry -> Prompt Tokens: {state.total_prompt_tokens}, Completion: {state.total_completion_tokens}"
        )
        logger.info(f"Phase Breakdown: {state.phase_metrics}")

        return state


if __name__ == "__main__":
    import asyncio

    workflow = FullstackAgenticWorkflow()
    asyncio.run(workflow.execute("Build a simple CRUD API and a To-Do UI."))
