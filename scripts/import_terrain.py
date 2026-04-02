"""
Terrain Importer — Script 2b
Scarica elevazione SRTM e costruisce la mesh terreno direttamente.
Usa Open-Meteo API (gratis, no key, dati SRTM 30m).

Uso: Blender > Scripting > Run Script
"""

import csv
import sys
import os
import math
import json
from urllib.request import Request, urlopen

CSV_PATH = r"C:\DATI\Informatica\AppStrade\dati\output\road_2026-04-02_23-09-47_clean.csv"
TERRAIN_MARGIN = 300    # metri extra attorno alla strada
GRID_STEP = 15          # metri tra punti griglia (piu' basso = piu' dettaglio)

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
        "ref_lat": lat_c, "ref_lon": lon_c,
    }


def latlon_to_meters(lat, lon, ref_lat, ref_lon):
    R = 6_371_000
    dy = (lat - ref_lat) * (math.pi / 180) * R
    dx = (lon - ref_lon) * (math.pi / 180) * R * math.cos(math.radians(ref_lat))
    return dx, dy


def build_grid(bbox, step_m):
    R = 6_371_000
    ref_lat = bbox["ref_lat"]
    width_m = (bbox["lon_max"] - bbox["lon_min"]) * (math.pi / 180) * R * math.cos(math.radians(ref_lat))
    height_m = (bbox["lat_max"] - bbox["lat_min"]) * (math.pi / 180) * R

    cols = max(int(width_m / step_m) + 1, 3)
    rows = max(int(height_m / step_m) + 1, 3)

    lats_arr, lons_arr = [], []
    for r in range(rows):
        lat = bbox["lat_min"] + (bbox["lat_max"] - bbox["lat_min"]) * r / (rows - 1)
        for c in range(cols):
            lon = bbox["lon_min"] + (bbox["lon_max"] - bbox["lon_min"]) * c / (cols - 1)
            lats_arr.append(lat)
            lons_arr.append(lon)

    print(f"Griglia: {cols}x{rows} = {cols * rows} punti (~{step_m}m)")
    print(f"  Area: {width_m:.0f}m x {height_m:.0f}m")
    return lats_arr, lons_arr, cols, rows


def fetch_elevations_openmeteo(lats, lons):
    """Scarica elevazioni da Open-Meteo (SRTM 30m, gratis, no key)."""
    elevations = []
    # Open-Meteo accetta molti punti ma URL ha limiti di lunghezza
    # Mandiamo batch da 80 punti
    batch_size = 80
    total = len(lats)

    print(f"\nDownload elevazioni da Open-Meteo ({total} punti)...")

    for i in range(0, total, batch_size):
        batch_lats = lats[i:i + batch_size]
        batch_lons = lons[i:i + batch_size]

        lat_str = ",".join(f"{l:.6f}" for l in batch_lats)
        lon_str = ",".join(f"{l:.6f}" for l in batch_lons)
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lat_str}&longitude={lon_str}"

        try:
            rq = Request(url, headers={"User-Agent": "RoadRecorder/1.0"})
            with urlopen(rq, timeout=30) as response:
                data = json.loads(response.read().decode())
                elevations.extend(data["elevation"])
        except Exception as e:
            print(f"  ERRORE batch {i // batch_size + 1}: {e}")
            elevations.extend([0] * len(batch_lats))

        done = min(i + batch_size, total)
        if done % 400 < batch_size or done == total:
            print(f"  {done}/{total}...")

    e_valid = [e for e in elevations if e != 0]
    if e_valid:
        print(f"  Elevazione: {min(e_valid):.0f}m - {max(e_valid):.0f}m (delta {max(e_valid)-min(e_valid):.0f}m)")
    return elevations


def create_terrain_mesh(lats, lons, elevations, cols, rows, ref_lat, ref_lon):
    mesh = bpy.data.meshes.new("Terrain")
    obj = bpy.data.objects.new("Terrain", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    verts = []

    for i in range(len(lats)):
        x, y = latlon_to_meters(lats[i], lons[i], ref_lat, ref_lon)
        z = elevations[i]
        v = bm.verts.new((x, y, z))
        verts.append(v)

    bm.verts.ensure_lookup_table()

    for r in range(rows - 1):
        for c in range(cols - 1):
            i = r * cols + c
            try:
                bm.faces.new((verts[i], verts[i + 1], verts[i + cols + 1], verts[i + cols]))
            except:
                pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    # Smooth shading
    for poly in mesh.polygons:
        poly.use_smooth = True

    # Subdivision per superficie piu' liscia
    mod = obj.modifiers.new("Smooth", "SUBSURF")
    mod.levels = 2
    mod.render_levels = 3
    mod.subdivision_type = "SIMPLE"

    # Materiale base verde/marrone terreno
    mat = bpy.data.materials.new("TerrainMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.35, 0.30, 0.20, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    obj.data.materials.append(mat)

    print(f"\nMesh terreno: {len(mesh.vertices)} vertici, {len(mesh.polygons)} facce")
    return obj


def frame_view(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    with bpy.context.temp_override(area=area, region=region):
                        bpy.ops.view3d.view_selected()
                    break
            break


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERRORE: File non trovato: {CSV_PATH}")
        return

    print("=== Terrain Importer (SRTM via Open-Meteo) ===")
    print(f"File: {CSV_PATH}")
    print(f"Margine: {TERRAIN_MARGIN}m | Griglia: {GRID_STEP}m\n")

    bbox = load_bounding_box(CSV_PATH, margin_m=TERRAIN_MARGIN)
    if bbox is None:
        print("ERRORE: Nessun punto")
        return

    # Pulisci
    if "Cube" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

    # 1. Griglia
    lats, lons, cols, rows = build_grid(bbox, GRID_STEP)

    # 2. Elevazioni
    elevations = fetch_elevations_openmeteo(lats, lons)
    if not elevations or all(e == 0 for e in elevations):
        print("ERRORE: Nessuna elevazione")
        return

    # 3. Mesh
    terrain = create_terrain_mesh(lats, lons, elevations, cols, rows, bbox["ref_lat"], bbox["ref_lon"])
    frame_view(terrain)

    print(f"\nTerreno pronto! Stesse coordinate di import_blender.py")
    print("Done!")


main()
