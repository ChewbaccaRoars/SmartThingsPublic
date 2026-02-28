import Foundation
import UIKit

class ClaudeService: ObservableObject {
    private let apiURL = "https://api.anthropic.com/v1/messages"
    private let model = "claude-opus-4-6"
    private let apiVersion = "2023-06-01"

    // Retrieve API key from UserDefaults (set via Settings screen)
    var apiKey: String {
        UserDefaults.standard.string(forKey: "anthropic_api_key") ?? ""
    }

    func analyzeItem(image: UIImage) async throws -> ResaleAnalysis {
        guard !apiKey.isEmpty else { throw AppError.noAPIKey }

        guard let imageData = image.jpegData(compressionQuality: 0.8) else {
            throw AppError.imageEncodingFailed
        }
        let base64Image = imageData.base64EncodedString()

        let prompt = buildPrompt()
        let requestBody = buildRequestBody(base64Image: base64Image, prompt: prompt)

        guard let url = URL(string: apiURL) else { throw AppError.networkError("Invalid URL") }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue(apiVersion, forHTTPHeaderField: "anthropic-version")
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AppError.networkError("No HTTP response")
        }
        guard httpResponse.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw AppError.networkError("HTTP \(httpResponse.statusCode): \(body)")
        }

        return try parseResponse(data: data)
    }

    // MARK: - Private helpers

    private func buildPrompt() -> String {
        """
        You are an expert resale analyst. Analyze the item in this photo and provide a detailed resale value assessment.

        Respond with ONLY a valid JSON object (no markdown, no explanation outside JSON) using this exact structure:
        {
          "itemName": "string",
          "itemDescription": "brief description of the item and its condition",
          "estimatedRetailValue": 0.00,
          "condition": "Brand New|Like New|Good|Fair|Poor",
          "confidence": "High|Medium|Low",
          "recommendation": "A 1-2 sentence recommendation on whether to sell and where",
          "tips": ["tip1", "tip2", "tip3"],
          "platforms": [
            {
              "platform": "eBay",
              "estimatedSalePrice": 0.00,
              "fees": [
                {"name": "Final Value Fee (12.9%)", "amount": 0.00, "percentage": 12.9},
                {"name": "Transaction Fee", "amount": 0.30, "percentage": null},
                {"name": "Shipping (estimated)", "amount": 0.00, "percentage": null}
              ]
            },
            {
              "platform": "Facebook Marketplace",
              "estimatedSalePrice": 0.00,
              "fees": [
                {"name": "Selling Fee (5%)", "amount": 0.00, "percentage": 5.0}
              ]
            },
            {
              "platform": "Mercari",
              "estimatedSalePrice": 0.00,
              "fees": [
                {"name": "Selling Fee (10%)", "amount": 0.00, "percentage": 10.0},
                {"name": "Payment Processing (2.9% + $0.50)", "amount": 0.00, "percentage": 2.9}
              ]
            },
            {
              "platform": "OfferUp",
              "estimatedSalePrice": 0.00,
              "fees": [
                {"name": "Service Fee (7.9%)", "amount": 0.00, "percentage": 7.9}
              ]
            }
          ]
        }

        Platform fee rules to calculate amounts accurately:
        - eBay: 12.9% of sale price + $0.30 per transaction + estimated shipping
        - Facebook Marketplace: 5% (min $0.40) for shipped items; 0% for local pickup
        - Mercari: 10% selling fee + (2.9% of sale + $0.50) payment processing
        - OfferUp: 7.9% service fee for shipped sales; 0% local

        Base estimates on current used-market prices. If the item is not recognizable, set confidence to "Low" and use conservative estimates.
        """
    }

    private func buildRequestBody(base64Image: String, prompt: String) -> [String: Any] {
        [
            "model": model,
            "max_tokens": 1500,
            "messages": [
                [
                    "role": "user",
                    "content": [
                        [
                            "type": "image",
                            "source": [
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64Image
                            ]
                        ],
                        [
                            "type": "text",
                            "text": prompt
                        ]
                    ]
                ]
            ]
        ]
    }

    private func parseResponse(data: Data) throws -> ResaleAnalysis {
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let content = json["content"] as? [[String: Any]],
              let firstContent = content.first,
              let text = firstContent["text"] as? String else {
            throw AppError.parsingError("Unexpected response structure")
        }

        // Strip any accidental markdown fences
        let cleaned = text
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "```json", with: "")
            .replacingOccurrences(of: "```", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        guard let jsonData = cleaned.data(using: .utf8),
              let parsed = try JSONSerialization.jsonObject(with: jsonData) as? [String: Any] else {
            throw AppError.parsingError("Could not parse JSON from Claude response")
        }

        return try mapToAnalysis(parsed)
    }

    private func mapToAnalysis(_ dict: [String: Any]) throws -> ResaleAnalysis {
        guard let itemName = dict["itemName"] as? String,
              let itemDescription = dict["itemDescription"] as? String,
              let retailValue = dict["estimatedRetailValue"] as? Double,
              let conditionStr = dict["condition"] as? String,
              let confidenceStr = dict["confidence"] as? String,
              let recommendation = dict["recommendation"] as? String,
              let tipsArray = dict["tips"] as? [String],
              let platformsArray = dict["platforms"] as? [[String: Any]] else {
            throw AppError.parsingError("Missing required fields in Claude response")
        }

        let condition = ItemCondition(rawValue: conditionStr) ?? .good
        let confidence = ConfidenceLevel(rawValue: confidenceStr) ?? .medium

        let platforms = platformsArray.compactMap { pDict -> PlatformEstimate? in
            guard let platformStr = pDict["platform"] as? String,
                  let platform = ResalePlatform(rawValue: platformStr),
                  let salePrice = pDict["estimatedSalePrice"] as? Double,
                  let feesArray = pDict["fees"] as? [[String: Any]] else { return nil }

            let fees = feesArray.compactMap { fDict -> Fee? in
                guard let name = fDict["name"] as? String,
                      let amount = fDict["amount"] as? Double else { return nil }
                let pct = fDict["percentage"] as? Double
                return Fee(name: name, amount: amount, percentage: pct)
            }

            return PlatformEstimate(platform: platform, estimatedSalePrice: salePrice, fees: fees)
        }

        return ResaleAnalysis(
            itemName: itemName,
            itemDescription: itemDescription,
            estimatedRetailValue: retailValue,
            condition: condition,
            platforms: platforms,
            recommendation: recommendation,
            confidence: confidence,
            tips: tipsArray
        )
    }
}
