import SwiftUI
import MapKit

struct ContentView: View {
    @StateObject private var recorder = RecordingManager()
    @State private var shareURL: URL?
    @State private var showShareSheet = false
    @State private var mapRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 46.0, longitude: 11.0),
        span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
    )

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("ROAD RECORDER")
                    .font(.headline.bold())
                Spacer()
                if recorder.isRecording {
                    Circle()
                        .fill(.red)
                        .frame(width: 10, height: 10)
                        .opacity(recorder.isRecording ? 1 : 0)
                    Text("REC")
                        .font(.caption.bold())
                        .foregroundColor(.red)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)

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
                            .background(.green)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                    }
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
            .padding()
        }
        .onAppear {
            recorder.requestPermission()
        }
        .sheet(isPresented: $showShareSheet) {
            if let url = shareURL {
                ShareSheet(items: [url])
            }
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
