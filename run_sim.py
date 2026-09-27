import asyncio
from shared.logging import configure_logging
from servers.orchestrator.workflows.fullstack_graph import FullstackAgenticWorkflow

async def main():
    configure_logging("INFO")
    print("\n--- MEMULAI SIMULASI END-TO-END FULLSTACK FLOW ---\n")
    workflow = FullstackAgenticWorkflow()
    # Pancing orkestrator
    state = await workflow.execute("Build a simple CRUD API and a To-Do UI.")
    print("\n--- HASIL AKHIR STATE WORKFLOW ---")
    print(f"Current Phase: {state.current_phase}")
    print(f"Retries: {state.qa_retry_count}")
    print("Summaries:")
    for summary in state.context_summaries:
        print(f" -> {summary}")

if __name__ == "__main__":
    asyncio.run(main())
