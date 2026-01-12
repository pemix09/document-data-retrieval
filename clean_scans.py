import os
import shutil
import ollama
from pathlib import Path

# --- KONFIGURACJA ---
ROOT_FOLDER = "scans"
REJECTED_FOLDER = "_ODRZUCONE"
HISTORY_FILE = "clean_scans_processed.txt"
MODEL_NAME = "llama3.2-vision"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.heic'}

# Foldery, których NIE ruszać (bezpieczne)
SAFE_FOLDERS = {'documentScan', 'other'}

# --- SZCZEGÓŁOWE KRYTERIA DLA KAŻDEGO TYPU ---
# AI otrzyma instrukcję: "Szukaj [Tytuł]. Wymagane cechy: [Cechy]"
DOCUMENT_TYPES = {
    # --- PODATKI (PIT) - WYMÓG SYMBOLU W NAGŁÓWKU ---
    'pit11': ('Deklaracja PIT-11',
              'Wyraźny symbol "PIT-11" (zazwyczaj lewy górny róg), tabela z przychodami, dane płatnika i podatnika'),
    'pit37': ('Zeznanie PIT-37',
              'Wyraźny symbol "PIT-37" (duży druk w nagłówku/rogu), biało-zielony lub biały formularz, pola na PESEL'),
    'pit36': ('Zeznanie PIT-36', 'Wyraźny symbol "PIT-36" w nagłówku formularza, sekcje działalności gospodarczej'),
    'pit36L': ('Zeznanie PIT-36L', 'Wyraźny symbol "PIT-36L" (podatek liniowy) w nagłówku'),
    'pit28': ('Zeznanie PIT-28', 'Wyraźny symbol "PIT-28" (ryczałt) w nagłówku formularza'),
    'pit38': ('Zeznanie PIT-38', 'Wyraźny symbol "PIT-38" (kapitały pieniężne) w nagłówku'),
    'pit39': ('Zeznanie PIT-39', 'Wyraźny symbol "PIT-39" (nieruchomości) w nagłówku'),
    'pit5': ('Deklaracja PIT-5', 'Symbol "PIT-5" widoczny na formularzu'),
    'pit8C': ('Informacja PIT-8C', 'Symbol "PIT-8C" widoczny w nagłówku formularza'),
    'vat7': ('Deklaracja VAT-7 / JPK', 'Symbol "VAT-7" lub nagłówek JPK_V7, tabela rozliczenia podatku VAT'),
    'cit8': ('Zeznanie CIT-8', 'Symbol "CIT-8" w nagłówku, dotyczy osób prawnych'),
    'pcc3': ('Deklaracja PCC-3', 'Symbol "PCC-3" (podatek od czynności cywilnoprawnych) w nagłówku'),

    # --- FINANSE ---
    'invoice': ('Faktura VAT',
                'Słowo "Faktura" lub "Invoice", tabela z kolumnami netto/vat/brutto, dane sprzedawcy i nabywcy'),
    'proformaInvoice': ('Faktura Proforma',
                        'Wyraźny napis "Proforma" lub "Zamówienie", brak skutków księgowych (wygląda jak faktura)'),
    'receipt': ('Paragon fiskalny',
                'Wąski wydruk z drukarki fiskalnej, logo sklepu na górze, stawki PTU na dole, data i godzina'),
    'utilityBill': ('Rachunek za media',
                    'Logo dostawcy (prąd/gaz/woda/internet), wykres zużycia, kwota "do zapłaty", numer konta'),
    'bankStatement': ('Wyciąg bankowy', 'Logo banku, lista operacji z datami i kwotami, saldo początkowe i końcowe'),
    'loanAgreement': ('Umowa kredytowa',
                      'Tytuł "Umowa kredytu" lub "Umowa pożyczki", harmonogram spłat, pieczęci banku'),
    'insurancePolicy': ('Polisa ubezpieczeniowa',
                        'Tytuł "Polisa", numer polisy, okres ubezpieczenia, przedmiot ubezpieczenia (auto/dom)'),

    # --- PRAWO ---
    'notarialDeed': ('Akt notarialny',
                     'Godło państwowe (orzeł), pieczęć notariusza, charakterystyczny sznurek (repetytorium), tytuł "Akt Notarialny"'),
    'courtJudgment': ('Wyrok sądu',
                      'Godło państwowe, nagłówek "Wyrok w imieniu Rzeczypospolitej Polskiej", sygnatura akt'),
    'powerOfAttorney': ('Pełnomocnictwo',
                        'Tytuł "Pełnomocnictwo" lub "Upoważnienie", dane mocodawcy i pełnomocnika, podpis'),
    'employmentContract': ('Umowa o pracę',
                           'Tytuł "Umowa o pracę", określenie stanowiska, wynagrodzenia, wymiaru etatu'),
    'mandateContract': ('Umowa zlecenie',
                        'Tytuł "Umowa zlecenie", określenie czynności do wykonania, stawka godzinowa/miesięczna'),
    'taskContract': ('Umowa o dzieło', 'Tytuł "Umowa o dzieło", określenie konkretnego rezultatu/dzieła'),
    'b2bContract': ('Kontrakt B2B', 'Umowa współpracy biznesowej, dane dwóch firm (NIP), określenie zasad współpracy'),
    'nonCompeteAgreement': ('Zakaz konkurencji',
                            'Umowa lub aneks o zakazie konkurencji, określenie kar umownych i okresu obowiązywania'),
    'lawsuit': ('Pozew sądowy', 'Pismo procesowe, nagłówek "Pozew", oznaczenie sądu i stron, uzasadnienie'),

    # --- OSOBISTE ---
    'idCard': ('Dowód osobisty', 'Plastikowa karta, zdjęcie twarzy, godło, napis "Rzeczpospolita Polska"'),
    'passport': ('Paszport', 'Strona z danymi, zdjęcie, hologramy, dolny pasek maszynowy (<<<)'),
    'birthCertificate': ('Akt urodzenia', 'Odpis aktu stanu cywilnego, godło, pieczęć urzędu stanu cywilnego (USC)'),
    'marriageCertificate': ('Akt małżeństwa', 'Odpis aktu małżeństwa, dane małżonków, pieczęć USC'),
    'deathCertificate': ('Akt zgonu', 'Odpis aktu zgonu, czarna ramka lub standardowy druk USC, pieczęć'),
    'peselConfirmation': ('Zaświadczenie PESEL',
                          'Biały druk urzędowy, potwierdzenie nadania numeru PESEL, pieczęć gminy/urzędu'),
    'drivingLicense': ('Prawo jazdy', 'Różowa plastikowa karta, zdjęcie, ikony pojazdów na rewersie'),
    'schoolCertificate': ('Świadectwo szkolne',
                          'Gilosz (ozdobne tło), godło, nazwa szkoły, oceny, czerwony pasek (opcjonalnie)'),
    'universityDiploma': ('Dyplom studiów',
                          'Ozdobny papier, godło uczelni, tytuł zawodowy (licencjat/magister/inżynier), pieczęć sucha lub tuszowa'),
    'professionalCertificate': ('Certyfikat zawodowy',
                                'Nazwa kursu/szkolenia, imię i nazwisko uczestnika, podpis organizatora'),
    'cv': ('CV / Życiorys', 'Układ sekcyjny: Doświadczenie, Edukacja, Umiejętności, często zdjęcie, dane kontaktowe'),

    # --- ZDROWIE ---
    'sickLeave': ('Zwolnienie L4', 'Formularz ZUS ZLA (zielony/biały) lub wydruk e-ZLA, dane pacjenta i lekarza'),
    'prescription': ('Recepta', 'Kod kreskowy (góra/dół), "Recepta", lista leków, dane świadczeniodawcy'),
    'medicalResults': ('Wyniki badań',
                       'Wydruk laboratoryjny, nazwy parametrów (morfologia, glukoza itp.), normy i wyniki'),
    'referral': ('Skierowanie', 'Tytuł "Skierowanie", rozpoznanie (kod ICD-10), pieczęć lekarza kierującego'),
    'medicalHistory': ('Historia choroby/Wypis', 'Karta informacyjna leczenia szpitalnego, epikryza, zalecenia'),
    'vaccinationCard': ('Karta szczepień', 'Książeczka lub karta, tabela z datami szczepień i nazwami preparatów'),
    'sanitaryBooklet': ('Książeczka sanepidowska',
                        'Mała książeczka, wpisy badań na nosicielstwo, pieczątki stacji sanitarno-epidemiologicznej'),

    # --- NIERUCHOMOŚCI / AUTO ---
    'propertyDeed': ('Akt własności', 'Akt notarialny dotyczący przeniesienia własności nieruchomości'),
    'landRegistry': ('Księga wieczysta', 'Wydruk z EKW (Elektroniczne Księgi Wieczyste), działy I-IV'),
    'rentalAgreement': ('Umowa najmu', 'Tytuł "Umowa najmu lokalu", określenie czynszu, kaucji, adres lokalu'),
    'registrationCertificate': ('Dowód rejestracyjny',
                                'Składany dokument (błękitno-żółty), hologram, pola z kodami A, B, C'),
    'vehicleHistory': ('Karta pojazdu', 'Czerwona książeczka (stary typ) lub wydruk historii z CEPiK'),
    'landMap': ('Mapa geodezyjna', 'Rysunek techniczny terenu, granice działek, numery działek, pieczęć starostwa'),
    'technicalInspection': ('Przegląd techniczny',
                            'Zaświadczenie ze stacji kontroli pojazdów lub pieczątka w dowodzie rejestracyjnym'),

    # --- INNE ---
    'application': ('Wniosek/Podanie', 'Nagłówek "Wniosek" lub "Podanie", adresat (urząd/firma), prośba, podpis'),
    'certificate': ('Zaświadczenie', 'Tytuł "Zaświadczenie", potwierdzenie faktu przez instytucję, pieczęć'),
    'authorization': ('Upoważnienie', 'Tytuł "Upoważnienie", dane osoby upoważnianej do czynności, podpis')
}

DEFAULT_CRITERIA = "Oficjalny dokument z czytelnym tekstem i pieczęciami."


# --- LOGIKA ---

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())


def mark_as_done(rel_path):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{rel_path}\n")


def check_document_strict(file_path, doc_name, criteria):
    """
    Wysyła zapytanie do Llama Vision z BARDZO rygorystycznymi wymogami.
    """
    print(f" (Weryfikacja: {doc_name} -> {criteria[:30]}...)", end="", flush=True)

    prompt = f"""
    Działaj jako rygorystyczny audytor dokumentów. Twoim zadaniem jest potwierdzenie autentyczności typu dokumentu.

    OBRAZ: {file_path}
    OCZEKIWANY TYP: {doc_name}

    KRYTYCZNE WYMAGANIA WIZUALNE (MUST HAVE):
    - {criteria}

    NATYCHMIASTOWE ODRZUCENIE (REJECT IF):
    1. To jest zrzut ekranu (widać paski przeglądarki, kursor, interfejs telefonu).
    2. To jest zdjęcie ekranu monitora (widać piksele/morę).
    3. Dokument jest nieczytelny, rozmazany lub ucięty w sposób uniemożliwiający identyfikację.
    4. Brakuje kluczowych elementów wymienionych w wymaganiach (np. brak napisu "PIT-11" na rzekomym PIT-11).
    5. To jest zdjęcie przedmiotu, zwierzęcia lub osoby (selfie), a nie skan dokumentu.

    DECYZJA:
    Czy obraz spełnia wszystkie kryteria dla {doc_name}?
    Odpowiedz TYLKO jednym słowem: TAK lub NIE.
    """

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [str(file_path)]
            }]
        )
        # Czyszczenie odpowiedzi (np. "TAK." -> "TAK")
        answer = response['message']['content'].strip().upper().replace('.', '')

        if "TAK" in answer or "YES" in answer:
            return True
        return False

    except Exception as e:
        print(f" ❌ Błąd API: {e}")
        return None


def main():
    base_path = Path(ROOT_FOLDER)
    rejected_path = base_path / REJECTED_FOLDER

    if not base_path.exists():
        print(f"❌ Folder '{ROOT_FOLDER}' nie istnieje!")
        return

    if not rejected_path.exists():
        rejected_path.mkdir()

    processed_files = load_history()
    print(f"📂 Historia: {len(processed_files)} plików pominiętych.")
    print(f"🚀 Start audytu wizualnego (Model: {MODEL_NAME})...")

    # Pobieramy listę folderów w katalogu scans
    subdirs = [d for d in base_path.iterdir() if d.is_dir()]

    for folder in subdirs:
        folder_name = folder.name

        # 1. Pomijanie folderów specjalnych
        if folder_name == REJECTED_FOLDER:
            continue

        # 2. Pomijanie folderów "bezpiecznych" (np. documentScan - szybki zrzut)
        if folder_name in SAFE_FOLDERS:
            # print(f"⏩ Pomijam bezpieczny folder: {folder_name}")
            continue

        # Pobieranie kryteriów z mapy
        if folder_name in DOCUMENT_TYPES:
            doc_name, doc_criteria = DOCUMENT_TYPES[folder_name]
        else:
            # Jeśli folderu nie ma w słowniku, można go pominąć lub użyć domyślnych
            # print(f"⏩ Folder nieznany w systemie: {folder_name} (pomijam)")
            continue

        files = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
        if not files:
            continue

        print(f"\n📂 Audyt folderu: [{folder_name}]")

        for file_path in files:
            rel_path_str = str(file_path.relative_to(base_path))

            # Sprawdzenie historii
            if rel_path_str in processed_files:
                continue

            print(f"  👁️  Plik: {file_path.name}...", end="", flush=True)

            is_valid = check_document_strict(file_path, doc_name, doc_criteria)

            if is_valid is True:
                print(" ✅ OK")
                mark_as_done(rel_path_str)

            elif is_valid is False:
                print(" 🗑️  ODRZUCONY")

                # Przenoszenie
                target_dir = rejected_path / folder_name
                if not target_dir.exists():
                    target_dir.mkdir(parents=True)

                try:
                    shutil.move(str(file_path), str(target_dir / file_path.name))
                    mark_as_done(rel_path_str)  # Oznaczamy jako przetworzony (usunięty)
                except Exception as e:
                    print(f"     [!] Błąd przenoszenia: {e}")
            else:
                print(" ⚠️ Błąd modelu (spróbujemy ponownie).")

    print("\n✨ Zakończono.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Zatrzymano.")