import asyncio

from servers.memory import hindsight_engine


async def run_test():
    # 1. Pastikan database dan schema terbuat tanpa exception
    print("[*] Inisiasi...")

    # 2. Store dummy experience
    print("[*] Menyimpan Experience...")
    exp = await hindsight_engine.store_experience(
        task_description="Testing koneksi ke RouterOS memakai HTTP.",
        action_taken="requests.get('http://router')",
        outcome="Gagal. 403 Forbidden. Harus HTTPS dan verify_ssl=False.",
        success=False,
    )
    print(f"    -> Tersimpan dengan Exp ID: {exp.id}")

    # 3. Simulate Agent reflection
    print("[*] Simulasi Refleksi...")
    lesson = "RouterOS memerlukan HTTPS (TLS) secara bawaan dan setingan mikrotik_tls_verify ke False jika self-signed."
    advice = "Selalu gunakan param scheme='https' dan tls_verify=False saat memanggil Mikrotik."
    learning = await hindsight_engine.reflect_and_learn(exp.id, lesson, advice)
    print(f"    -> Berhasil mempelajari Lesson ID: {learning.id}")

    # 4. Cari Advice (Simulasi Vector Search)
    print("[*] Melakukan pencarian Advice...")
    advice_list = await hindsight_engine.search_advice("Bagaimana cara menghubungi RouterOS?")
    for item in advice_list:
        print(f"    -> [Found Advice]: {item.advice_for_future}")


if __name__ == "__main__":
    asyncio.run(run_test())
