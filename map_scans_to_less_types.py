import os
import shutil
from pathlib import Path

# --- KONFIGURACJA ---
SOURCE_DIR = Path("scans")
DEST_DIR = Path("scans_less_types")

# --- MAPOWANIE (Na podstawie Twojej funkcji fromId) ---
# Klucz: Stara nazwa folderu (z poprzedniego enuma)
# Wartość: Nowa nazwa folderu (z nowego enuma)

FOLDER_MAPPING = {
    # --- ID 0-11 -> taxDocument ---
    'pit11': 'taxDocument',
    'pit37': 'taxDocument',
    'pit36': 'taxDocument',
    'pit36L': 'taxDocument',
    'pit28': 'taxDocument',
    'pit38': 'taxDocument',
    'pit39': 'taxDocument',
    'pit5': 'taxDocument',
    'pit8C': 'taxDocument',
    'vat7': 'taxDocument',
    'cit8': 'taxDocument',
    'pcc3': 'taxDocument',

    # --- ID 12-13 -> invoice ---
    'invoice': 'invoice',
    'proformaInvoice': 'invoice',

    # --- ID 22-26 -> contract ---
    'employmentContract': 'contract',
    'mandateContract': 'contract',
    'taskContract': 'contract',
    'b2bContract': 'contract',
    'nonCompeteAgreement': 'contract',

    # --- ID 20, 27 -> courtDocument ---
    'courtJudgment': 'courtDocument',
    'lawsuit': 'courtDocument',

    # --- ID 33 -> officialCertificate ---
    'peselConfirmation': 'officialCertificate',

    # --- ID 35-37 -> educationDocument ---
    'schoolCertificate': 'educationDocument',
    'universityDiploma': 'educationDocument',
    'professionalCertificate': 'educationDocument',

    # --- ID 39, 41, 43 -> medicalDocument ---
    'sickLeave': 'medicalDocument',
    'medicalResults': 'medicalDocument',
    'medicalHistory': 'medicalDocument',

    # --- ID 46, 47, 51 -> propertyDeed ---
    'propertyDeed': 'propertyDeed',
    'landRegistry': 'propertyDeed',
    'landMap': 'propertyDeed',

    # --- ID 49, 50 -> vehicleDocument ---
    'registrationCertificate': 'vehicleDocument',
    'vehicleHistory': 'vehicleDocument',

    # --- ID 56 -> other (authorization) ---
    'authorization': 'other',

    # --- POZOSTAŁE (Bez zmian nazwy lub mapowanie 1:1) ---
    'receipt': 'receipt',
    'utilityBill': 'utilityBill',
    'bankStatement': 'bankStatement',
    'loanAgreement': 'loanAgreement',
    'insurancePolicy': 'insurancePolicy',
    'notarialDeed': 'notarialDeed',
    'powerOfAttorney': 'powerOfAttorney',
    'idCard': 'idCard',
    'passport': 'passport',
    'birthCertificate': 'birthCertificate',
    'marriageCertificate': 'marriageCertificate',
    'deathCertificate': 'deathCertificate',
    'drivingLicense': 'drivingLicense',
    'cv': 'cv',
    'prescription': 'prescription',
    'referral': 'referral',
    'vaccinationCard': 'vaccinationCard',
    'sanitaryBooklet': 'sanitaryBooklet',
    'rentalAgreement': 'rentalAgreement',
    'technicalInspection': 'technicalInspection',
    'documentScan': 'documentScan',
    'application': 'application',
    'certificate': 'certificate',
    'other': 'other'
}


def get_unique_filename(destination_folder, filename):
    """
    Zwraca unikalną nazwę pliku, jeśli taki już istnieje w folderze docelowym.
    Np. jeśli 'plik.jpg' istnieje, zwróci 'plik_1.jpg'.
    """
    if not (destination_folder / filename).exists():
        return filename

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1

    while True:
        new_filename = f"{stem}_{counter}{suffix}"
        if not (destination_folder / new_filename).exists():
            return new_filename
        counter += 1


def main():
    if not SOURCE_DIR.exists():
        print(f"❌ Folder źródłowy '{SOURCE_DIR}' nie istnieje!")
        return

    # Tworzenie folderu docelowego
    if not DEST_DIR.exists():
        DEST_DIR.mkdir()
        print(f"📂 Utworzono folder docelowy: {DEST_DIR}")

    print("🚀 Rozpoczynam migrację dokumentów...")

    moved_count = 0
    folders_processed = 0

    # Iteracja po starych folderach w scans/
    for old_folder_path in SOURCE_DIR.iterdir():
        if not old_folder_path.is_dir():
            continue

        old_name = old_folder_path.name

        # Pomijamy foldery specjalne (np. _ODRZUCONE)
        if old_name.startswith("_"):
            continue

        # Sprawdzamy czy mamy mapowanie dla tego folderu
        new_name = FOLDER_MAPPING.get(old_name)

        if not new_name:
            print(f"⚠️  Nieznany typ folderu: '{old_name}' - pomijam.")
            continue

        # Tworzenie folderu w nowej strukturze
        target_folder = DEST_DIR / new_name
        if not target_folder.exists():
            target_folder.mkdir()

        # Przenoszenie plików
        files = [f for f in old_folder_path.iterdir() if f.is_file() and f.name != ".DS_Store"]

        if files:
            print(f"📦 Przenoszę {len(files)} plików z '{old_name}' -> '{new_name}'")

            for file in files:
                unique_name = get_unique_filename(target_folder, file.name)
                target_path = target_folder / unique_name

                try:
                    # shutil.move przenosi plik (usuwa ze źródła)
                    # Jeśli chcesz kopiować, użyj shutil.copy2
                    shutil.move(str(file), str(target_path))
                    moved_count += 1
                except Exception as e:
                    print(f"   ❌ Błąd przenoszenia {file.name}: {e}")

        folders_processed += 1

        # Opcjonalnie: Usuń stary pusty folder
        try:
            old_folder_path.rmdir()
        except:
            pass  # Jeśli folder nie jest pusty (np. pliki ukryte), zostaw go

    print("-" * 40)
    print(f"✅ Zakończono migrację.")
    print(f"📂 Przetworzono folderów źródłowych: {folders_processed}")
    print(f"📄 Przeniesiono plików: {moved_count}")
    print(f"📍 Nowa lokalizacja: {DEST_DIR.absolute()}")


if __name__ == "__main__":
    main()