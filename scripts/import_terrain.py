"""
Terrain Importer — Script 2b
Scarica elevazione reale e costruisce la mesh terreno direttamente.
Nessun plugin richiesto, solo Blender.

Uso da Blender > Scripting > Run Script
"""

import csv
import sys
import os
import math
import json
from urllib.request import Request, urlopen

# ── Configurazione ──────────────────────────────────────────────────

CSV_PATH = r"C:\DATI\Informatica\AppStrade\dati\output\road_2026-04-02_23-09-47_clean.csv"
TERRAIN_MARGIN = 300    # metri extra attorno alla strada
GRID_STEP = 30          # metri tra i punti della griglia (30 = buon dettaglio)

if "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv:
        CSV_PATH = argv[0]

# ── Import Blender ──────────────────────────────────────────────────

import bpy
import bmesh


def load_bounding_box(csv_path, margin_m):
    """Calcola bounding box dal CSV con margine."""
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
    """Converte lat/lon in coordinate metriche locali."""
    R = 6_371_000
    dy = (lat - ref_lat) * (math.pi / 180) * R
    dx = (lon - ref_lon) * (math.pi / 180) * R * math.cos(math.radians(ref_lat))
    return dx, dy


def build_grid(bbox, step_m):
    """Costruisce una griglia di punti lat/lon che copre il bounding box."""
    R = 6_371_000
    ref_lat = bbox["ref_lat"]

    # Dimensioni in metri
    width_m = (bbox["lon_max"] - bbox["lon_min"]) * (math.pi / 180) * R * math.cos(math.radians(ref_lat))
    height_m = (bbox["lat_max"] - bbox["lat_min"]) * (math.pi / 180) * R

    cols = max(int(width_m / step_m) + 1, 3)
    rows = max(int(height_m / step_m) + 1, 3)

    lats_arr = []
    lons_arr = []
    for r in range(rows):
        lat = bbox["lat_min"] + (bbox["lat_max"] - bbox["lat_min"]) * r / (rows - 1)
        for c in range(cols):
            lon = bbox["lon_min"] + (bbox["lon_max"] - bbox["lon_min"]) * c / (cols - 1)
            lats_arr.append(lat)
            lons_arr.append(lon)

    print(f"Griglia: {cols}x{rows} = {cols*rows} punti (passo ~{step_m}m)")
    return lats_arr, lons_arr, cols, rows


def fetch_elevations(lats, lons):
    """Scarica le elevazioni da Open Elevation API (gratis, no key)."""
    elevations = []
    batch_size = 100  # API accetta max ~100 punti per richiesta

    total = len(lats)
    print(f"Download elevazioni ({total} punti)...")

    for i in range(0, total, batch_size):
        batch_lats = lats[i:i+batch_size]
        batch_lons = lons[i:i+batch_size]

        locations = "|".join(f"{lat},{lon}" for lat, lon in zip(batch_lats, batch_lons))
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={locations}"

        try:
            rq = Request(url, headers={"User-Agent": "RoadRecorder/1.0"})
            with urlopen(rq, timeout=60) as response:
                data = json.loads(response.read().decode())
                for result in data["results"]:
                    elevations.append(result["elevation"])
        except Exception as e:
            print(f"  Errore batch {i//batch_size + 1}: {e}")
            print(f"  Provo endpoint alternativo...")
            # Fallback: open-meteo elevation API
            try:
                lat_str = ",".join(str(l) for l in batch_lats)
                lon_str = ",".join(str(l) for l in batch_lons)
                url2 = f"https://api.open-meteo.com/v1/elevation?latitude={lat_str}&longitude={lon_str}"
                rq2 = Request(url2, headers={"User-Agent": "RoadRecorder/1.0"})
                with urlopen(rq2, timeout=60) as response2:
                    data2 = json.loads(response2.read().decode())
                    elevations.extend(data2["elevation"])
            except Exception as e2:
                print(f"  Anche fallback fallito: {e2}")
                # Riempi con 0 per non bloccare
                elevations.extend([0] * len(batch_lats))

        done = min(i + batch_size, total)
        print(f"  {done}/{total} punti scaricati...")

    print(f"Elevazioni: min={min(elevations):.0f}m, max={max(elevations):.0f}m")
    return elevations


def create_terrain_mesh(lats, lons, elevations, cols, rows, ref_lat, ref_lon):
    """Crea la mesh terreno in Blender a scala reale."""
    mesh = bpy.data.meshes.new("Terrain")
    obj = bpy.data.objects.new("Terrain", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    vert_grid = []

    # Crea i vertici
    for i in range(len(lats)):
        x, y = latlon_to_meters(lats[i], lons[i], ref_lat, ref_lon)
        z = elevations[i]
        v = bm.verts.new((x, y, z))
        vert_grid.append(v)

    bm.verts.ensure_lookup_table()

    # Crea le facce (quad grid)
    for r in range(rows - 1):
        for c in range(cols - 1):
            i = r * cols + c
            v1 = vert_grid[i]
            v2 = vert_grid[i + 1]
            v3 = vert_grid[i + cols + 1]
            v4 = vert_grid[i + cols]
            try:
                bm.faces.new((v1, v2, v3, v4))
            except:
                pass

    bm.to_mesh(mesh)
    bm.free()

    mesh.update()

    # Smooth shading per aspetto migliore
    for poly in mesh.polygons:
        poly.use_smooth = True

    # Aggiungi subdivision surface per piu' dettaglio
    mod = obj.modifiers.new("Subdivision", "SUBSURF")
    mod.levels = 2
    mod.render_levels = 3

    print(f"Mesh terreno: {len(mesh.vertices)} vertici, {len(mesh.polygons)} facce")
    return obj


def frame_view(obj):
    """Centra la vista sull'oggetto."""
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

    print("=== Terrain Importer ===")
    print(f"File: {CSV_PATH}\n")

    bbox = load_bounding_box(CSV_PATH, margin_m=TERRAIN_MARGIN)
    if bbox is None:
        print("ERRORE: Nessun punto nel CSV")
        return

    print(f"Area: {bbox['lat_min']:.5f}-{bbox['lat_max']:.5f} N, {bbox['lon_min']:.5f}-{bbox['lon_max']:.5f} E")
    print(f"Margine: {TERRAIN_MARGIN}m, griglia: {GRID_STEP}m\n")

    # Rimuovi cubo default
    if "Cube" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)

    # Imposta scena
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

    # 1. Costruisci griglia
    lats, lons, cols, rows = build_grid(bbox, GRID_STEP)

    # 2. Scarica elevazioni
    elevations = fetch_elevations(lats, lons)

    if not elevations or all(e == 0 for e in elevations):
        print("ERRORE: Nessuna elevazione scaricata")
        return

    # 3. Crea mesh terreno
    print()
    terrain = create_terrain_mesh(lats, lons, elevations, cols, rows, bbox["ref_lat"], bbox["ref_lon"])

    # 4. Centra vista
    frame_view(terrain)

    print(f"\nTerreno pronto! Coordinate in metri, stesso sistema di import_blender.py")
    print(f"Esegui import_blender.py per aggiungere la strada sopra il terreno.")
    print("Done!")


main()
