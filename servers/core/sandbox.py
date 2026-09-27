import asyncio
import logging
from typing import Any
from pathlib import Path
from shared.config import get_settings

logger = logging.getLogger("mcp.core.sandbox")

class PersistentDockerSandbox:
    """
    Menyediakan persistent execution sandbox menggunakan Docker.
    Ini menggantikan eksekusi subprocess lokal dengan container ephemeral
    yang menjaga state (seperti node_modules & venv) selama satu lifecycle.
    """
    
    def __init__(self, session_id: str, image: str = "node:20-bullseye"):
        self.session_id = f"mcp_sandbox_{session_id}"
        self.image = image
        self.is_running = False
        
        # Ambil whitelist cwd utama (workspace)
        try:
            self.host_workspace = Path(get_settings().allowed_directories[0]).resolve()
        except IndexError:
            self.host_workspace = Path.cwd() / "workspace"
            
        self.container_workspace = "/workspace"

    async def start(self):
        """Memulai container di background agar state persisten."""
        if self.is_running:
            return
            
        logger.info(f"Membangun Persistent Sandbox: {self.session_id}")
        
        # Pastikan direktori host ada
        self.host_workspace.mkdir(parents=True, exist_ok=True)
        
        # Jalankan docker container mode tail -f (sleep infinite)
        cmd = [
            "docker", "run", "-d", "--rm", 
            "--name", self.session_id,
            "-v", f"{self.host_workspace}:{self.container_workspace}",
            "-w", self.container_workspace,
            self.image,
            "tail", "-f", "/dev/null"
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        
        if proc.returncode == 0:
            self.is_running = True
            logger.info("Sandbox berhasil diamankan.")
        else:
            raise RuntimeError(f"Gagal memulai sandbox Docker {self.session_id}")

    async def execute(self, command: str, timeout: int = 60) -> dict[str, Any]:
        """Eksekusi perintah bash ke dalam container yang sudah aktif."""
        if not self.is_running:
            raise RuntimeError("Sandbox belum berjalan.")
            
        logger.info(f"Sandbox Execute: {command}")
        
        # Bungkus perintah untuk dieksekusi dalam bash (menangani &&, pipeline secara aman di container)
        cmd = ["docker", "exec", self.session_id, "bash", "-c", command]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"success": False, "error": f"Timeout {timeout}s"}
            
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace")
        }

    async def stop(self):
        """Menghancurkan container setelah sesi agent selesai."""
        if not self.is_running:
            return
            
        logger.info(f"Menghancurkan Sandbox: {self.session_id}")
        cmd = ["docker", "stop", self.session_id]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        self.is_running = False
