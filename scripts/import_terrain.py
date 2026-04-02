"""
Terrain Importer — Script 2b
Usa BlenderGIS per scaricare terreno SRTM 30m con texture satellite.

Prerequisiti:
    - BlenderGIS attivato
    - API key OpenTopography impostata nelle preferenze BlenderGIS

Uso: Blender > Scripting > Run Script
"""

import csv
import sys
import os
import math

CSV_PATH = r"C:\DATI\Informatica\AppStrade\dati\output\road_2026-04-02_23-09-47_clean.csv"
TERRAIN_MARGIN = 300

if "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv:
        CSV_PATH = argv[0]

import bpy
import bmesh


def load_bounding_box(csv_path, margin_m):
    lats, lons = [], []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lats.append(float(row["lat"]))
            lons.append(float(row["lon"]))

    if not lats:
        return None

    R = 6_371_000
    lat_c = (min(lats) + max(lats)) / 2
    lon_c = (min(lons) + max(lons)) / 2
    m_lat = (margin_m / R) * (180 / math.pi)
    m_lon = (margin_m / (R * math.cos(math.radians(lat_c)))) * (180 / math.pi)

    return {
        "lat_min": min(lats) - m_lat, "lat_max": max(lats) + m_lat,
        "lon_min": min(lons) - m_lon, "lon_max": max(lons) + m_lon,
        "center_lat": lat_c, "center_lon": lon_c,
    }


def setup_geoscene(bbox):
    """Georeferenzia la scena con BlenderGIS."""
    from BlenderGIS.geoscene import GeoScene

    scn = bpy.context.scene
    scn.unit_settings.system = "METRIC"
    scn.unit_settings.scale_length = 1.0

    geoscn = GeoScene(scn)
    geoscn.crs = "EPSG:4326"
    geoscn.setOriginGeo(bbox["center_lon"], bbox["center_lat"])

    print(f"Scena georef: origine ({bbox['center_lon']:.6f}, {bbox['center_lat']:.6f})")
    return True


def create_bbox_mesh(bbox):
    """Crea un piano che copre il bounding box — BlenderGIS lo usa per l'estensione."""
    x_min = bbox["lon_min"] - bbox["center_lon"]
    x_max = bbox["lon_max"] - bbox["center_lon"]
    y_min = bbox["lat_min"] - bbox["center_lat"]
    y_max = bbox["lat_max"] - bbox["center_lat"]

    mesh = bpy.data.meshes.new("TerrainBBox")
    obj = bpy.data.objects.new("TerrainBBox", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    v1 = bm.verts.new((x_min, y_min, 0))
    v2 = bm.verts.new((x_max, y_min, 0))
    v3 = bm.verts.new((x_max, y_max, 0))
    v4 = bm.verts.new((x_min, y_max, 0))
    bm.faces.new((v1, v2, v3, v4))
    bm.to_mesh(mesh)
    bm.free()

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    R = 6_371_000
    lat_rad = math.radians(bbox["center_lat"])
    w = (bbox["lon_max"] - bbox["lon_min"]) * (math.pi / 180) * R * math.cos(lat_rad)
    h = (bbox["lat_max"] - bbox["lat_min"]) * (math.pi / 180) * R
    print(f"Piano riferimento: ~{w:.0f}m x {h:.0f}m")
    return obj


def download_terrain():
    """Scarica SRTM tramite BlenderGIS dem_query."""
    print("\nScaricamento SRTM 30m via OpenTopography...")

    # Forza il server SRTM 30m nelle preferenze
    try:
        import json
        prefs = bpy.context.preferences.addons["BlenderGIS"].preferences
        servers = json.loads(prefs.demServerJson)
        # Seleziona il primo server (SRTM 30m)
        if servers:
            prefs.demServer = servers[0][0]
    except Exception as e:
        print(f"  Nota: impossibile impostare server automaticamente: {e}")

    try:
        result = bpy.ops.importgis.dem_query("EXEC_DEFAULT")
        if result == {"FINISHED"}:
            print("Terreno SRTM importato!")
            return True
        else:
            print(f"Risultato: {result}")
            return False
    except Exception as e:
        print(f"Errore: {e}")
        return False


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERRORE: File non trovato: {CSV_PATH}")
        return

    print("=== Terrain Importer (BlenderGIS + SRTM) ===")
    print(f"File: {CSV_PATH}\n")

    bbox = load_bounding_box(CSV_PATH, margin_m=TERRAIN_MARGIN)
    if bbox is None:
        print("ERRORE: Nessun punto")
        return

    print(f"Bbox: {bbox['lat_min']:.5f}-{bbox['lat_max']:.5f} N, {bbox['lon_min']:.5f}-{bbox['lon_max']:.5f} E\n")

    # Pulisci scena
    if "Cube" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)

    # 1. Georeferenzia
    if not setup_geoscene(bbox):
        return

    # 2. Piano bounding box
    bbox_obj = create_bbox_mesh(bbox)

    # 3. Scarica SRTM
    success = download_terrain()

    if success:
        # Rimuovi il piano di riferimento
        if "TerrainBBox" in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects["TerrainBBox"], do_unlink=True)
        print("\nTerreno pronto!")
        print("Esegui import_blender.py per la strada.")
    else:
        print("\nDownload automatico fallito.")
        print("Il piano e' selezionato — prova manualmente:")
        print("  GIS > Get elevation (SRTM) > OK")

    print("\nDone!")


main()
