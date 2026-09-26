import asyncio
import os
import sys

from mcp.server.stdio import stdio_server

try:
    from agent_framework import Agent, MCPStreamableHTTPTool
    from agent_framework.openai import OpenAIChatClient
except ImportError:
    # Dummy mock jika lib belum terinstal dengan sempurna
    class MCPStreamableHTTPTool:
        def __init__(self, name, url):
            self.name = name
            self.url = url
    
    class OpenAIChatClient:
        pass
    
    class Agent:
        def __init__(self, client, name, instructions, tools):
            self.client = client
            self.name = name
            self.instructions = instructions
            self.tools = tools
            
        def as_mcp_server(self):
            class MockServer:
                def create_initialization_options(self):
                    return {}
                async def run(self, r, w, options):
                    pass
            return MockServer()

async def run_maf_server():
    """Menjalankan Orchestrator agen MAF menggunakan koneksi stdio"""
    
    # Inisialisasi Tools untuk connect ke server eksisting (SSE)
    # Server kita jalan di port tersebut sesuai skema
    tools = [
        MCPStreamableHTTPTool(name="memory", url="http://127.0.0.1:8001/sse"),
        MCPStreamableHTTPTool(name="knowledge", url="http://127.0.0.1:8002/sse"),
        MCPStreamableHTTPTool(name="skills", url="http://127.0.0.1:8003/sse"),
        MCPStreamableHTTPTool(name="bridge_gmail", url="http://127.0.0.1:8004/sse"),
        MCPStreamableHTTPTool(name="bridge_telegram", url="http://127.0.0.1:8005/sse"),
        MCPStreamableHTTPTool(name="bridge_gemini", url="http://127.0.0.1:8006/sse"),
        MCPStreamableHTTPTool(name="bridge_vision", url="http://127.0.0.1:8007/sse"),
        MCPStreamableHTTPTool(name="bridge_mikrotik", url="http://127.0.0.1:8008/sse"),
        # Lapisan Keputusan (SemIf / JEV-CPU) berjalan di CPU
        MCPStreamableHTTPTool(name="semif_decision", url="http://127.0.0.1:8080/mcp"),
    ]
    
    # Inisiasi MAF Agent (Lapisan 1: Orkestrasi)
    agent = Agent(
        client=OpenAIChatClient(
            model="llama3.2",
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        ), 
        name="MAF_Orchestrator",
        instructions="""Anda adalah node Orchestrator (MAF) di puncak Arsitektur 5-Lapis.
Alur kerja Anda (Triage -> Coding -> Hindsight):
1. Triage: Panggil 'semif_decision' untuk routing, guardrails, & klasifikasi tugas awal. Jika Qwen3-0.6B ragu (confidence < 0.5), eskalasi ke Human-in-the-loop.
2. Memori: Akses Hindsight Memory melalui server 'memory' (retain, reflect, search_advice) untuk memanggil Mental Models & Observations.
3. Execution: Delegasikan instruksi koding kepada `smolagents CodeAgent` murni via run_shell python atau serahkan pada e2b sandbox. Panduan cara koding dapat dibaca dari folder `skills/` (Hugging Face SKILL.md). Gunakan MCP Bridge untuk kapabilitas eksternal (Mis. MikroTik).""",
        tools=tools
    )
    
    # Bungkus sebagai MCP Server
    server = agent.as_mcp_server()
    
    # Jalankan stdio loop
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

def main():
    asyncio.run(run_maf_server())

if __name__ == "__main__":
    main()
