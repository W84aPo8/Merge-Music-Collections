#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import hashlib
import shutil
import time
from pathlib import Path
from datetime import datetime
import argparse

class UnixStyleFileMerger:
    def __init__(self, source_dir, target_dir):
        # Absolute Pfade ab Wurzel
        self.source = Path(source_dir).resolve()
        self.target = Path(target_dir).resolve()

        # Log-Datei
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.target / f"merge_{timestamp}.log"

        # MD5-Index für Ziel (nur für Duplikaterkennung)
        self.target_md5s = set()

        # Statistiken
        self.stats = {
            'source_files': 0,
            'target_files': 0,
            'duplicates': 0,
            'copied': 0,
            'errors': 0,
            'total_size': 0
        }

    def log(self, msg):
        """Einfaches Logging"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} - {msg}"
        print(line)

        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
        except:
            pass

    def calculate_md5(self, filepath):
        """MD5 einer Datei berechnen - Python 3.6 kompatibel"""
        try:
            md5_hash = hashlib.md5()
            with open(filepath, 'rb') as f:
                # Python 3.6 kompatibel (kein Walrus-Operator)
                while True:
                    chunk = f.read(8192 * 1024)  # 8MB chunks
                    if not chunk:
                        break
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            self.log(f"MD5 Fehler {filepath}: {e}")
            return None

    def scan_target(self):
        """Scanne Zielverzeichnis und sammle alle MD5s"""
        self.log(f"Scanne Ziel: {self.target}")
        count = 0
        start_time = time.time()

        for root, dirs, files in os.walk(self.target):
            for file in files:
                filepath = Path(root) / file
                try:
                    md5 = self.calculate_md5(filepath)
                    if md5:
                        self.target_md5s.add(md5)
                    count += 1
                    if count % 1000 == 0:
                        elapsed = time.time() - start_time
                        self.log(f"  {count} Dateien gescannt ({elapsed:.1f}s)...")
                except Exception as e:
                    self.log(f"  Fehler {filepath}: {e}")
                    continue

        elapsed = time.time() - start_time
        self.stats['target_files'] = count
        self.log(f"Ziel gescannt: {count} Dateien, {len(self.target_md5s)} eindeutige MD5s in {elapsed:.1f}s")

    def dry_run(self):
        """Trockenlauf - nur analysieren"""
        self.log(f"TROCKENLAUF - Quelle: {self.source} -> Ziel: {self.target}")
        self.log("=" * 60)

        try:
            # Ziel scannen
            self.scan_target()

            # Quelle analysieren
            self.log(f"\nAnalysiere Quelle: {self.source}")
            to_copy = []
            duplicates = []
            start_time = time.time()

            for root, dirs, files in os.walk(self.source):
                for file in files:
                    try:
                        source_path = Path(root) / file

                        # Dateigröße
                        size = source_path.stat().st_size

                        # MD5 berechnen
                        md5 = self.calculate_md5(source_path)

                        if md5:
                            self.stats['source_files'] += 1

                            if md5 in self.target_md5s:
                                duplicates.append({
                                    'path': source_path.relative_to(self.source),
                                    'size': size
                                })
                                self.stats['duplicates'] += 1
                            else:
                                to_copy.append({
                                    'source': source_path,
                                    'size': size
                                })
                                self.stats['total_size'] += size

                        # Fortschritt
                        if self.stats['source_files'] % 1000 == 0:
                            elapsed = time.time() - start_time
                            self.log(f"  {self.stats['source_files']} Dateien analysiert ({elapsed:.1f}s)...")

                    except Exception as e:
                        self.log(f"  Fehler {file}: {e}")
                        continue

            elapsed = time.time() - start_time

            # Bericht
            self.log(f"\n" + "=" * 60)
            self.log("ERGEBNIS TROCKENLAUF")
            self.log("=" * 60)
            self.log(f"Analysezeit: {elapsed:.1f}s")
            self.log(f"Quelldateien: {self.stats['source_files']:,}")
            self.log(f"Zieldateien: {self.stats['target_files']:,}")
            self.log(f"Bereits vorhanden (gleicher Inhalt): {self.stats['duplicates']:,}")
            self.log(f"Zu kopieren: {len(to_copy):,}")

            if to_copy:
                self.log(f"Platzbedarf: {self.stats['total_size'] / (1024**3):.2f} GB")

                # Prüfe Platz
                try:
                    free = shutil.disk_usage(self.target).free
                    self.log(f"Freier Platz: {free / (1024**3):.2f} GB")
                    if free < self.stats['total_size']:
                        self.log("WARNUNG: Nicht genug Platz!")
                        needed = (self.stats['total_size'] - free) / (1024**3)
                        self.log(f"Fehlend: {needed:.2f} GB")
                    else:
                        free_after = (free - self.stats['total_size']) / (1024**3)
                        self.log(f"Verbleibend nach Kopie: {free_after:.2f} GB")
                except Exception as e:
                    self.log(f"Platzprüfung fehlgeschlagen: {e}")

            # Beispiel-Dateien zeigen
            if duplicates and len(duplicates) <= 10:
                self.log(f"\nBeispiele für bereits vorhandene Dateien:")
                for d in duplicates[:5]:
                    self.log(f"  {d['path']} ({d['size'] / (1024**2):.1f} MB)")

            if to_copy and len(to_copy) <= 10:
                self.log(f"\nBeispiele für neue Dateien:")
                for f in to_copy[:5]:
                    rel = f['source'].relative_to(self.source)
                    self.log(f"  {rel} ({f['size'] / (1024**2):.1f} MB)")

            return True

        except Exception as e:
            self.log(f"Fehler: {e}")
            return False

    def execute(self):
        """Kopiervorgang ausführen"""
        self.log(f"KOPIERVORGANG - Quelle: {self.source} -> Ziel: {self.target}")
        self.log("=" * 60)

        # Bestätigung
        print(f"\nQUELLE: {self.source}")
        print(f"ZIEL:   {self.target}")
        print(f"\nNeue Dateien: {self.stats['source_files'] - self.stats['duplicates']:,}")
        print(f"Platzbedarf: {self.stats['total_size'] / (1024**3):.2f} GB")
        print(f"\nFortfahren? (j/n): ", end='')

        if input().lower() != 'j':
            self.log("Abgebrochen durch Benutzer")
            return False

        # Platzprüfung
        try:
            free = shutil.disk_usage(self.target).free
            if free < self.stats['total_size']:
                self.log(f"WARNUNG: Nicht genug Platz!")
                needed = (self.stats['total_size'] - free) / (1024**3)
                print(f"\nFehlend: {needed:.2f} GB")
                print("Trotzdem fortfahren? (j/n): ", end='')
                if input().lower() != 'j':
                    self.log("Abgebrochen - nicht genug Platz")
                    return False
        except:
            self.log("Platzprüfung fehlgeschlagen")

        try:
            # Kopieren
            self.log("\nBeginne mit Kopieren...")
            start_time = time.time()
            files_processed = 0

            for root, dirs, files in os.walk(self.source):
                for file in files:
                    source_path = Path(root) / file
                    files_processed += 1

                    try:
                        # MD5 der Quelldatei
                        md5 = self.calculate_md5(source_path)
                        if not md5:
                            self.stats['errors'] += 1
                            continue

                        # Prüfe ob bereits im Ziel
                        if md5 in self.target_md5s:
                            self.stats['duplicates'] += 1
                            continue

                        # Zielpfad erstellen (cp-Stil)
                        rel_path = source_path.relative_to(self.source)
                        target_path = self.target / rel_path

                        # Verzeichnis erstellen
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        # Wenn Datei existiert (gleicher Name)
                        if target_path.exists():
                            # Prüfe ob gleicher Inhalt
                            target_md5 = self.calculate_md5(target_path)
                            if target_md5 == md5:
                                self.stats['duplicates'] += 1
                                continue
                            else:
                                # Anderer Inhalt - eindeutigen Namen finden
                                target_path = self._unique_name(target_path)

                        # Kopieren
                        shutil.copy2(source_path, target_path)

                        # Zum Index hinzufügen
                        self.target_md5s.add(md5)
                        self.stats['copied'] += 1

                        # Fortschritt
                        if self.stats['copied'] % 100 == 0:
                            elapsed = time.time() - start_time
                            rate = self.stats['copied'] / elapsed if elapsed > 0 else 0
                            self.log(f"Kopiert: {self.stats['copied']}/{len(self.source_files)} "
                                   f"({rate:.1f} Dateien/Sekunde)")

                    except Exception as e:
                        self.stats['errors'] += 1
                        self.log(f"Fehler {source_path}: {e}")

            # Bericht
            elapsed = time.time() - start_time
            self.log(f"\n" + "=" * 60)
            self.log("KOPIERVORGANG ABGESCHLOSSEN")
            self.log("=" * 60)
            self.log(f"Gesamtzeit: {elapsed:.1f}s")

            if elapsed > 0:
                rate = self.stats['copied'] / elapsed
                self.log(f"Durchschnitt: {rate:.1f} Dateien/Sekunde")

            self.log(f"\nERGEBNIS:")
            self.log(f"  Kopiert:          {self.stats['copied']:,}")
            self.log(f"  Bereits vorhanden: {self.stats['duplicates']:,}")
            self.log(f"  Fehler:           {self.stats['errors']:,}")

            if self.stats['copied'] > 0:
                avg_size = self.stats['total_size'] / self.stats['copied']
                self.log(f"  Durchschn. Größe: {avg_size / (1024**2):.1f} MB")

            self.log(f"\nLog-Datei: {self.log_file}")

            return True

        except KeyboardInterrupt:
            self.log("\nAbbruch durch Benutzer (Ctrl+C)")
            return False
        except Exception as e:
            self.log(f"Fehler: {e}")
            return False

    def _unique_name(self, path):
        """Finde eindeutigen Namen bei Konflikt"""
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1

def main():
    parser = argparse.ArgumentParser(
        description='Kopiert Dateien wie cp -r, prüft mit MD5 ob Datei bereits existiert',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s --dry-run /quelle /ziel
  %(prog)s --execute /quelle /ziel

Funktionsweise:
  1. Scanne Zielverzeichnis, sammle MD5s aller Dateien
  2. Gehe durch Quelldateien
  3. Prüfe: Ist MD5(Quelle) schon in Ziel-MD5s?
     - JA: Überspringen (Datei existiert bereits)
     - NEIN: Kopieren wie 'cp -r' (gleiche Pfadstruktur)

Sicherheit:
  - Trockenlauf (--dry-run) zuerst ausführen!
  - Keine Dateien werden gelöscht
  - Bei Namenskonflikten wird Datei umbenannt
        """
    )

    # Optionale Argumente
    parser.add_argument('--dry-run', action='store_true',
                       help='Nur analysieren, nichts kopieren')
    parser.add_argument('--execute', action='store_true',
                       help='Kopiervorgang ausführen')

    # Positionale Argumente
    parser.add_argument('source', help='Quellverzeichnis (absoluter Pfad)')
    parser.add_argument('target', help='Zielverzeichnis (absoluter Pfad)')

    args = parser.parse_args()

    # Validierung
    if not (args.dry_run or args.execute):
        parser.error("Entweder --dry-run oder --execute muss angegeben werden")

    if args.dry_run and args.execute:
        parser.error("Nur eines von --dry-run oder --execute kann angegeben werden")

    merger = UnixStyleFileMerger(args.source, args.target)

    if args.dry_run:
        success = merger.dry_run()
        if success:
            print(f"\n" + "=" * 60)
            print("Zum Kopieren ausführen:")
            print(f"{sys.argv[0]} --execute \"{args.source}\" \"{args.target}\"")
            print("=" * 60)
    else:
        success = merger.execute()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()