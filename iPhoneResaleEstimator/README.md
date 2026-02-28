# ResaleEstimator — iPhone App

An iOS app that uses Claude's vision AI to analyze photos of items and estimate their resale value across multiple platforms, accounting for all fees.

## Features

- **Camera & Photo Library** — Take a photo or select from your library
- **Claude Vision Analysis** — Powered by Claude Opus 4.6 to identify items and estimate current market prices
- **Multi-Platform Estimates** — Compares eBay, Facebook Marketplace, Mercari, and OfferUp
- **Fee Breakdown** — Shows exact fee calculations per platform so you know your true net earnings
- **Sell/Skip Recommendation** — AI-generated advice on whether it's worth selling and where
- **Selling Tips** — Platform-specific tips to maximize your sale price

## Supported Platforms & Fee Structures

| Platform | Fee |
|---|---|
| eBay | 12.9% final value fee + $0.30/transaction + shipping |
| Facebook Marketplace | 5% (min $0.40) for shipped; 0% local pickup |
| Mercari | 10% selling fee + 2.9% + $0.50 payment processing |
| OfferUp | 7.9% for shipped; 0% local |

## Setup

### Prerequisites
- Xcode 15+
- iOS 17+ deployment target
- An [Anthropic API key](https://console.anthropic.com)

### Running the App

1. Open `ResaleEstimator.xcodeproj` in Xcode
2. Select your target device or simulator
3. Build & Run (`Cmd+R`)
4. On first launch, tap the **gear icon** (Settings) and enter your Anthropic API key

### Project Structure

```
iPhoneResaleEstimator/
├── ResaleEstimator.xcodeproj/
│   └── project.pbxproj
└── ResaleEstimator/
    ├── Info.plist
    └── Sources/
        ├── App/
        │   └── ResaleEstimatorApp.swift      # @main entry point
        ├── Models/
        │   └── ResaleModels.swift            # Data types
        ├── Services/
        │   └── ClaudeService.swift           # Anthropic API integration
        └── Views/
            ├── ContentView.swift             # Home screen
            ├── ImagePickerView.swift         # Camera + photo picker
            ├── ResultsView.swift             # Analysis results
            └── SettingsView.swift            # API key configuration
```

## How It Works

1. **Capture** — User takes a photo or picks one from their library
2. **Encode** — Image is JPEG-compressed and base64-encoded
3. **Analyze** — Sent to Claude's vision API with a structured prompt requesting JSON output
4. **Parse** — Response is parsed into typed Swift models
5. **Display** — Results shown with platform comparison, fee breakdown, and recommendations

## API Key Storage

Your API key is stored in `UserDefaults` under the key `anthropic_api_key`. For production use, consider migrating to the iOS Keychain for enhanced security.
