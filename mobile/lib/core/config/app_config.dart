class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    // Android emulator → host localhost; change for physical device or production.
    // Port 8765 because 8000/8001/8002 are occupied locally by unrelated services.
    defaultValue: 'http://192.168.100.63:8765',
  );
}
