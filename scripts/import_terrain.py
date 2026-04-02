"""
Terrain Importer — Script 2b
Importa il terreno 3D reale nell'area della strada registrata.

Richiede BlenderGIS installato e attivato in Blender.

Uso da Blender:
    1. Apri Blender (scena nuova)
    2. Vai su Scripting (tab in alto)
    3. Apri questo file
    4. Modifica CSV_PATH se necessario
    5. Premi Run Script
"""

import csv
import sys
import os
import math
import tempfile

# ── Configurazione ──────────────────────────────────────────────────

CSV_PATH = r"C:\DATI\Informatica\AppStrade\dati\output\road_2026-04-02_23-09-47_clean.csv"
TERRAIN_MARGIN = 200  # metri extra attorno alla strada

# Se lanciato da terminale: blender --python import_terrain.py -- "file.csv"
if "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv:
        CSV_PATH = argv[0]

# ── Import Blender ──────────────────────────────────────────────────

import bpy
import bmesh


def load_bounding_box(csv_path, margin_m=200):
    """Calcola il bounding box lat/lon dal CSV con margine."""
    lats, lons = [], []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lats.append(float(row["lat"]))
            lons.append(float(row["lon"]))

    if not lats:
        return None

    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)

    R = 6_371_000
    margin_lat = (margin_m / R) * (180 / math.pi)
    margin_lon = (margin_m / (R * math.cos(math.radians((lat_min + lat_max) / 2)))) * (180 / math.pi)

    return {
        "lat_min": lat_min - margin_lat,
        "lat_max": lat_max + margin_lat,
        "lon_min": lon_min - margin_lon,
        "lon_max": lon_max + margin_lon,
        "center_lat": (lat_min + lat_max) / 2,
        "center_lon": (lon_min + lon_max) / 2,
    }


def setup_geoscene(bbox):
    """Georeferenzia la scena Blender con BlenderGIS."""
    from BlenderGIS.geoscene import GeoScene

    scn = bpy.context.scene
    scn.unit_settings.system = "METRIC"
    scn.unit_settings.scale_length = 1.0

    geoscn = GeoScene(scn)
    geoscn.crs = "EPSG:4326"
    geoscn.setOriginGeo(bbox["center_lon"], bbox["center_lat"])

    print(f"Scena georef: EPSG:4326, origine ({bbox['center_lon']:.6f}, {bbox['center_lat']:.6f})")
    return True


def download_gmrt_terrain(bbox):
    """Scarica il terreno da GMRT (Marine-geo.org) — NO API key necessaria."""
    from urllib.request import Request, urlopen

    url = (
        f"http://www.gmrt.org/services/GridServer"
        f"?west={bbox['lon_min']}&east={bbox['lon_max']}"
        f"&south={bbox['lat_min']}&north={bbox['lat_max']}"
        f"&layer=topo&format=geotiff&resolution=high"
    )

    print(f"Download terreno da GMRT (no API key)...")
    print(f"  URL: {url[:80]}...")

    filepath = os.path.join(tempfile.gettempdir(), "terrain_gmrt.tif")

    try:
        rq = Request(url, headers={"User-Agent": "BlenderGIS/RoadRecorder"})
        with urlopen(rq, timeout=120) as response:
            data = response.read()
            with open(filepath, "wb") as f:
                f.write(data)
        size_kb = len(data) / 1024
        print(f"  Scaricato: {filepath} ({size_kb:.0f} KB)")
        return filepath
    except Exception as e:
        print(f"  ERRORE download: {e}")
        return None


def download_srtm_opentopo(bbox, api_key=""):
    """Scarica SRTM da OpenTopography (richiede API key gratuita)."""
    if not api_key:
        return None

    from urllib.request import Request, urlopen

    url = (
        f"https://portal.opentopography.org/API/globaldem"
        f"?demtype=SRTMGL1"
        f"&west={bbox['lon_min']}&east={bbox['lon_max']}"
        f"&south={bbox['lat_min']}&north={bbox['lat_max']}"
        f"&outputFormat=GTiff&API_Key={api_key}"
    )

    print(f"Download SRTM 30m da OpenTopography...")
    filepath = os.path.join(tempfile.gettempdir(), "terrain_srtm.tif")

    try:
        rq = Request(url, headers={"User-Agent": "BlenderGIS/RoadRecorder"})
        with urlopen(rq, timeout=120) as response:
            data = response.read()
            with open(filepath, "wb") as f:
                f.write(data)
        size_kb = len(data) / 1024
        print(f"  Scaricato: {filepath} ({size_kb:.0f} KB)")
        return filepath
    except Exception as e:
        print(f"  ERRORE download: {e}")
        return None


def import_geotiff_as_terrain(filepath):
    """Importa un GeoTIFF come terreno 3D usando BlenderGIS georaster."""
    print(f"Importazione terreno in Blender...")

    try:
        result = bpy.ops.importgis.georaster(
            "EXEC_DEFAULT",
            filepath=filepath,
            reprojection=True,
            rastCRS="EPSG:4326",
            importMode="DEM",
            subdivision="subsurf",
            demInterpolation=True,
        )
        if result == {"FINISHED"}:
            print("Terreno importato!")
            return True
        else:
            print(f"Risultato: {result}")
            return False
    except Exception as e:
        print(f"Errore importazione: {e}")
        return False


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERRORE: File non trovato: {CSV_PATH}")
        return

    print("=== Terrain Importer ===")
    print(f"File: {CSV_PATH}\n")

    bbox = load_bounding_box(CSV_PATH, margin_m=TERRAIN_MARGIN)
    if bbox is None:
        print("ERRORE: Nessun punto nel CSV")
        return

    print(f"Bounding box ({TERRAIN_MARGIN}m margine):")
    print(f"  Lat: {bbox['lat_min']:.6f} -> {bbox['lat_max']:.6f}")
    print(f"  Lon: {bbox['lon_min']:.6f} -> {bbox['lon_max']:.6f}\n")

    # Rimuovi cubo default
    if "Cube" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)

    # 1. Georeferenzia la scena
    if not setup_geoscene(bbox):
        return

    # 2. Scarica terreno — prova GMRT (gratis, no API key)
    filepath = download_gmrt_terrain(bbox)

    # Fallback: OpenTopography (se hai API key nelle preferenze BlenderGIS)
    if filepath is None:
        try:
            prefs = bpy.context.preferences.addons["BlenderGIS"].preferences
            api_key = getattr(prefs, "opentopography_api_key", "")
            filepath = download_srtm_opentopo(bbox, api_key)
        except:
            pass

    if filepath is None:
        print("\nERRORE: Download terreno fallito.")
        print("Prova manualmente: GIS > Get elevation (SRTM)")
        return

    # 3. Importa il GeoTIFF come terreno
    success = import_geotiff_as_terrain(filepath)

    if success:
        print("\nTerreno pronto!")
        print("Ora esegui import_blender.py per aggiungere la strada sopra il terreno.")
    else:
        print("\nImportazione fallita.")
        print(f"Il file GeoTIFF e' stato scaricato qui: {filepath}")
        print("Prova manualmente: GIS > Import georeferenced raster")
        print(f"  File: {filepath}")
        print("  Mode: DEM")

    print("\nDone!")


main()
