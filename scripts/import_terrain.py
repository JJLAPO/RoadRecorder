"""
Terrain Importer — Script 2b
Importa il terreno 3D reale nell'area della strada registrata.

Richiede BlenderGIS installato in Blender:
    https://github.com/domlysz/BlenderGIS

Uso da Blender:
    1. Assicurati che BlenderGIS sia installato e attivato
    2. Vai su Scripting (tab in alto)
    3. Apri questo file
    4. Modifica CSV_PATH se necessario
    5. Premi Run Script

Oppure da terminale:
    blender --python import_terrain.py -- "percorso/al/file_clean.csv"

Output:
    - Mesh terreno 3D con elevazione reale
    - Texture satellite sovrapposta (se disponibile)
    - Scala 1:1 (metri)
"""

import csv
import sys
import os
import math

# ── Configurazione ──────────────────────────────────────────────────

# CSV pulito dallo script clean_road.py
CSV_PATH = r"C:\DATI\Informatica\AppStrade\dati\output\road_2026-04-02_23-09-47_clean.csv"

# Margine extra attorno alla strada (in metri)
TERRAIN_MARGIN = 200

# Risoluzione SRTM: 'SRTM1' (30m) o 'SRTM3' (90m)
SRTM_RESOLUTION = "SRTM1"

# Zoom livello satellite (15-17 consigliato, piu' alto = piu' dettaglio ma piu' pesante)
SATELLITE_ZOOM = 16

# Se lanciato da terminale con: blender --python script.py -- "file.csv"
if "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv:
        CSV_PATH = argv[0]


# ── Import Blender ──────────────────────────────────────────────────

import bpy


def load_bounding_box(csv_path, margin_m=200):
    """Calcola il bounding box lat/lon dal CSV con margine in metri."""
    lats, lons = [], []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lats.append(float(row["lat"]))
            lons.append(float(row["lon"]))

    if not lats:
        print("ERRORE: Nessun punto nel CSV")
        return None

    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)

    # Converti margine da metri a gradi
    R = 6_371_000
    margin_lat = (margin_m / R) * (180 / math.pi)
    margin_lon = (margin_m / (R * math.cos(math.radians((lat_min + lat_max) / 2)))) * (180 / math.pi)

    bbox = {
        "lat_min": lat_min - margin_lat,
        "lat_max": lat_max + margin_lat,
        "lon_min": lon_min - margin_lon,
        "lon_max": lon_max + margin_lon,
    }

    print(f"Bounding box strada:")
    print(f"  Lat: {lat_min:.6f} -> {lat_max:.6f}")
    print(f"  Lon: {lon_min:.6f} -> {lon_max:.6f}")
    print(f"Bounding box con margine ({margin_m}m):")
    print(f"  Lat: {bbox['lat_min']:.6f} -> {bbox['lat_max']:.6f}")
    print(f"  Lon: {bbox['lon_min']:.6f} -> {bbox['lon_max']:.6f}")

    return bbox


def check_blendergis():
    """Verifica che BlenderGIS sia installato e attivo."""
    addon = None
    # Prova vari nomi con cui puo' essere installato
    for name in ["blendergis", "BlenderGIS", "io_import_georaster"]:
        if name in bpy.context.preferences.addons:
            addon = name
            break

    if addon is None:
        # Prova a trovarlo tra gli addon disponibili
        import addon_utils
        for mod in addon_utils.modules():
            if "gis" in mod.__name__.lower() or "blendergis" in mod.__name__.lower():
                print(f"Trovato addon: {mod.__name__} — provo ad attivarlo...")
                bpy.ops.preferences.addon_enable(module=mod.__name__)
                addon = mod.__name__
                break

    if addon is None:
        print("\nERRORE: BlenderGIS non trovato!")
        print("Installalo da: https://github.com/domlysz/BlenderGIS")
        print("  1. Scarica lo ZIP")
        print("  2. Blender > Edit > Preferences > Add-ons > Install")
        print("  3. Seleziona lo ZIP e attiva l'addon")
        return False

    print(f"BlenderGIS trovato: {addon}")
    return True


def import_terrain_srtm(bbox):
    """Importa il terreno SRTM tramite BlenderGIS."""
    print(f"\nImportazione terreno SRTM ({SRTM_RESOLUTION})...")

    try:
        # Imposta la scena come georeferenziata
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.0

        # Prova l'operatore BlenderGIS per SRTM
        result = bpy.ops.importgis.srtm_query(
            lat=((bbox["lat_min"] + bbox["lat_max"]) / 2),
            lon=((bbox["lon_min"] + bbox["lon_max"]) / 2),
            zt=0,
        )

        if result == {"FINISHED"}:
            print("Terreno SRTM importato con successo!")
            return True
        else:
            print(f"Risultato operatore: {result}")
            return False

    except Exception as e:
        print(f"Operatore SRTM non disponibile: {e}")
        print("Provo metodo alternativo...")
        return False


def import_terrain_manual(bbox):
    """Metodo alternativo: usa l'operatore generico di BlenderGIS."""
    print("\nProvo importazione via operatore generico...")

    try:
        # Alcuni build di BlenderGIS usano questo operatore
        result = bpy.ops.importgis.dem_srtm(
            lat_min=bbox["lat_min"],
            lat_max=bbox["lat_max"],
            lon_min=bbox["lon_min"],
            lon_max=bbox["lon_max"],
        )
        if result == {"FINISHED"}:
            print("Terreno importato!")
            return True
    except Exception as e:
        print(f"dem_srtm non disponibile: {e}")

    try:
        # Operatore basemap per overlay satellite
        result = bpy.ops.importgis.basemap(
            source="GOOGLE_SAT",
            zoom=SATELLITE_ZOOM,
            lat_min=bbox["lat_min"],
            lat_max=bbox["lat_max"],
            lon_min=bbox["lon_min"],
            lon_max=bbox["lon_max"],
        )
        if result == {"FINISHED"}:
            print("Basemap satellite importata!")
            return True
    except Exception as e:
        print(f"basemap non disponibile: {e}")

    return False


def try_blosm(bbox):
    """Prova ad usare Blosm come alternativa."""
    try:
        addon_prefs = bpy.context.preferences.addons["blosm"].preferences
        addon_prefs.minLat = bbox["lat_min"]
        addon_prefs.maxLat = bbox["lat_max"]
        addon_prefs.minLon = bbox["lon_min"]
        addon_prefs.maxLon = bbox["lon_max"]
        addon_prefs.dataType = "terrain"

        result = bpy.ops.blosm.import_data()
        if result == {"FINISHED"}:
            print("Terreno importato via Blosm!")
            return True
    except Exception as e:
        print(f"Blosm non disponibile: {e}")

    return False


def print_manual_instructions(bbox):
    """Se l'automazione fallisce, stampa istruzioni manuali."""
    print("\n" + "=" * 50)
    print("IMPORTAZIONE MANUALE")
    print("=" * 50)
    print()
    print("Se l'importazione automatica non ha funzionato,")
    print("puoi importare il terreno manualmente in BlenderGIS:")
    print()
    print("1. In Blender: GIS > Web geodata > Basemap")
    print(f"   - Source: Google Satellite")
    print(f"   - Zoom: {SATELLITE_ZOOM}")
    print()
    print("2. Naviga sulla mappa fino alla tua zona:")
    print(f"   Coordinate centro: {(bbox['lat_min']+bbox['lat_max'])/2:.6f}, {(bbox['lon_min']+bbox['lon_max'])/2:.6f}")
    print()
    print("3. GIS > Web geodata > Get elevation (SRTM)")
    print()
    print("4. Questo crea il terreno 3D con texture satellite")
    print()
    print(f"Bounding box da usare:")
    print(f"  Sud:  {bbox['lat_min']:.6f}")
    print(f"  Nord: {bbox['lat_max']:.6f}")
    print(f"  Ovest: {bbox['lon_min']:.6f}")
    print(f"  Est:  {bbox['lon_max']:.6f}")


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERRORE: File non trovato: {CSV_PATH}")
        print("Modifica CSV_PATH nello script o lancia con:")
        print('  blender --python import_terrain.py -- "percorso/file_clean.csv"')
        return

    print("=== Terrain Importer ===")
    print(f"File: {CSV_PATH}")
    print(f"Margine: {TERRAIN_MARGIN}m")
    print()

    bbox = load_bounding_box(CSV_PATH, margin_m=TERRAIN_MARGIN)
    if bbox is None:
        return

    # Prova BlenderGIS
    has_gis = check_blendergis()

    success = False
    if has_gis:
        success = import_terrain_srtm(bbox)
        if not success:
            success = import_terrain_manual(bbox)

    # Prova Blosm come fallback
    if not success:
        success = try_blosm(bbox)

    if success:
        print("\nTerreno importato con successo!")
        print("Ora puoi eseguire import_blender.py per aggiungere la strada sopra il terreno.")
    else:
        print_manual_instructions(bbox)

    print("\nDone!")


main()
