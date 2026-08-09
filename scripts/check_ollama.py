import ollama
import httpx

def check_ollama():
    try:
        models = ollama.list()
        print("✅ Ollama is running.")
        print("Models found:", models)
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print("Checking if we can reach it via httpx...")
        try:
            r = httpx.get("http://localhost:11434")
            print(f"Server reached: {r.status_code}")
        except Exception as e2:
            print(f"httpx failed: {e2}")

if __name__ == "__main__":
    check_ollama()
