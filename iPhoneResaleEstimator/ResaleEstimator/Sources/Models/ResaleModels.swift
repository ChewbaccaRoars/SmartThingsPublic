import Foundation

struct ResaleAnalysis: Identifiable, Codable {
    let id: UUID
    let itemName: String
    let itemDescription: String
    let estimatedRetailValue: Double
    let condition: ItemCondition
    let platforms: [PlatformEstimate]
    let recommendation: String
    let confidence: ConfidenceLevel
    let tips: [String]

    init(
        id: UUID = UUID(),
        itemName: String,
        itemDescription: String,
        estimatedRetailValue: Double,
        condition: ItemCondition,
        platforms: [PlatformEstimate],
        recommendation: String,
        confidence: ConfidenceLevel,
        tips: [String]
    ) {
        self.id = id
        self.itemName = itemName
        self.itemDescription = itemDescription
        self.estimatedRetailValue = estimatedRetailValue
        self.condition = condition
        self.platforms = platforms
        self.recommendation = recommendation
        self.confidence = confidence
        self.tips = tips
    }

    var bestPlatform: PlatformEstimate? {
        platforms.max(by: { $0.netEarnings < $1.netEarnings })
    }
}

struct PlatformEstimate: Identifiable, Codable {
    let id: UUID
    let platform: ResalePlatform
    let estimatedSalePrice: Double
    let fees: [Fee]

    init(id: UUID = UUID(), platform: ResalePlatform, estimatedSalePrice: Double, fees: [Fee]) {
        self.id = id
        self.platform = platform
        self.estimatedSalePrice = estimatedSalePrice
        self.fees = fees
    }

    var totalFees: Double {
        fees.reduce(0) { $0 + $1.amount }
    }

    var netEarnings: Double {
        max(0, estimatedSalePrice - totalFees)
    }

    var feePercentage: Double {
        guard estimatedSalePrice > 0 else { return 0 }
        return (totalFees / estimatedSalePrice) * 100
    }

    var isWorthSelling: Bool {
        netEarnings > 5.0
    }
}

struct Fee: Identifiable, Codable {
    let id: UUID
    let name: String
    let amount: Double
    let percentage: Double?

    init(id: UUID = UUID(), name: String, amount: Double, percentage: Double? = nil) {
        self.id = id
        self.name = name
        self.amount = amount
        self.percentage = percentage
    }
}

enum ResalePlatform: String, Codable, CaseIterable {
    case ebay = "eBay"
    case amazon = "Amazon"
    case facebookMarketplace = "Facebook Marketplace"
    case mercari = "Mercari"
    case poshmark = "Poshmark"
    case depop = "Depop"
    case offerUp = "OfferUp"

    var icon: String {
        switch self {
        case .ebay: return "cart.fill"
        case .amazon: return "shippingbox.fill"
        case .facebookMarketplace: return "person.2.fill"
        case .mercari: return "tag.fill"
        case .poshmark: return "bag.fill"
        case .depop: return "tshirt.fill"
        case .offerUp: return "location.fill"
        }
    }

    var color: String {
        switch self {
        case .ebay: return "ebayRed"
        case .amazon: return "amazonOrange"
        case .facebookMarketplace: return "facebookBlue"
        case .mercari: return "mercariRed"
        case .poshmark: return "poshmarkRed"
        case .depop: return "depopGreen"
        case .offerUp: return "offerUpGreen"
        }
    }
}

enum ItemCondition: String, Codable {
    case brandNew = "Brand New"
    case likeNew = "Like New"
    case good = "Good"
    case fair = "Fair"
    case poor = "Poor"

    var multiplier: Double {
        switch self {
        case .brandNew: return 1.0
        case .likeNew: return 0.85
        case .good: return 0.70
        case .fair: return 0.50
        case .poor: return 0.30
        }
    }

    var icon: String {
        switch self {
        case .brandNew: return "star.fill"
        case .likeNew: return "star.leadinghalf.filled"
        case .good: return "checkmark.seal.fill"
        case .fair: return "exclamationmark.triangle.fill"
        case .poor: return "xmark.seal.fill"
        }
    }
}

enum ConfidenceLevel: String, Codable {
    case high = "High"
    case medium = "Medium"
    case low = "Low"

    var color: String {
        switch self {
        case .high: return "green"
        case .medium: return "orange"
        case .low: return "red"
        }
    }
}

enum AppError: LocalizedError {
    case noAPIKey
    case imageEncodingFailed
    case networkError(String)
    case parsingError(String)
    case unknownError

    var errorDescription: String? {
        switch self {
        case .noAPIKey:
            return "API key not configured. Please add your Anthropic API key in Settings."
        case .imageEncodingFailed:
            return "Failed to process the image. Please try again."
        case .networkError(let msg):
            return "Network error: \(msg)"
        case .parsingError(let msg):
            return "Failed to parse response: \(msg)"
        case .unknownError:
            return "An unknown error occurred. Please try again."
        }
    }
}
