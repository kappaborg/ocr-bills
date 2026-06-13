import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

/// Minimal PostHog event client over plain HTTP. No SDK, no native bridge —
/// so we don't inherit the posthog_flutter package's Kotlin compile issues.
/// Trade-off: no session replay (SDK-only). We keep custom events and
/// user identification, which is what the 10-friend beta actually needs.
///
/// Pass the project key at build time:
///   --dart-define=POSTHOG_API_KEY=phc_...
/// All calls no-op when the key is empty so dev builds and CI don't
/// pollute the production dataset.
class Analytics {
  static const _key = String.fromEnvironment('POSTHOG_API_KEY');
  // Default is the US host because that's where the beta project lives.
  // PostHog's /capture/ endpoint always returns HTTP 200 — even for an
  // unrecognised api_key — so a wrong-region build looks like it's
  // working in our smoke tests but no events land. Verified empirically:
  // /decide returned 200 on us.i.posthog.com and 401 on eu.i.posthog.com
  // for this project's key.
  static const _host = String.fromEnvironment(
    'POSTHOG_HOST',
    defaultValue: 'https://us.i.posthog.com',
  );

  static String? _distinctId;
  static Map<String, Object>? _userProps;

  static bool get enabled => _key.isNotEmpty;

  /// Best-effort init. Generates an anonymous distinct_id until login
  /// supplies a real one. Safe to call once on app start.
  static Future<void> init() async {
    if (!enabled) return;
    _distinctId = 'anon-${DateTime.now().millisecondsSinceEpoch}';
    // Fire-and-forget; never await network on app start.
    unawaited(capture('app_open', {
      'platform': Platform.operatingSystem,
      'os_version': Platform.operatingSystemVersion,
    }));
  }

  /// Attach the real user id once they log in. PostHog stitches the
  /// pre-login anonymous session to this id via $identify.
  static Future<void> identify(int userId, {String? email}) async {
    if (!enabled) return;
    final previous = _distinctId;
    _distinctId = userId.toString();
    _userProps = {if (email != null) 'email': email};
    unawaited(_send({
      'event': r'$identify',
      'distinct_id': _distinctId,
      'properties': {
        r'$anon_distinct_id': previous,
        r'$set': _userProps,
      },
    }));
  }

  /// On logout, generate a fresh anonymous id so subsequent events
  /// aren't attributed to the previous user.
  static Future<void> reset() async {
    if (!enabled) return;
    _distinctId = 'anon-${DateTime.now().millisecondsSinceEpoch}';
    _userProps = null;
  }

  /// Capture a single custom event. Properties are flat key→value pairs.
  static Future<void> capture(String event, [Map<String, Object>? props]) async {
    if (!enabled) return;
    unawaited(_send({
      'event': event,
      'distinct_id': _distinctId ?? 'anon-unknown',
      'properties': props ?? const {},
    }));
  }

  static Future<void> _send(Map<String, Object?> body) async {
    try {
      final payload = {
        'api_key': _key,
        'timestamp': DateTime.now().toUtc().toIso8601String(),
        ...body,
      };
      await http
          .post(
            Uri.parse('$_host/capture/'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 8));
    } catch (e) {
      if (kDebugMode) debugPrint('Analytics send failed: $e');
    }
  }
}
