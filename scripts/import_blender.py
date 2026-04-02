"""
Road Blender Importer — Script 2
Importa il CSV pulito in Blender come curva 3D a scala reale (1 unita' = 1 metro).

Uso da Blender:
    1. Apri Blender
    2. Vai su Scripting (tab in alto)
    3. Apri questo file
    4. Modifica CSV_PATH con il percorso del tuo CSV pulito
    5. Premi Run Script

Oppure da terminale:
    blender --python import_blender.py -- "percorso/al/file_clean.csv"

Output:
    - Curva NURBS "RoadCurve" con i punti della strada
    - Scala reale: 1 unita' Blender = 1 metro
    - Pronta per modificatori (bevel, array, ecc.)
"""

import csv
import sys
import os

# ── Configurazione ──────────────────────────────────────────────────

# Modifica questo percorso se esegui dallo Scripting tab di Blender
CSV_PATH = r"C:\DATI\Informatica\AppStrade\dati\output\road_2026-04-02_23-09-47_clean.csv"

# Se lanciato da terminale con: blender --python script.py -- "file.csv"
if "--" in sys.argv:
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv:
        CSV_PATH = argv[0]


# ── Import Blender ──────────────────────────────────────────────────

import math
import bpy
import mathutils


def load_road_points(csv_path):
    """Carica i punti dal CSV pulito."""
    points = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            x = float(row["x"])
            y = float(row["y"])
            z = float(row["z"])
            points.append((x, y, z))
    print(f"Caricati {len(points)} punti da {csv_path}")
    return points


def create_nurbs_curve(points, name="RoadCurve"):
    """Crea una curva NURBS 3D dai punti."""
    curve_data = bpy.data.curves.new(name=name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 12  # smoothness della curva

    # Crea spline NURBS
    spline = curve_data.splines.new("NURBS")
    spline.points.add(len(points) - 1)  # il primo punto esiste gia'

    for i, (x, y, z) in enumerate(points):
        spline.points[i].co = (x, y, z, 1.0)  # w=1.0 per NURBS
        spline.points[i].radius = 1.0
        spline.points[i].tilt = math.radians(90)  # ruota 90° -> extrude orizzontale

    spline.use_endpoint_u = True
    spline.order_u = 4  # grado 3, buon compromesso smooth/fedelta'

    # Crea oggetto e aggiungilo alla scena
    curve_obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(curve_obj)
    bpy.context.view_layer.objects.active = curve_obj
    curve_obj.select_set(True)

    return curve_obj, curve_data


def setup_scene():
    """Configura la scena per scala reale."""
    # Imposta unita' a metri
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.context.scene.unit_settings.length_unit = "METERS"

    # Rimuovi il cubo di default se presente
    if "Cube" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)


def frame_camera_to_road(curve_obj):
    """Posiziona la vista per vedere tutta la strada."""
    # Seleziona la curva
    bpy.context.view_layer.objects.active = curve_obj
    curve_obj.select_set(True)

    # Zoom to fit in tutte le viewport 3D
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    override = bpy.context.copy()
                    override["area"] = area
                    override["region"] = region
                    with bpy.context.temp_override(**override):
                        bpy.ops.view3d.view_selected()
                    break
            break


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERRORE: File non trovato: {CSV_PATH}")
        print("Modifica CSV_PATH nello script o lancia con:")
        print('  blender --python import_blender.py -- "percorso/file_clean.csv"')
        return

    print(f"\n=== Road Blender Importer ===")
    print(f"File: {CSV_PATH}")

    setup_scene()

    points = load_road_points(CSV_PATH)
    if not points:
        print("ERRORE: Nessun punto nel CSV")
        return

    curve, curve_data = create_nurbs_curve(points)

    # Superficie piatta orizzontale via extrude (tilt 90° sui punti)
    road_width = 3.0  # metri — modifica per la tua strada
    curve_data.extrude = road_width / 2.0

    # Info utili
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]

    print(f"\nCurva creata: '{curve.name}'")
    print(f"  Larghezza strada: {road_width} m (modifica road_width nello script)")
    print(f"  Punti: {len(points)}")
    print(f"  Estensione X: {min(xs):.0f} -> {max(xs):.0f} m ({max(xs)-min(xs):.0f} m)")
    print(f"  Estensione Y: {min(ys):.0f} -> {max(ys):.0f} m ({max(ys)-min(ys):.0f} m)")
    print(f"  Altitudine Z: {min(zs):.0f} -> {max(zs):.0f} m (delta {max(zs)-min(zs):.1f} m)")
    print(f"  Scala: 1 unita' = 1 metro (reale)")
    print(f"\nProssimi passi:")
    print(f"  1. Aggiungi Bevel (Properties > Object Data > Geometry > Bevel) per dare larghezza")
    print(f"  2. Converti a mesh (Ctrl+Alt+C) quando sei soddisfatto")
    print(f"  3. Esporta in FBX per Assetto Corsa")

    frame_camera_to_road(curve)
    print("\nDone!")


main()
