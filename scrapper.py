import asyncio
import os
import random
from playwright.async_api import async_playwright

# Próbujemy zaimportować stealth w sposób bezpieczny
try:
    import playwright_stealth
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

# --- KONFIGURACJA ---
OUTPUT_DIR = "scan-candidates"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DOCUMENT_QUERIES = {
    "pit11": "PIT-11 wzór wypełniony pdf",
    "pit37": "PIT-37 wzór wypełniony pdf",
    "faktura": "faktura vat wzór wypełniona jpg",
    "umowa_praca": "umowa o pracę wzór wypełniony pdf",
}

async def run_scraper():
    async with async_playwright() as p:
        # headless=False jest kluczowe, żebyś widział co się dzieje
        browser = await p.chromium.launch(headless=False)
        
        # Tworzymy kontekst z "ludzkimi" parametrami
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="pl-PL"
        )
        
        page = await context.new_page()

        # Próba aktywacji stealth
        if HAS_STEALTH:
            try:
                # Wywołujemy funkcję bezpośrednio z modułu
                await playwright_stealth.stealth_async(page)
            except Exception as e:
                print(f"⚠️ Nie udało się aktywować stealth, kontynuuję bez: {e}")

        for tech_name, query in DOCUMENT_QUERIES.items():
            print(f"🔎 Szukam: {tech_name}...")
            
            try:
                # Idziemy do Google
                await page.goto(f"https://www.google.pl/search?q={query}&hl=pl", wait_until="networkidle")
                
                # Akceptacja cookies Google (szukamy przycisku)
                try:
                    accept_btn = page.get_by_role("button", name="Zaakceptuj wszystko")
                    if await accept_btn.is_visible(timeout=3000):
                        await accept_btn.click()
                except:
                    pass

                # Wyciągamy linki z wyników wyszukiwania
                # Szukamy linków w kontenerze #search
                search_results = await page.locator("#search a").evaluate_all("elements => elements.map(e => e.href)")
                
                # Filtrujemy linki (tylko unikalne i nie-google)
                links = list(set([l for l in search_results if l.startswith("http") and "google.com" not in l]))

                downloaded = 0
                for link in links[:3]: # Sprawdzamy pierwsze 3 linki
                    if downloaded >= 1: break
                    
                    print(f"  -> Sprawdzam: {link[:50]}...")
                    
                    try:
                        # Otwieramy link i czekamy na ewentualny download
                        async with page.expect_download(timeout=5000) as download_info:
                            await page.goto(link, wait_until="domcontentloaded", timeout=10000)
                        
                        download = await download_info.value
                        ext = ".pdf" if ".pdf" in download.suggested_filename.lower() else ".jpg"
                        fname = f"{tech_name}_{downloaded+1}{ext}"
                        await download.save_as(os.path.join(OUTPUT_DIR, fname))
                        print(f"  ✅ POBRANO: {fname}")
                        downloaded += 1
                        
                    except Exception:
                        # Jeśli strona się otworzyła, ale nie pobrał się plik, wracamy do wyników
                        await page.go_back()
                        continue

            except Exception as e:
                print(f"  ❌ Błąd przy kategorii {tech_name}: {e}")
            
            await asyncio.sleep(random.uniform(2, 4))

        print("\n✨ Koniec. Przeglądarka zostanie otwarta jeszcze przez 30 sekund...")
        await asyncio.sleep(30)
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_scraper())
    except KeyboardInterrupt:
        print("\n🛑 Przerwano ręcznie.")