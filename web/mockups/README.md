# M0-4 static mockups

Open any `.html` file directly in a browser (no server needed).
Colours, sizes and symbols come only from `web/src/design/tokens.ts`.

After changing `tokens.ts`:

```bash
node --experimental-strip-types web/scripts/mockup-assets.mjs          # regenerate assets/
node --experimental-strip-types web/scripts/mockup-assets.mjs --check  # verify tokens-only
```
