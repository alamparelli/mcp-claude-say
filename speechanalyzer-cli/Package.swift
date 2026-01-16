// swift-tools-version: 6.2
import PackageDescription

let package = Package(
  name: "apple-speechanalyzer-cli",
  platforms: [ .macOS(.v26) ],
  targets: [
    .executableTarget(
      name: "apple-speechanalyzer-cli",
      linkerSettings: [
        .unsafeFlags([
          "-Xlinker","-sectcreate",
          "-Xlinker","__TEXT",
          "-Xlinker","__info_plist",
          "-Xlinker","Info.plist"   
        ])
      ]
    )
  ]
)
