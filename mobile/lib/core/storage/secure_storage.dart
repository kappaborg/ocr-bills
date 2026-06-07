import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorage {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  static const _tokenKey = 'jwt_token';
  static const _themeKey = 'theme_mode';

  static Future<void> saveToken(String token) =>
      _storage.write(key: _tokenKey, value: token);

  static Future<String?> getToken() => _storage.read(key: _tokenKey);

  static Future<void> deleteToken() => _storage.delete(key: _tokenKey);

  // Theme preference: "light" | "dark" | "system". Stored alongside the token
  // so we don't need a second storage backend for one tiny pref.
  static Future<void> saveTheme(String value) =>
      _storage.write(key: _themeKey, value: value);

  static Future<String?> getTheme() => _storage.read(key: _themeKey);

  static const _onboardedKey = 'onboarded_v1';
  static const _displayCurrencyKey = 'display_currency';

  static Future<bool> getOnboarded() async =>
      (await _storage.read(key: _onboardedKey)) == '1';

  static Future<void> setOnboarded() =>
      _storage.write(key: _onboardedKey, value: '1');

  static Future<String?> getDisplayCurrency() =>
      _storage.read(key: _displayCurrencyKey);

  static Future<void> saveDisplayCurrency(String code) =>
      _storage.write(key: _displayCurrencyKey, value: code);
}
