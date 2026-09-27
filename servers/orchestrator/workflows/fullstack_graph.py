from dataclasses import dataclass, field
from typing import Literal
import uuid

from shared.logging import get_logger
from servers.core.sandbox import PersistentDockerSandbox

logger = get_logger("mcp.orchestrator.workflows.fullstack")

@dataclass
class WorkflowState:
    task_description: str
    current_phase: Literal["ARCHITECT", "BACKEND", "FRONTEND", "QA", "DONE"] = "ARCHITECT"
    context_summaries: list[str] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)
    qa_retry_count: int = 0
    max_retries: int = 2

class FullstackAgenticWorkflow:
    """
    Deterministic State Machine for Full-Stack App Development.
    Protects against Context Bloat, infinite loops, and RAG Poisoning.
    """
    
    def __init__(self):
        # We will inject the SemIf (Decision) validator here,
        # and the MCP suite clients for actual execution.
        pass

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

    async def run_qa_phase(self, state: WorkflowState, sandbox: PersistentDockerSandbox) -> WorkflowState:
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

    async def execute(self, task_description: str):
        state = WorkflowState(task_description=task_description)
        
        # Inisiasi Lifecycle Sandbox Persisten (Dibangun sekali per sesi)
        sandbox = PersistentDockerSandbox(session_id=str(uuid.uuid4())[:8])
        await sandbox.start()
        
        try:
            while state.current_phase != "DONE":
                if state.current_phase == "ARCHITECT":
                    state = await self.run_architect_phase(state)
                elif state.current_phase == "BACKEND":
                    state = await self.run_backend_phase(state)
                elif state.current_phase == "FRONTEND":
                    state = await self.run_frontend_phase(state)
                elif state.current_phase == "QA":
                    state = await self.run_qa_phase(state, sandbox)
        finally:
            # Hancurkan sandbox setelah tugas selesai (mencegah memory leak / dangling container)
            await sandbox.stop()
            
        logger.info("Workflow completed.")
        return state

if __name__ == "__main__":
    import asyncio
    workflow = FullstackAgenticWorkflow()
    asyncio.run(workflow.execute("Build a simple CRUD API and a To-Do UI."))
