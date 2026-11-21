# Alili Cortex

Original Flutter chat application and Cloudflare Worker backend, built specifically in this repository.

## AC architecture

The approved architecture baseline is documented in [AC Master Architecture v1](docs/AC-MASTER-ARCHITECTURE-v1.md). It defines the single AC Assistant experience, AC Master Core, specialist brains, shared knowledge and skill exchange, memory, the Intelligence Foundry, permissioned execution, free-first governance and a staged implementation roadmap.

The architecture document is a design contract, not a claim that every planned capability is already implemented. Work is developed on feature branches and remains subject to review; no change is merged into `main` without explicit approval.

## Current implementation

- Arabic RTL single-chat interface.
- Local image and file selection with previews. Uploading attachments is not implemented yet and the app will not pretend they were sent.
- Secure on-device storage for the Worker URL and personal API access token.
- Authenticated text chat through `POST /v1/chat`.
- Sequential fallback between explicitly enabled providers.
- Server-side provider credentials; no provider API key is shipped in the Flutter app.
- Worker and Flutter automated tests plus Android release build in GitHub Actions.

## Connect the Android app

1. Deploy the Worker from the `worker/` directory using your own Cloudflare account.
2. Set the Worker secret `APP_API_KEY` to a long random value. This is the personal access token entered in the app.
3. Add provider credentials as Worker secrets. Enable a provider only after checking its current free-tier terms, quotas, and billing requirements; then set its matching `FREE_*_CONFIRMED` variable to `true`.
4. Install the app, open the connection settings (tune icon), and enter the Worker HTTPS URL and the same personal access token.
5. Send a text message to verify the live connection.

The app stores the access token using Android encrypted secure storage. It is not committed to this repository. Do not paste provider API keys into the app; those belong only in Worker secrets.

## Current limitations

Search, autonomous execution, image generation, video/audio, persistent conversation sync, and attachment upload are not implemented yet. Their buttons or UI must not be interpreted as proof that those services are active. The search and execution switches currently prevent a misleading chat request and show an explanatory message.

## Tests

- Worker: `cd worker && npm test`
- Flutter: `flutter pub get && flutter analyze && flutter test`
- Android: `flutter build apk --release`

See `worker/README.md` for backend configuration and deployment details.

## Branding and connection diagnostics

The Android launcher icon is generated from the Alili Cortex mark during the CI Android build. The app's connection settings include an authenticated check against `/v1/providers/status`, so a saved URL and access key can be verified before starting a chat.
