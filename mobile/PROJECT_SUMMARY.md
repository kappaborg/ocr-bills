# OCR Bills — Flutter Mobile App: Complete Project Summary

---

## 1. Original Project

**Location:** `/Users/kappasutra/OCR BILLS/`
**Type:** Full-stack OCR receipt tracking web app

### Backend (`/backend/`)
- FastAPI 0.135.2, Python 3.11+, SQLAlchemy 2.0, SQLite
- JWT auth (HS256, 24h expiry), passlib password hashing
- Tesseract OCR (pytesseract + Pillow), multi-script support for 30+ languages
- Rule-based receipt parser (regex + keyword matching, 25+ languages)
- Virtual environment: `/Users/kappasutra/OCR BILLS/backend/venv/`
- Start command:
```bash
source "/Users/kappasutra/OCR BILLS/backend/venv/bin/activate"
cd "/Users/kappasutra/OCR BILLS/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend (`/backend/frontend/`)
- Next.js 14, React 18, TypeScript, Tailwind CSS
- **Replaced entirely by this Flutter app**

---

## 2. Flutter Mobile App

**Location:** `/Users/kappasutra/OCR BILLS/mobile/`
**Targets:** iOS + Android

### Architecture
- State management: `flutter_riverpod` (StateNotifierProvider, FutureProvider)
- Navigation: `go_router` with StatefulShellRoute (bottom nav tabs)
- HTTP: `dio` with JWT Bearer interceptor + 401 auto-logout
- Secure storage: `flutter_secure_storage` for JWT token

### Key Dependencies (`pubspec.yaml`)
```yaml
flutter_riverpod: ^2.5.1
go_router: ^13.2.0
dio: ^5.4.3+1
flutter_secure_storage: ^9.2.2
camera: ^0.10.5+9
image_picker: ^1.1.2
image_cropper: ^7.1.0
fl_chart: ^0.68.0
cached_network_image: ^3.3.1
shimmer: ^3.0.0
intl: ^0.19.0
permission_handler: ^11.3.1
path_provider: ^2.1.3
share_plus: ^9.0.0
open_file: ^3.3.2
```

### File Structure (47 files)
```
lib/
├── main.dart
├── core/
│   ├── api/
│   │   ├── api_client.dart          # Dio instance + JWT interceptor + error mapping
│   │   ├── api_exception.dart       # AppException class
│   │   └── endpoints.dart           # All API path constants
│   ├── config/
│   │   └── app_config.dart          # Base URL (dart-define or default IP)
│   ├── routing/
│   │   └── app_router.dart          # go_router + auth redirect + bottom nav shell
│   ├── storage/
│   │   └── secure_storage.dart      # JWT read/write/delete
│   └── theme/
│       └── app_theme.dart           # Material 3, light/dark, status colours
├── features/
│   ├── auth/
│   │   ├── data/auth_repository.dart
│   │   ├── models/user.dart
│   │   ├── presentation/login_screen.dart
│   │   ├── presentation/register_screen.dart
│   │   └── providers/auth_provider.dart
│   ├── scanner/
│   │   ├── data/scanner_repository.dart
│   │   ├── presentation/scanner_screen.dart
│   │   └── presentation/widgets/camera_overlay.dart
│   ├── receipts/
│   │   ├── data/receipts_repository.dart
│   │   ├── models/receipt.dart
│   │   ├── models/receipt_item.dart
│   │   ├── presentation/receipts_list_screen.dart
│   │   ├── presentation/receipt_detail_screen.dart
│   │   ├── presentation/receipt_confirm_screen.dart
│   │   └── providers/receipts_provider.dart
│   ├── dashboard/
│   │   ├── data/dashboard_repository.dart
│   │   ├── models/insights.dart
│   │   ├── presentation/dashboard_screen.dart
│   │   ├── presentation/insights_screen.dart
│   │   ├── presentation/widgets/spending_chart.dart
│   │   └── providers/dashboard_provider.dart
│   ├── inventory/
│   │   ├── data/inventory_repository.dart
│   │   ├── models/inventory_item.dart
│   │   ├── presentation/inventory_screen.dart
│   │   └── providers/inventory_provider.dart
│   └── settings/
│       ├── presentation/settings_screen.dart
│       └── presentation/export_screen.dart
└── shared/
    ├── widgets/
    │   ├── confidence_indicator.dart
    │   ├── error_view.dart
    │   ├── loading_skeleton.dart
    │   ├── receipt_card.dart
    │   └── status_badge.dart
    └── utils/
        ├── currency_formatter.dart
        └── date_formatter.dart
```

### Screens & Routes
| Route | Screen | Description |
|-------|--------|-------------|
| `/splash` | SplashScreen | Auth check on startup |
| `/login` | LoginScreen | Email + password login |
| `/register` | RegisterScreen | New account creation |
| `/home/dashboard` | DashboardScreen | Spending summary, bar chart, recent receipts |
| `/home/scan` | ScannerScreen | Full-screen camera + receipt frame overlay |
| `/home/receipts` | ReceiptsListScreen | Swipe-to-delete list with status badges |
| `/home/inventory` | InventoryScreen | Products + need-to-buy recommendations |
| `/receipt/:id` | ReceiptDetailScreen | Metadata, image, items, 2s status polling |
| `/receipt/:id/confirm` | ReceiptConfirmScreen | Inline item editing before confirm |
| `/insights` | InsightsScreen | Frequency + spending spike alerts |
| `/settings` | SettingsScreen | Change password, logout |
| `/export` | ExportScreen | CSV export with date/category filters |

---

## 3. Setup Steps (One-Time)

### Step 1 — Install Flutter
```bash
brew install --cask flutter
flutter doctor --android-licenses
```

### Step 2 — Scaffold & Install Dependencies
```bash
cd "/Users/kappasutra/OCR BILLS/mobile"
flutter create --project-name receipt_scanner_app --org com.yourname .
flutter pub get
```

### Step 3 — iOS Pods
```bash
cd ios && pod install && cd ..
```

### Step 4 — Java Fix (Critical)
System Java was OpenJDK 25 (Homebrew) — incompatible with Android Gradle Plugin.
Fixed by pinning to Temurin Java 21 in `android/gradle.properties`:
```
org.gradle.java.home=/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home
```
Also updated `android/app/build.gradle.kts`:
```kotlin
compileOptions {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}
kotlinOptions {
    jvmTarget = JavaVersion.VERSION_21.toString()
}
```

### Step 5 — Android Manifest
Added to `android/app/src/main/AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.CAMERA"/>
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32"/>
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES"/>
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" android:maxSdkVersion="29"/>
<uses-feature android:name="android.hardware.camera" android:required="false"/>
```
Also added `android:usesCleartextTraffic="true"` to `<application>` tag for local HTTP.

### Step 6 — iOS Info.plist
Added to `ios/Runner/Info.plist`:
```xml
<key>NSCameraUsageDescription</key>
<string>We need camera access to scan your receipts.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>We need photo library access to upload receipts from your gallery.</string>
<key>NSPhotoLibraryAddUsageDescription</key>
<string>We save cropped receipt images to your photo library.</string>
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
</dict>
```

### Step 7 — iOS Podfile
Set minimum iOS version in `ios/Podfile`:
```ruby
platform :ios, '14.0'
```

### Step 8 — Backend URL
Set in `lib/core/config/app_config.dart` to the Mac's local IP for physical device:
```dart
defaultValue: 'http://192.168.100.53:8000',
```
Override at build time:
```bash
flutter run --dart-define=API_BASE_URL=http://YOUR_IP:8000
```

---

## 4. Bugs Found & Fixed

### Bug 1 — Login silently failing → reload login screen (Flutter)
**Symptom:** After registering or logging in, app just reloads the login screen with no error.

**Root cause:** `/auth/me` returns only `{"id", "email"}` — no `created_at` field.
`User.fromJson` called `DateTime.parse(json['created_at'] as String)` on `null`, throwing a TypeError.
`AsyncValue.guard` caught it silently, set auth state to error, router saw `isAuth = false` and redirected back to `/login`.

**Fixes applied:**
- `lib/features/auth/models/user.dart` — made `createdAt` nullable, used `DateTime.tryParse` with null check:
```dart
createdAt: json['created_at'] != null
    ? DateTime.tryParse(json['created_at'] as String)
    : null,
```
- `lib/features/auth/providers/auth_provider.dart` — replaced `AsyncValue.guard` with explicit try/catch that resets state to `null` then re-throws so login screen can show the error in a snackbar:
```dart
try {
  final user = await _repo.login(email, password);
  state = AsyncValue.data(user);
} catch (e, st) {
  state = const AsyncValue.data(null);
  Error.throwWithStackTrace(e, st);
}
```

---

### Bug 2 — "Google Vision OCR is not configured" processing error (Backend)
**Symptom:** Every scanned receipt shows `processing_error: "Google Vision OCR is not configured in this MVP scaffold."` and status stays `error`.

**Root cause:** `.env` had `GOOGLE_VISION_API_KEY` set to a real API key value.
`ocr.py` line 184 checks `if settings.GOOGLE_VISION_API_KEY: raise RuntimeError(...)` — with a truthy key, it raised instead of falling through to Tesseract.

**Fix:** Cleared the key in `backend/.env`:
```
GOOGLE_VISION_API_KEY=""
```
**Backend restart required** after this change.

---

### Bug 3 — `type Null is not a subtype of type int` in Receipts tab (Backend)
**Symptom:** Opening the Receipts tab crashes with a Dart type cast error.

**Root cause:** `GET /receipts` list endpoint returned:
```json
[{"receipt_id": 1, "processing_status": "confirmed"}]
```
Only 2 fields, with key `receipt_id` (not `id`). Flutter's `Receipt.fromJson` reads `json['id'] as int` — `null as int` crashes.

**Fix:** Changed `backend/app/api/routes/receipts.py` list endpoint from returning `ReceiptUploadResult` to returning full `ReceiptOut` objects:
```python
@router.get("", response_model=list[ReceiptOut])
def list_receipts(db, user):
    receipts = (
        db.query(Receipt)
        .options(selectinload(Receipt.items))
        .filter(Receipt.user_id == user.id)
        .order_by(Receipt.id.desc())
        .limit(50)
        .all()
    )
    return [_get_receipt_out(r) for r in receipts]
```

---

### Bug 4 — Change password API mismatch (Backend + Flutter)
**Symptom:** Changing password in Settings would fail with a 422 validation error.

**Root cause:** Backend `/auth/profile` requires both `current_password` and `new_password`, but Flutter was only sending `new_password`.

**Fixes applied:**
- `auth_repository.dart` — added `currentPassword` parameter
- `auth_provider.dart` — updated `changePassword` signature
- `settings_screen.dart` — added "Current Password" field to the UI

---

## 5. Run Commands

### Start Backend
```bash
source "/Users/kappasutra/OCR BILLS/backend/venv/bin/activate"
cd "/Users/kappasutra/OCR BILLS/backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Run on Android — OnePlus A6000 (device ID: `6f7955e6`)
```bash
cd "/Users/kappasutra/OCR BILLS/mobile"
flutter run -d 6f7955e6 --dart-define=API_BASE_URL=http://192.168.100.53:8000
```

### Run on iPhone (device ID: `00008130-0012694A0182001C`)
> Requires **Developer Mode ON**: Settings → Privacy & Security → Developer Mode → ON, then restart iPhone.
```bash
cd "/Users/kappasutra/OCR BILLS/mobile"
flutter run -d 00008130-0012694A0182001C --dart-define=API_BASE_URL=http://192.168.100.53:8000
```

### Check Connected Devices
```bash
flutter devices
```

### Hot Reload / Restart (while app is running)
```
r  → Hot reload (instant UI update)
R  → Hot restart (full state reset)
q  → Quit
```

---

## 6. Known Remaining Items

| Item | Status | Notes |
|------|--------|-------|
| iPhone Developer Mode | Pending | Settings → Privacy & Security → Developer Mode |
| Android SDK version | Warning | SDK 34 installed, Flutter 3.41 wants 36. Builds work; upgrade via Android Studio if needed |
| `open_file` macOS warning | Harmless | Package doesn't support macOS; iOS/Android unaffected |
| Backend rate limiting | MVP only | In-memory token bucket, single-process only. Needs Redis for multi-worker production |
| Receipt processing notifications | Not implemented | App polls every 2s; no push notifications |
| Release build signing | Not configured | Needs Android keystore + Apple Developer account for store deployment |
| Google Vision OCR | Disabled | Key cleared; Tesseract handles all OCR. Re-enable if Vision is ever implemented |

---

## 7. Current Working State

| Feature | Status |
|---------|--------|
| Register / Login | ✅ Working |
| JWT auth + auto-logout on 401 | ✅ Working |
| Camera scanner + receipt overlay | ✅ Working |
| Tesseract OCR via backend | ✅ Working |
| Receipt list (all fields) | ✅ Working |
| Receipt detail + 2s status polling | ✅ Working |
| Confirm / edit items | ✅ Working |
| Dashboard + spending chart | ✅ Working |
| Inventory + need-to-buy | ✅ Working |
| Insights screen | ✅ Working |
| CSV export + share | ✅ Working |
| Change password | ✅ Working |
| Android (OnePlus A6000) | ✅ Running |
| iPhone 15 Pro | ⏳ Pending Developer Mode |
