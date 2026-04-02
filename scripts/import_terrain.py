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

Il flusso:
    1. Georeferenzia la scena (CRS + origine al centro strada)
    2. Crea un piano di riferimento grande quanto il bounding box
    3. Scarica SRTM elevation dal web e lo applica al piano
"""

import csv
import sys
import os
import math

# ── Configurazione ──────────────────────────────────────────────────

CSV_PATH = r"C:\DATI\Informatica\AppStrade\dati\output\road_2026-04-02_23-09-47_clean.csv"

# Margine extra attorno alla strada (in metri)
TERRAIN_MARGIN = 200

# Se lanciato da terminale: blender --python import_terrain.py -- "file.csv"
if "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv:
        CSV_PATH = argv[0]

# ── Import Blender ──────────────────────────────────────────────────

import bpy
import bmesh


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

    R = 6_371_000
    margin_lat = (margin_m / R) * (180 / math.pi)
    margin_lon = (margin_m / (R * math.cos(math.radians((lat_min + lat_max) / 2)))) * (180 / math.pi)

    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2

    bbox = {
        "lat_min": lat_min - margin_lat,
        "lat_max": lat_max + margin_lat,
        "lon_min": lon_min - margin_lon,
        "lon_max": lon_max + margin_lon,
        "center_lat": center_lat,
        "center_lon": center_lon,
    }

    print(f"Centro strada: {center_lat:.6f}, {center_lon:.6f}")
    print(f"Bounding box con margine ({margin_m}m):")
    print(f"  Lat: {bbox['lat_min']:.6f} -> {bbox['lat_max']:.6f}")
    print(f"  Lon: {bbox['lon_min']:.6f} -> {bbox['lon_max']:.6f}")

    return bbox


def setup_geoscene(bbox):
    """Georeferenzia la scena Blender con BlenderGIS."""
    # Importa GeoScene dal modulo BlenderGIS
    import importlib
    addon_path = None
    for name in ["BlenderGIS", "blendergis"]:
        if name in bpy.context.preferences.addons:
            addon_path = name
            break

    if addon_path is None:
        print("ERRORE: BlenderGIS non attivato!")
        return False

    # Accedi al modulo GeoScene di BlenderGIS
    from BlenderGIS.geoscene import GeoScene

    scn = bpy.context.scene
    scn.unit_settings.system = "METRIC"
    scn.unit_settings.scale_length = 1.0

    geoscn = GeoScene(scn)

    # Imposta CRS a EPSG:4326 (WGS84 lat/lon)
    geoscn.crs = "EPSG:4326"

    # Imposta l'origine della scena al centro della strada
    geoscn.setOriginGeo(bbox["center_lon"], bbox["center_lat"])

    print(f"Scena georeferenziata: EPSG:4326, origine a ({bbox['center_lon']:.6f}, {bbox['center_lat']:.6f})")
    return True


def create_bbox_mesh(bbox):
    """Crea un piano mesh che copre il bounding box (per BlenderGIS dem_query)."""
    from BlenderGIS.geoscene import GeoScene

    geoscn = GeoScene(bpy.context.scene)

    # Calcola posizioni in coordinate scena (relative all'origine)
    # In EPSG:4326 le coordinate sono in gradi, l'origine e' al centro
    x_min = bbox["lon_min"] - bbox["center_lon"]
    x_max = bbox["lon_max"] - bbox["center_lon"]
    y_min = bbox["lat_min"] - bbox["center_lat"]
    y_max = bbox["lat_max"] - bbox["center_lat"]

    # Converti gradi in metri approssimati per la dimensione del piano
    R = 6_371_000
    lat_rad = math.radians(bbox["center_lat"])
    sx = (bbox["lon_max"] - bbox["lon_min"]) * (math.pi / 180) * R * math.cos(lat_rad)
    sy = (bbox["lat_max"] - bbox["lat_min"]) * (math.pi / 180) * R

    # Crea il piano mesh
    mesh = bpy.data.meshes.new("TerrainBBox")
    obj = bpy.data.objects.new("TerrainBBox", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    # Piano con i 4 vertici del bounding box in coordinate scena
    # Per EPSG:4326 le "unita'" sono gradi
    v1 = bm.verts.new((x_min, y_min, 0))
    v2 = bm.verts.new((x_max, y_min, 0))
    v3 = bm.verts.new((x_max, y_max, 0))
    v4 = bm.verts.new((x_min, y_max, 0))
    bm.faces.new((v1, v2, v3, v4))
    bm.to_mesh(mesh)
    bm.free()

    # Seleziona e rendi attivo
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    print(f"Piano di riferimento creato: {sx:.0f}m x {sy:.0f}m")
    return obj


def download_terrain():
    """Chiama BlenderGIS dem_query per scaricare il terreno SRTM."""
    print("\nScaricamento terreno SRTM...")
    try:
        result = bpy.ops.importgis.dem_query("EXEC_DEFAULT")
        if result == {"FINISHED"}:
            print("Terreno SRTM scaricato e importato!")
            return True
        else:
            print(f"Risultato: {result}")
            return False
    except Exception as e:
        print(f"Errore dem_query: {e}")
        return False


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERRORE: File non trovato: {CSV_PATH}")
        return

    print("=== Terrain Importer ===")
    print(f"File: {CSV_PATH}")
    print()

    bbox = load_bounding_box(CSV_PATH, margin_m=TERRAIN_MARGIN)
    if bbox is None:
        return

    # Rimuovi cubo default
    if "Cube" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)

    # 1. Georeferenzia la scena
    print()
    if not setup_geoscene(bbox):
        return

    # 2. Crea piano bounding box come riferimento
    print()
    bbox_obj = create_bbox_mesh(bbox)

    # 3. Scarica terreno SRTM
    success = download_terrain()

    if success:
        # Rimuovi il piano di riferimento (il terreno lo ha sostituito)
        bpy.data.objects.remove(bbox_obj, do_unlink=True)
        print("\nTerreno pronto! Ora esegui import_blender.py per aggiungere la strada.")
    else:
        print("\n" + "=" * 50)
        print("DOWNLOAD AUTOMATICO FALLITO")
        print("=" * 50)
        print()
        print("Prova manualmente in BlenderGIS:")
        print("  1. La scena e' gia' georeferenziata")
        print("  2. Il piano TerrainBBox e' selezionato")
        print("  3. Vai su: GIS > Get elevation (SRTM)")
        print("  4. Clicca OK nella finestra che appare")
        print()
        print("Se chiede un API key per OpenTopography:")
        print("  - Registrati gratis su https://opentopography.org")
        print("  - Richiedi un API key")
        print("  - Inseriscilo nelle preferenze di BlenderGIS")

    print("\nDone!")


main()
