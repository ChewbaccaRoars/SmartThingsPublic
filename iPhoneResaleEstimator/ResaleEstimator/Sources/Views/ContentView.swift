import SwiftUI

struct ContentView: View {
    @StateObject private var claudeService = ClaudeService()
    @State private var selectedImage: UIImage?
    @State private var analysis: ResaleAnalysis?
    @State private var isAnalyzing = false
    @State private var errorMessage: String?
    @State private var showImageSource = false
    @State private var showResults = false
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ZStack {
                Color(.systemGroupedBackground).ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 24) {
                        // App tagline
                        taglineSection

                        // Image well
                        imageWell

                        // Analyze button
                        if selectedImage != nil {
                            analyzeButton
                        }

                        // Empty state
                        if selectedImage == nil {
                            emptyState
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Resale Estimator")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "gear")
                    }
                }
            }
            .sheet(isPresented: $showImageSource) {
                ImageSourceSheet(selectedImage: $selectedImage)
                    .presentationDetents([.medium])
            }
            .sheet(isPresented: $showResults) {
                if let analysis, let image = selectedImage {
                    ResultsView(analysis: analysis, image: image) {
                        showResults = false
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView()
            }
            .alert("Error", isPresented: Binding(
                get: { errorMessage != nil },
                set: { if !$0 { errorMessage = nil } }
            )) {
                Button("OK") { errorMessage = nil }
            } message: {
                Text(errorMessage ?? "")
            }
        }
    }

    // MARK: - Tagline

    private var taglineSection: some View {
        VStack(spacing: 6) {
            Text("Snap it. Analyze it. Sell it.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - Image Well

    private var imageWell: some View {
        Button {
            showImageSource = true
        } label: {
            ZStack {
                if let image = selectedImage {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                        .frame(maxWidth: .infinity)
                        .frame(height: 300)
                        .clipShape(RoundedRectangle(cornerRadius: 20))
                        .overlay(alignment: .bottomTrailing) {
                            changePhotoButton
                        }
                } else {
                    RoundedRectangle(cornerRadius: 20)
                        .fill(.quaternary)
                        .frame(maxWidth: .infinity)
                        .frame(height: 300)
                        .overlay {
                            VStack(spacing: 12) {
                                Image(systemName: "camera.viewfinder")
                                    .font(.system(size: 56))
                                    .foregroundStyle(.secondary)
                                Text("Tap to add a photo")
                                    .font(.headline)
                                    .foregroundStyle(.secondary)
                            }
                        }
                }
            }
        }
    }

    private var changePhotoButton: some View {
        Label("Change", systemImage: "arrow.triangle.2.circlepath.camera")
            .font(.caption.bold())
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(.ultraThinMaterial, in: Capsule())
            .padding(12)
    }

    // MARK: - Analyze Button

    private var analyzeButton: some View {
        Button {
            Task { await runAnalysis() }
        } label: {
            HStack(spacing: 10) {
                if isAnalyzing {
                    ProgressView()
                        .tint(.white)
                    Text("Analyzing with Claude...")
                        .font(.headline)
                } else {
                    Image(systemName: "sparkles")
                    Text("Estimate Resale Value")
                        .font(.headline)
                }
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(
                isAnalyzing
                    ? AnyShapeStyle(.gray)
                    : AnyShapeStyle(LinearGradient(
                        colors: [.blue, .purple],
                        startPoint: .leading,
                        endPoint: .trailing
                    )),
                in: RoundedRectangle(cornerRadius: 16)
            )
        }
        .disabled(isAnalyzing)
        .animation(.easeInOut, value: isAnalyzing)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 16) {
            Divider()
            Text("How it works")
                .font(.headline)
                .foregroundStyle(.secondary)

            HStack(spacing: 0) {
                ForEach(steps, id: \.title) { step in
                    VStack(spacing: 8) {
                        Image(systemName: step.icon)
                            .font(.title2)
                            .foregroundStyle(.blue)
                        Text(step.title)
                            .font(.caption.bold())
                        Text(step.detail)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(.vertical, 8)
        }
    }

    private var steps: [(icon: String, title: String, detail: String)] {
        [
            ("camera.fill", "Snap", "Take or upload a photo"),
            ("sparkles", "Analyze", "Claude identifies the item"),
            ("dollarsign.circle.fill", "Earn", "See your best selling options")
        ]
    }

    // MARK: - Analysis

    @MainActor
    private func runAnalysis() async {
        guard let image = selectedImage else { return }
        isAnalyzing = true
        errorMessage = nil
        defer { isAnalyzing = false }

        do {
            analysis = try await claudeService.analyzeItem(image: image)
            showResults = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
