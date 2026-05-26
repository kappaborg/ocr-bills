# Flutter Mobile App — Setup Guide

## 1. Install Flutter

```bash
# macOS via Homebrew
brew install --cask flutter

# Verify
flutter doctor
```

Accept all Android/iOS licenses:
```bash
flutter doctor --android-licenses
```

## 2. Scaffold the Flutter project

```bash
cd "/Users/kappasutra/OCR BILLS/mobile"
flutter create --project-name receipt_scanner_app --org com.yourname .
```

This generates the android/, ios/, test/ scaffolding. Your existing lib/ and pubspec.yaml files are already in place and will be preserved.

## 3. Install dependencies

```bash
flutter pub get
```

## 4. Configure Android

Open `android/app/src/main/AndroidManifest.xml` and add the contents from `android_config_notes.xml`.

Set minSdkVersion in `android/app/build.gradle`:
```gradle
defaultConfig {
    minSdkVersion 21
    ...
}
```

## 5. Configure iOS

Open `ios/Runner/Info.plist` and add the keys from `ios_config_notes.plist`.

Open `ios/Podfile` and set:
```ruby
platform :ios, '14.0'
```

Then run:
```bash
cd ios && pod install && cd ..
```

## 6. Set your backend URL

**Android emulator**: The default `http://10.0.2.2:8000` already points to your Mac's localhost.

**iOS simulator**: Change `AppConfig.baseUrl` in `lib/core/config/app_config.dart` to `http://localhost:8000`.

**Physical device**: Use your Mac's local IP (e.g., `http://192.168.1.100:8000`).

To pass it at build time:
```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.100:8000
```

## 7. Start the backend

```bash
cd "/Users/kappasutra/OCR BILLS/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 8. Run the app

```bash
# Android emulator or connected device
flutter run

# Specific device
flutter devices
flutter run -d <device_id>

# iOS simulator
flutter run -d iPhone
```

## 9. Build release

```bash
# Android APK
flutter build apk --release --dart-define=API_BASE_URL=https://your-api.com

# Android App Bundle (for Play Store)
flutter build appbundle --release --dart-define=API_BASE_URL=https://your-api.com

# iOS (requires Xcode + Apple Developer account)
flutter build ios --release --dart-define=API_BASE_URL=https://your-api.com
```

## Project Structure

```
lib/
├── main.dart                          # App entry point
├── core/
│   ├── api/api_client.dart            # Dio HTTP client with JWT interceptor
│   ├── api/endpoints.dart             # All API endpoint paths
│   ├── config/app_config.dart         # Base URL config
│   ├── routing/app_router.dart        # go_router with auth redirect
│   ├── storage/secure_storage.dart    # JWT token storage
│   └── theme/app_theme.dart           # Material 3 light/dark theme
├── features/
│   ├── auth/                          # Login, register, auth state
│   ├── scanner/                       # Camera scanning screen
│   ├── receipts/                      # Receipt list, detail, confirm
│   ├── dashboard/                     # Dashboard + insights + charts
│   ├── inventory/                     # Inventory + need-to-buy
│   └── settings/                      # Settings + CSV export
└── shared/
    ├── widgets/                       # Reusable UI components
    └── utils/                         # Formatters
```

## Key Features

| Screen | Route | Description |
|--------|-------|-------------|
| Dashboard | /home/dashboard | Spending summary, chart, recent receipts |
| Scanner | /home/scan | Camera capture with receipt overlay |
| Receipts | /home/receipts | Swipeable list with delete |
| Inventory | /home/inventory | Products + need-to-buy recommendations |
| Receipt Detail | /receipt/:id | Polls until processed, shows items |
| Confirm Items | /receipt/:id/confirm | Edit OCR-extracted items |
| Insights | /insights | Spending/frequency spike alerts |
| Export | /export | CSV export with filters |
| Settings | /settings | Change password, logout |
