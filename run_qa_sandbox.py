import asyncio
from servers.core.sandbox import PersistentDockerSandbox
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

async def main():
    import uuid
    sid = "qa_" + str(uuid.uuid4())[:8]
    sandbox = PersistentDockerSandbox(session_id=sid, image="node:20-bullseye")
    sandbox.host_workspace = Path("/home/aseps/MCP/workspace")
    await sandbox.start()
    try:
        print("\n--- MENJALANKAN NPM INSTALL DI DALAM DOCKER SANDBOX ---")
        res_install = await sandbox.execute("cd Projects/TodoApp && npm install express node-fetch@2")
        print("Install stdout:", res_install["stdout"])
        if not res_install["success"]:
            print("Install stderr:", res_install["stderr"])

        print("\n--- MENJALANKAN QA TEST DI DALAM DOCKER SANDBOX ---")
        res_test = await sandbox.execute("cd Projects/TodoApp && npm test")
        print("Test stdout:", res_test["stdout"])
        if not res_test["success"]:
            print("Test stderr:", res_test["stderr"])
    finally:
        await sandbox.stop()
        print("\n--- DOCKER SANDBOX DIHANCURKAN ---")

if __name__ == "__main__":
    asyncio.run(main())
