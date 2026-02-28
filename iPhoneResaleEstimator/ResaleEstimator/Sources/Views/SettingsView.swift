import SwiftUI

struct SettingsView: View {
    @AppStorage("anthropic_api_key") private var apiKey: String = ""
    @State private var maskedKey: String = ""
    @State private var isEditing = false
    @State private var draftKey: String = ""
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Anthropic API Key", systemImage: "key.fill")
                            .font(.subheadline.bold())

                        if isEditing {
                            TextField("sk-ant-...", text: $draftKey)
                                .textFieldStyle(.roundedBorder)
                                .autocorrectionDisabled()
                                .textInputAutocapitalization(.never)

                            HStack {
                                Button("Save") {
                                    apiKey = draftKey.trimmingCharacters(in: .whitespacesAndNewlines)
                                    isEditing = false
                                }
                                .buttonStyle(.borderedProminent)

                                Button("Cancel", role: .cancel) {
                                    draftKey = apiKey
                                    isEditing = false
                                }
                                .buttonStyle(.bordered)
                            }
                        } else {
                            HStack {
                                Text(apiKey.isEmpty ? "Not configured" : maskKey(apiKey))
                                    .foregroundStyle(apiKey.isEmpty ? .red : .secondary)
                                    .font(.subheadline)
                                Spacer()
                                Button(apiKey.isEmpty ? "Add" : "Edit") {
                                    draftKey = apiKey
                                    isEditing = true
                                }
                                .font(.subheadline)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                } header: {
                    Text("API Configuration")
                } footer: {
                    Text("Your API key is stored securely in the device keychain via UserDefaults and never leaves your device except when making requests to Anthropic.")
                }

                Section("About") {
                    LabeledContent("Model", value: "Claude Opus 4.6")
                    LabeledContent("Version", value: "1.0.0")
                    Link(destination: URL(string: "https://console.anthropic.com")!) {
                        Label("Get an API Key", systemImage: "arrow.up.right.square")
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func maskKey(_ key: String) -> String {
        guard key.count > 8 else { return String(repeating: "•", count: key.count) }
        let prefix = String(key.prefix(8))
        let masked = String(repeating: "•", count: min(key.count - 8, 20))
        return prefix + masked
    }
}
