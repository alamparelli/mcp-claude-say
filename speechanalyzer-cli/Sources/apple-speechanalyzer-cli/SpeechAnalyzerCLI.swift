
// Apple Speech Analyzer CLI (macOS 26.0+)
// Build with: swift build -c release
// Usage:
//   .build/release/apple-speechanalyzer-cli \
//       --input-audio-path <path-to-audio> \
//       --output-txt-path <path-to-output> [--locale en-US] [--live]
//
// Requires: Xcode 26 beta command-line tools and macOS 26.0 runtime.

import Foundation
import AVFAudio
import Speech
import Darwin

@main
struct SpeechAnalyzerCLI {
    static func main() async throws {
        var inputPath: String?
        var outputPath: String?
        var localeIdentifier = Locale.current.identifier
        var liveMode = false

        var it = CommandLine.arguments.dropFirst().makeIterator()
        while let arg = it.next() {
            switch arg {
            case "--input-audio-path": inputPath  = it.next()
            case "--output-txt-path":  outputPath = it.next()
            case "--locale":           localeIdentifier = it.next() ?? localeIdentifier
            case "--live":            liveMode = true
            default:                   CLIUsage.exit()
            }
        }

        guard let inPath = inputPath, let outPath = outputPath else {
            CLIUsage.exit()
        }

        guard #available(macOS 26.0, *) else {
            fputs("Error: SpeechAnalyzer requires macOS 26.0 or newer.\n", stderr)
            Darwin.exit(EXIT_FAILURE)
        }

        let locale      = Locale(identifier: localeIdentifier)
        let transcriber = SpeechTranscriber(
            locale: locale,
            preset: liveMode ? .progressiveTranscription : .transcription
        )

        if !(await SpeechTranscriber.installedLocales).contains(locale) {
            FileHandle.standardError.write(Data("Downloading speech model for \(localeIdentifier)…\n".utf8))
            if let request = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
                try await request.downloadAndInstall()
            }
        }

        let analyzer    = SpeechAnalyzer(modules: [transcriber])
        let inputURL    = URL(fileURLWithPath: inPath)
        let audioFile   = try AVAudioFile(forReading: inputURL)
        let outputURL   = URL(fileURLWithPath: outPath)

        async let attrTranscript: AttributedString = transcriber.results.reduce(into: AttributedString("")) { partial, result in
            partial.append(result.text)
            partial.append(AttributedString(" "))
        }

        if let last = try await analyzer.analyzeSequence(from: audioFile) {
            try await analyzer.finalizeAndFinish(through: last)
        } else {
            await analyzer.cancelAndFinishNow()
        }

        let plainText = String((try await attrTranscript).characters)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        try plainText.write(to: outputURL, atomically: true, encoding: .utf8)
        print("✅ Saved transcript to \(outputURL.path)")
    }
}

enum CLIUsage {
    static func exit() -> Never {
        let prog = (CommandLine.arguments.first as NSString?)?.lastPathComponent ?? "apple-speechanalyzer-cli"
        fputs("""
Usage: \(prog) --input-audio-path <file> --output-txt-path <file> [--locale <id>] [--live]

Example:
  .build/release/\(prog) --input-audio-path demo.flac \
                         --output-txt-path demo.txt \
                         --locale en-US

""", stderr)
        Darwin.exit(EXIT_FAILURE)
    }
}
