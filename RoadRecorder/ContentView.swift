import SwiftUI
import MapKit

struct ContentView: View {
    @StateObject private var recorder = RecordingManager()
    @State private var shareURL: URL?
    @State private var showShareSheet = false
    @State private var showExportError = false
    @State private var mapRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 46.0, longitude: 11.0),
        span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
    )

    private var hasError: Bool {
        recorder.locationManager.lastError != nil ||
        recorder.altimeterManager.lastError != nil
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("ROAD RECORDER")
                    .font(.headline.bold())
                Spacer()

                // GPS signal indicator
                if recorder.locationManager.signalLost {
                    Image(systemName: "location.slash")
                        .foregroundColor(.orange)
                        .font(.caption)
                }

                if recorder.isWarmingUp {
                    Image(systemName: "antenna.radiowaves.left.and.right")
                        .foregroundColor(.blue)
                        .font(.caption)
                    Text("WARMUP")
                        .font(.caption.bold())
                        .foregroundColor(.blue)
                } else if recorder.isRecording {
                    Circle()
                        .fill(.red)
                        .frame(width: 10, height: 10)
                    Text("REC")
                        .font(.caption.bold())
                        .foregroundColor(.red)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)

            // Error / status banner
            if let error = recorder.locationManager.lastError {
                ErrorBanner(message: error, color: .red)
            } else if let error = recorder.altimeterManager.lastError {
                ErrorBanner(message: error, color: .orange)
            } else if recorder.isWarmingUp {
                ErrorBanner(
                    message: "GPS warmup — precisione: \(formatAccuracy(recorder.locationManager.currentLocation?.horizontalAccuracy)) (serve < 5m)",
                    color: .blue
                )
            } else if recorder.locationManager.signalLost && recorder.isRecording {
                ErrorBanner(message: "Segnale GPS perso — in attesa...", color: .orange)
            }

            // Map
            Map(coordinateRegion: $mapRegion,
                showsUserLocation: true,
                annotationItems: recorder.points) { point in
                MapAnnotation(coordinate: point.coordinate) {
                    Circle()
                        .fill(.blue)
                        .frame(width: 4, height: 4)
                }
            }
            .frame(maxHeight: .infinity)
            .onChange(of: recorder.locationManager.currentLocation) { location in
                if let coord = location?.coordinate {
                    withAnimation {
                        mapRegion.center = coord
                    }
                }
            }

            // Stats
            VStack(spacing: 8) {
                HStack {
                    StatBox(title: "Punti", value: "\(recorder.points.count)")
                    StatBox(title: "Distanza", value: formatDistance(recorder.totalDistance))
                }
                HStack {
                    StatBox(title: "Altitudine GPS",
                            value: formatAlt(recorder.locationManager.currentLocation?.altitude))
                    StatBox(title: "Alt. Baro Δ",
                            value: String(format: "%+.1f m", recorder.altimeterManager.relativeAltitude))
                }
                HStack {
                    StatBox(title: "Precisione",
                            value: formatAccuracy(recorder.locationManager.currentLocation?.horizontalAccuracy))
                    StatBox(title: "Velocità",
                            value: formatSpeed(recorder.locationManager.currentLocation?.speed))
                }
                // Diagnostics row
                if recorder.isRecording || recorder.droppedPoints > 0 || recorder.gpsGapCount > 0 {
                    HStack {
                        StatBox(title: "Scartati", value: "\(recorder.droppedPoints)")
                        StatBox(title: "Gap GPS", value: "\(recorder.gpsGapCount)")
                    }
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)

            // Buttons
            HStack(spacing: 16) {
                if !recorder.isRecording {
                    Button(action: {
                        recorder.startRecording()
                    }) {
                        Label("START", systemImage: "record.circle")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(hasError ? .gray : .green)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                    }
                    .disabled(hasError && recorder.locationManager.authorizationStatus == .denied)
                } else {
                    Button(action: {
                        recorder.stopRecording()
                    }) {
                        Label("STOP", systemImage: "stop.circle")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(.red)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                    }
                }

                Button(action: {
                    if let url = recorder.exportCSV() {
                        shareURL = url
                        showShareSheet = true
                    } else {
                        showExportError = true
                    }
                }) {
                    Label("SALVA", systemImage: "square.and.arrow.up")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(recorder.points.isEmpty ? .gray : .blue)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
                .disabled(recorder.points.isEmpty)
            }
            .padding(.horizontal)

            // Log export button
            Button(action: {
                shareURL = recorder.exportLog()
                showShareSheet = true
            }) {
                Label("Esporta Log", systemImage: "doc.text")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 8)
        }
        .onAppear {
            recorder.requestPermission()
        }
        .sheet(isPresented: $showShareSheet) {
            if let url = shareURL {
                ShareSheet(items: [url])
            }
        }
        .alert("Errore Export", isPresented: $showExportError) {
            Button("OK") {}
        } message: {
            Text(recorder.exportError ?? "Errore sconosciuto")
        }
    }

    // MARK: - Formatting

    private func formatDistance(_ meters: Double) -> String {
        if meters < 1000 {
            return String(format: "%.0f m", meters)
        }
        return String(format: "%.2f km", meters / 1000)
    }

    private func formatAlt(_ alt: Double?) -> String {
        guard let alt else { return "—" }
        return String(format: "%.0f m", alt)
    }

    private func formatAccuracy(_ acc: Double?) -> String {
        guard let acc, acc >= 0 else { return "—" }
        return String(format: "±%.1f m", acc)
    }

    private func formatSpeed(_ speed: Double?) -> String {
        guard let speed, speed >= 0 else { return "—" }
        let kmh = speed * 3.6
        return String(format: "%.0f km/h", kmh)
    }
}

// MARK: - Error Banner

struct ErrorBanner: View {
    let message: String
    let color: Color

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.caption)
            Text(message)
                .font(.caption)
        }
        .foregroundColor(.white)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .frame(maxWidth: .infinity)
        .background(color.opacity(0.9))
    }
}

// MARK: - StatBox

struct StatBox: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption2)
                .foregroundColor(.secondary)
            Text(value)
                .font(.system(.body, design: .monospaced).bold())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
