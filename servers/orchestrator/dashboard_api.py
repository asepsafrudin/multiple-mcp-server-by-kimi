import asyncio
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import time

from servers.orchestrator.workflows.fullstack_graph import FullstackAgenticWorkflow

app = FastAPI(title="Agentic Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singleton for demonstration of single-tenant UI
workflow_instance = None
workflow_task = None

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/state")
async def get_state():
    """Retrieve the current state of the global workflow."""
    if not workflow_instance:
        return {"status": "idle", "state": None}
    
    state = getattr(workflow_instance, 'latest_state', None)
    if not state:
        return {"status": "running", "state": None}
        
    return {
        "status": "running" if state.current_phase != "DONE" else "completed",
        "current_phase": state.current_phase,
        "task_description": state.task_description,
        "context_summaries": state.context_summaries,
        "total_execution_time_seconds": getattr(state, 'total_execution_time_seconds', 0),
        "total_prompt_tokens": getattr(state, 'total_prompt_tokens', 0),
        "total_completion_tokens": getattr(state, 'total_completion_tokens', 0),
        "phase_metrics": getattr(state, 'phase_metrics', {}),
        "recent_errors": state.recent_errors
    }

@app.post("/api/start")
async def start_workflow(task_description: str, background_tasks: BackgroundTasks):
    """Start a new workflow execution in the background."""
    global workflow_instance, workflow_task
    
    if workflow_instance and getattr(workflow_instance, 'latest_state', None) and workflow_instance.latest_state.current_phase != "DONE":
        raise HTTPException(status_code=400, detail="A workflow is already running")
        
    workflow_instance = FullstackAgenticWorkflow(ui_mode=True)
    
    # helper for background run since execute is async
    async def run_task():
        await workflow_instance.execute(task_description)
        
    background_tasks.add_task(asyncio.create_task, run_task())
    return {"status": "started", "task_description": task_description}

@app.post("/api/hitl")
async def hitl_decision(decision: str, feedback: str = ""):
    """Provide HITL decision: 'approve', 'reject', 'steer'"""
    global workflow_instance
    if not workflow_instance:
        raise HTTPException(status_code=400, detail="No active workflow")
    
    state = getattr(workflow_instance, 'latest_state', None)
    if not state or state.current_phase != "WAITING_APPROVAL":
        raise HTTPException(status_code=400, detail="Workflow is not waiting for approval")
    
    if decision not in ['approve', 'reject', 'steer']:
        raise HTTPException(status_code=400, detail="Invalid decision")
        
    workflow_instance.hitl_decision = decision
    workflow_instance.hitl_feedback = feedback
    workflow_instance.hitl_event.set()
    
    return {"status": "decision_submitted", "decision": decision}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
