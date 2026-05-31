class AppConfig {
  /// Base URL of the ExTaSy backend.
  ///
  /// Default is the public Hugging Face Spaces deploy at
  /// https://kappasutra-extasy-backend.hf.space — the app works on a phone
  /// without any LAN setup, no IP juggling, no Mac in the loop.
  ///
  /// For local backend development, override at build time:
  ///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8765   # Android emulator
  ///   flutter run --dart-define=API_BASE_URL=http://192.168.X.X:8765 # physical device + Mac
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://kappasutra-extasy-backend.hf.space',
  );
}
