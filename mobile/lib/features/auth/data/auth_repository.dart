import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/endpoints.dart';
import '../../../core/storage/secure_storage.dart';
import '../models/user.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(ref.read(apiClientProvider));
});

class AuthRepository {
  final ApiClient _api;
  AuthRepository(this._api);

  Future<User> login(String email, String password) async {
    final res = await _api.post(Endpoints.login, data: {'email': email, 'password': password});
    final token = res.data['access_token'] as String;
    await SecureStorage.saveToken(token);
    return getMe();
  }

  Future<User> register(String email, String password) async {
    await _api.post(Endpoints.register, data: {'email': email, 'password': password});
    return login(email, password);
  }

  Future<User> getMe() async {
    final res = await _api.get(Endpoints.me);
    return User.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> changePassword(String currentPassword, String newPassword) async {
    await _api.patch(Endpoints.profile, data: {
      'current_password': currentPassword,
      'new_password': newPassword,
    });
  }

  Future<void> logout() async {
    await SecureStorage.deleteToken();
  }
}
