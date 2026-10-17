# Study Quest Android build

This work is isolated on the `android-mobile-build` branch. No original Flask source files were changed.

## Automated APK build
The GitHub Actions workflow **Build Study Quest Android APK** builds a debug APK when this branch is updated. Open the repository's Actions tab, select the latest workflow run, and download the `Study-Quest-debug-APK` artifact. Extract it to get `app-debug.apk`, then transfer it to your Android phone to install.

## App behavior
- Android-first Study Quest home screen with dark/light theme.
- Opens the existing Render-hosted Flask app in a secure browser tab.
- Schedules and cancels daily local Android notifications.
- Firebase and AI secrets stay on the server; do not put API keys in this app.

## Build limitations
The workflow builds a debug APK for sideloaded testing, not a signed Play Store release. Test login, Google sign-in, dashboard, AI features, notification scheduling and cancellation on a real phone before relying on it.