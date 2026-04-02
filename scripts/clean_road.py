"""
Road Data Cleaner — Script 1
Prende il CSV grezzo dall'app RoadRecorder, pulisce i dati,
proietta in coordinate metriche, e genera mappa di confronto satellite.

Uso:
    python clean_road.py <input.csv> [--output-dir <dir>]

Output:
    - road_clean.csv         -> CSV pulito (x, y, z in metri + dati originali)
    - road_profile.png       -> Profilo altimetrico
    - road_map.html          -> Mappa interattiva con tracciato su satellite
    - road_stats.txt         -> Statistiche di pulizia
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.ndimage import uniform_filter1d


# ── Coordinate conversion ──────────────────────────────────────────

def latlon_to_meters(lat, lon, ref_lat, ref_lon):
    """Converte lat/lon in coordinate metriche locali (x=est, y=nord) rispetto a un punto di riferimento."""
    R = 6_371_000  # raggio terra in metri
    lat_rad = math.radians(ref_lat)

    dy = (lat - ref_lat) * (math.pi / 180) * R
    dx = (lon - ref_lon) * (math.pi / 180) * R * math.cos(lat_rad)
    return dx, dy


def project_to_local(df):
    """Aggiunge colonne x, y (metri) con origine al primo punto."""
    ref_lat = df.iloc[0]["lat"]
    ref_lon = df.iloc[0]["lon"]

    xs, ys = [], []
    for _, row in df.iterrows():
        dx, dy = latlon_to_meters(row["lat"], row["lon"], ref_lat, ref_lon)
        xs.append(dx)
        ys.append(dy)

    df["x"] = xs
    df["y"] = ys
    return df


# ── Filtering ───────────────────────────────────────────────────────

def filter_accuracy(df, max_h_acc=10.0):
    """Rimuove punti con precisione orizzontale troppo bassa."""
    before = len(df)
    df = df[df["h_accuracy"] <= max_h_acc].copy()
    removed = before - len(df)
    return df, removed


def filter_pressure_missing(df):
    """Rimuove i primi punti dove il barometro non si era ancora avviato (pressure=0)."""
    before = len(df)
    df = df[df["pressure"] > 0].copy()
    removed = before - len(df)
    return df, removed


def filter_spikes(df, max_jump_m=15.0):
    """Rimuove spike GPS: punti che saltano troppo rispetto ai vicini."""
    if len(df) < 3:
        return df, 0

    keep = [True] * len(df)
    xs = df["x"].values
    ys = df["y"].values

    for i in range(1, len(df) - 1):
        # Distanza dal punto precedente e successivo
        d_prev = math.hypot(xs[i] - xs[i-1], ys[i] - ys[i-1])
        d_next = math.hypot(xs[i+1] - xs[i], ys[i+1] - ys[i])
        d_skip = math.hypot(xs[i+1] - xs[i-1], ys[i+1] - ys[i-1])

        # Se rimuovendo il punto la distanza prev->next è molto minore, è uno spike
        if d_prev + d_next > d_skip * 2.5 and d_prev > max_jump_m:
            keep[i] = False

    removed = keep.count(False)
    df = df[keep].copy()
    return df, removed


# ── Smoothing ───────────────────────────────────────────────────────

def smooth_path(df, window=7):
    """Smooth delle coordinate x, y con Savitzky-Golay."""
    if len(df) < window:
        return df

    polyorder = min(3, window - 1)
    df["x_raw"] = df["x"].copy()
    df["y_raw"] = df["y"].copy()
    df["x"] = savgol_filter(df["x"].values, window, polyorder)
    df["y"] = savgol_filter(df["y"].values, window, polyorder)
    return df


def compute_altitude(df, smooth_window=11):
    """Calcola altitudine combinata: GPS di riferimento + barometro relativo, poi smooth."""
    # Altitudine base = media GPS dei primi 5 punti (più stabile)
    base_alt = df["alt_gps"].iloc[:5].mean()
    df["z"] = base_alt + df["alt_baro_rel"]

    # Smooth altitudine
    if len(df) >= smooth_window:
        polyorder = min(3, smooth_window - 1)
        df["z_raw"] = df["z"].copy()
        df["z"] = savgol_filter(df["z"].values, smooth_window, polyorder)

    return df


# ── Resampling ──────────────────────────────────────────────────────

def compute_cumulative_distance(df):
    """Calcola la distanza cumulativa lungo il percorso."""
    dx = np.diff(df["x"].values, prepend=df["x"].values[0])
    dy = np.diff(df["y"].values, prepend=df["y"].values[0])
    dz = np.diff(df["z"].values, prepend=df["z"].values[0])
    ds = np.sqrt(dx**2 + dy**2 + dz**2)
    ds[0] = 0
    df["distance"] = np.cumsum(ds)
    return df


def resample_by_distance(df, step_m=2.0):
    """Ricampiona il percorso a distanza fissa (un punto ogni step_m metri)."""
    total_dist = df["distance"].values[-1]
    if total_dist < step_m:
        return df

    new_distances = np.arange(0, total_dist, step_m)

    # Interpolazione di tutte le colonne numeriche utili
    cols_to_interp = ["x", "y", "z", "speed", "course"]
    result = {"distance": new_distances}

    for col in cols_to_interp:
        result[col] = np.interp(new_distances, df["distance"].values, df[col].values)

    new_df = pd.DataFrame(result)

    # Ricalcola lat/lon dai nuovi x, y per la mappa
    ref_lat = df.iloc[0]["lat"]
    ref_lon = df.iloc[0]["lon"]
    R = 6_371_000
    lat_rad = math.radians(ref_lat)

    new_df["lat"] = ref_lat + (new_df["y"] / R) * (180 / math.pi)
    new_df["lon"] = ref_lon + (new_df["x"] / (R * math.cos(lat_rad))) * (180 / math.pi)

    return new_df


# ── Output: mappa satellite ────────────────────────────────────────

def generate_map(df_raw, df_clean, output_path):
    """Genera mappa HTML interattiva con tracciato grezzo e pulito su satellite."""
    import folium

    center_lat = df_clean["lat"].mean()
    center_lon = df_clean["lon"].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=17,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Satellite",
    )

    # Tracciato grezzo (rosso, sottile)
    raw_coords = list(zip(df_raw["lat"], df_raw["lon"]))
    folium.PolyLine(raw_coords, color="red", weight=2, opacity=0.6, tooltip="Grezzo").add_to(m)

    # Tracciato pulito (blu, spesso)
    clean_coords = list(zip(df_clean["lat"], df_clean["lon"]))
    folium.PolyLine(clean_coords, color="#00aaff", weight=4, opacity=0.9, tooltip="Pulito").add_to(m)

    # Marker inizio/fine
    folium.Marker(
        clean_coords[0],
        popup="START",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)
    folium.Marker(
        clean_coords[-1],
        popup="END",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    m.save(str(output_path))


# ── Output: profilo altimetrico ─────────────────────────────────────

def generate_profile(df, output_path):
    """Genera grafico del profilo altimetrico."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))

    # Profilo altimetrico — asse Y stretto sui dati reali
    ax1.plot(df["distance"], df["z"], color="#0066cc", linewidth=1.5)
    ax1.fill_between(df["distance"], df["z"], df["z"].min() - 5, alpha=0.15, color="#0066cc")
    ax1.set_xlabel("Distanza (m)")
    ax1.set_ylabel("Altitudine (m)")
    ax1.set_title("Profilo altimetrico")
    ax1.grid(True, alpha=0.3)
    z_margin = max((df["z"].max() - df["z"].min()) * 0.15, 2)
    ax1.set_ylim(df["z"].min() - z_margin, df["z"].max() + z_margin)

    # Pendenza
    if len(df) > 1:
        dz = np.diff(df["z"].values)
        dd = np.diff(df["distance"].values)
        dd[dd == 0] = 0.001
        grade = (dz / dd) * 100  # percentuale
        ax2.plot(df["distance"].values[1:], grade, color="#cc3300", linewidth=0.8, alpha=0.7)
        ax2.axhline(y=0, color="black", linewidth=0.5)
        ax2.set_xlabel("Distanza (m)")
        ax2.set_ylabel("Pendenza (%)")
        ax2.set_title("Pendenza lungo il percorso")
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(-25, 25)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150)
    plt.close()


# ── Output: statistiche ────────────────────────────────────────────

def write_stats(stats, output_path):
    """Scrive le statistiche di pulizia su file."""
    with open(output_path, "w") as f:
        f.write("=== Road Data Cleaning Stats ===\n\n")
        for key, value in stats.items():
            f.write(f"{key}: {value}\n")


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pulisce i dati GPS per ricostruzione strada")
    parser.add_argument("input_csv", help="CSV grezzo dall'app RoadRecorder")
    parser.add_argument("--output-dir", "-o", default=None, help="Cartella output (default: stessa del CSV)")
    parser.add_argument("--max-accuracy", type=float, default=10.0, help="Precisione max accettata in metri (default: 10)")
    parser.add_argument("--smooth-window", type=int, default=7, help="Finestra smooth percorso (default: 7)")
    parser.add_argument("--resample-step", type=float, default=2.0, help="Passo ricampionamento in metri (default: 2.0)")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"Errore: file non trovato: {input_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem  # es. "road_2026-04-02_23-09-47"

    print(f"Caricamento: {input_path}")
    df = pd.read_csv(input_path)
    stats = {"File input": str(input_path), "Punti grezzi": len(df)}
    print(f"  {len(df)} punti grezzi")

    # 1. Filtra pressione mancante
    df, n = filter_pressure_missing(df)
    stats["Rimossi (pressione=0)"] = n
    if n > 0:
        print(f"  Rimossi {n} punti senza barometro")

    # 2. Proietta in coordinate locali (serve per spike detection)
    df = project_to_local(df)

    # 3. Filtra precisione
    df, n = filter_accuracy(df, args.max_accuracy)
    stats["Rimossi (precisione bassa)"] = n
    if n > 0:
        print(f"  Rimossi {n} punti con precisione > {args.max_accuracy}m")

    # 4. Filtra spike
    df, n = filter_spikes(df)
    stats["Rimossi (spike)"] = n
    if n > 0:
        print(f"  Rimossi {n} spike GPS")

    df = df.reset_index(drop=True)
    stats["Punti dopo filtro"] = len(df)
    print(f"  {len(df)} punti dopo filtri")

    # Salva copia grezza proiettata (per mappa confronto)
    df_raw = df.copy()

    # 5. Smooth percorso
    df = smooth_path(df, window=args.smooth_window)
    print(f"  Smooth percorso (window={args.smooth_window})")

    # 6. Calcola altitudine combinata
    df = compute_altitude(df)
    alt_start = df["z"].iloc[0]
    alt_end = df["z"].iloc[-1]
    stats["Altitudine inizio"] = f"{alt_start:.1f} m"
    stats["Altitudine fine"] = f"{alt_end:.1f} m"
    stats["Dislivello totale (fine-inizio)"] = f"{alt_end - alt_start:.1f} m"
    print(f"  Altitudine: {alt_start:.1f}m -> {alt_end:.1f}m (delta {alt_end - alt_start:+.1f}m)")

    # 7. Distanza cumulativa
    df = compute_cumulative_distance(df)
    total_dist = df["distance"].iloc[-1]
    stats["Distanza totale"] = f"{total_dist:.0f} m"
    print(f"  Distanza totale: {total_dist:.0f}m")

    # 8. Ricampiona a distanza fissa
    df_resampled = resample_by_distance(df, step_m=args.resample_step)
    stats["Passo ricampionamento"] = f"{args.resample_step} m"
    stats["Punti finali"] = len(df_resampled)
    print(f"  Ricampionato a {args.resample_step}m -> {len(df_resampled)} punti")

    # ── Salva output ──

    # CSV pulito
    csv_path = output_dir / f"{stem}_clean.csv"
    df_resampled.to_csv(csv_path, index=False, float_format="%.6f")
    print(f"\n  CSV pulito: {csv_path}")

    # Mappa satellite
    map_path = output_dir / f"{stem}_map.html"
    generate_map(df_raw, df_resampled, map_path)
    print(f"  Mappa satellite: {map_path}")

    # Profilo altimetrico
    profile_path = output_dir / f"{stem}_profile.png"
    generate_profile(df_resampled, profile_path)
    print(f"  Profilo: {profile_path}")

    # Stats
    stats_path = output_dir / f"{stem}_stats.txt"
    write_stats(stats, stats_path)
    print(f"  Stats: {stats_path}")

    print(f"\nDone! Apri {map_path.name} per confrontare con il satellite.")


if __name__ == "__main__":
    main()
