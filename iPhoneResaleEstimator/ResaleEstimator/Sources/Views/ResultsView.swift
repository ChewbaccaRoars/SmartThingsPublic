import SwiftUI

struct ResultsView: View {
    let analysis: ResaleAnalysis
    let image: UIImage
    var onDismiss: () -> Void

    @State private var selectedPlatform: PlatformEstimate?
    private let currency = FloatingPointFormatStyle<Double>.Currency(code: "USD")

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Item image + summary header
                    headerSection

                    // Best platform highlight
                    if let best = analysis.bestPlatform {
                        bestPlatformBanner(best)
                    }

                    // Platform breakdown
                    platformsSection

                    // Tips section
                    if !analysis.tips.isEmpty {
                        tipsSection
                    }

                    // Recommendation
                    recommendationSection
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Resale Analysis")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: onDismiss)
                }
            }
        }
        .sheet(item: $selectedPlatform) { platform in
            PlatformDetailView(platform: platform)
                .presentationDetents([.medium])
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(spacing: 12) {
            Image(uiImage: image)
                .resizable()
                .scaledToFill()
                .frame(height: 200)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(alignment: .bottomLeading) {
                    conditionBadge
                        .padding(10)
                }

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(analysis.itemName)
                        .font(.title2.bold())
                    Spacer()
                    confidenceBadge
                }

                Text(analysis.itemDescription)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                HStack {
                    Label(
                        "Retail: \(analysis.estimatedRetailValue.formatted(currency))",
                        systemImage: "tag"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }
        }
        .padding(16)
        .background(.background, in: RoundedRectangle(cornerRadius: 16))
    }

    private var conditionBadge: some View {
        Label(analysis.condition.rawValue, systemImage: analysis.condition.icon)
            .font(.caption.bold())
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(.ultraThinMaterial, in: Capsule())
    }

    private var confidenceBadge: some View {
        Text("Confidence: \(analysis.confidence.rawValue)")
            .font(.caption2.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(confidenceColor.opacity(0.15), in: Capsule())
            .foregroundStyle(confidenceColor)
    }

    private var confidenceColor: Color {
        switch analysis.confidence {
        case .high: return .green
        case .medium: return .orange
        case .low: return .red
        }
    }

    // MARK: - Best Platform Banner

    private func bestPlatformBanner(_ platform: PlatformEstimate) -> some View {
        VStack(spacing: 4) {
            Text("Best Option")
                .font(.caption.bold())
                .foregroundStyle(.white.opacity(0.8))
            Text(platform.platform.rawValue)
                .font(.title3.bold())
                .foregroundStyle(.white)
            Text("Est. \(platform.netEarnings.formatted(currency)) net")
                .font(.largeTitle.bold())
                .foregroundStyle(.white)
            Text("after \(platform.totalFees.formatted(currency)) in fees (\(Int(platform.feePercentage))%)")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.8))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .background(
            LinearGradient(
                colors: [.green, .mint],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 16)
        )
    }

    // MARK: - Platforms

    private var platformsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("All Platforms")
                .font(.headline)

            ForEach(analysis.platforms.sorted(by: { $0.netEarnings > $1.netEarnings })) { platform in
                PlatformRow(platform: platform, currency: currency)
                    .onTapGesture { selectedPlatform = platform }
            }
        }
    }

    // MARK: - Tips

    private var tipsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Selling Tips", systemImage: "lightbulb.fill")
                .font(.headline)
                .foregroundStyle(.orange)

            ForEach(Array(analysis.tips.enumerated()), id: \.offset) { _, tip in
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                        .font(.body)
                    Text(tip)
                        .font(.subheadline)
                }
            }
        }
        .padding(16)
        .background(.background, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Recommendation

    private var recommendationSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Recommendation", systemImage: "brain.head.profile")
                .font(.headline)
            Text(analysis.recommendation)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(.background, in: RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Platform Row

struct PlatformRow: View {
    let platform: PlatformEstimate
    let currency: FloatingPointFormatStyle<Double>.Currency

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: platform.platform.icon)
                .font(.title3)
                .foregroundStyle(.white)
                .frame(width: 42, height: 42)
                .background(rowColor, in: RoundedRectangle(cornerRadius: 10))

            VStack(alignment: .leading, spacing: 2) {
                Text(platform.platform.rawValue)
                    .font(.subheadline.bold())
                Text("Fees: \(platform.totalFees.formatted(currency)) (\(Int(platform.feePercentage))%)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text(platform.netEarnings.formatted(currency))
                    .font(.headline)
                    .foregroundStyle(platform.isWorthSelling ? .primary : .red)
                Text("net")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(14)
        .background(.background, in: RoundedRectangle(cornerRadius: 14))
    }

    private var rowColor: Color {
        switch platform.platform {
        case .ebay: return .red
        case .amazon: return .orange
        case .facebookMarketplace: return .blue
        case .mercari: return .pink
        case .poshmark: return .red
        case .depop: return .green
        case .offerUp: return .teal
        }
    }
}

// MARK: - Platform Detail Sheet

struct PlatformDetailView: View {
    let platform: PlatformEstimate
    @Environment(\.dismiss) private var dismiss
    private let currency = FloatingPointFormatStyle<Double>.Currency(code: "USD")

    var body: some View {
        NavigationStack {
            List {
                Section("Sale Price") {
                    LabeledContent("Estimated Sale Price", value: platform.estimatedSalePrice.formatted(currency))
                }

                Section("Fee Breakdown") {
                    ForEach(platform.fees) { fee in
                        HStack {
                            Text(fee.name)
                                .font(.subheadline)
                            Spacer()
                            Text("-\(fee.amount.formatted(currency))")
                                .foregroundStyle(.red)
                        }
                    }
                    LabeledContent("Total Fees") {
                        Text("-\(platform.totalFees.formatted(currency))")
                            .foregroundStyle(.red)
                            .bold()
                    }
                }

                Section("Your Earnings") {
                    LabeledContent("Net Earnings") {
                        Text(platform.netEarnings.formatted(currency))
                            .foregroundStyle(platform.isWorthSelling ? .green : .red)
                            .font(.headline)
                    }
                    LabeledContent("Fee Rate", value: "\(String(format: "%.1f", platform.feePercentage))%")
                }
            }
            .navigationTitle(platform.platform.rawValue)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
