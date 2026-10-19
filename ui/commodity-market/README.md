# Commodity market presentation

A dependency-free, display-only homepage with desktop and mobile layouts.

## Features

- English is the default. Explicit `?lang=` selection supports `en`, `zh-Hans`, `zh-Hant`, `fr`, `es`, and `ja`.
- The category order is Gold, Silver, Copper, Iron Ore, Crude Oil, Coal, Soybeans, Corn.
- Desktop shows eight reference tiles and eight commodity cards. Mobile uses a two-column category selector with a focused commodity card and a product-details dialog.
- Navigation and the footer link to `https://8415wallet.com:9446/v3/web/index.html` in every language.
- All assets are local. No analytics, wallet provider, API request, signing, order submission, or blockchain transaction is initiated.
- Prices and quantities are unavailable (`—`). Product illustrations and the `DEMO` label do not represent live assets or executable orders.

## Static hosting

Publish the contents of this directory as the HTTPS document root. Keep `assets/`, `styles.css`, `locales.js`, and `app.js` at their relative paths. The document requires no server-side code or package installation. Do not proxy application or transaction endpoints into this display-only origin.

Use ordinary certificate validation, correct asset MIME types, `X-Content-Type-Options: nosniff`, and an HTTPS-only deployment. SVG files retain their authored dimensions. The three raster files retain their existing asset bytes.

## Application integration

Stable commodity identifiers are in `app.js`. `data-commodity` and the `commodity-<id>` anchors identify the display categories. They are not NFT identifiers. Preserve original NFT identity, quantity, source status, reference observations, units and settlement currencies when integrating the existing application. Do not promote display fields into verified business records.

Language changes retain the bounded search query. Unsupported languages fall back to English. No locale inference from the browser changes the initial default. Search and category selection affect only the local view.

## Acceptance

Rendered browser and deployment checks remain outstanding for this revision. Verify the default English page, all six language selections, fixed eight-category ordering, narrow-screen navigation, keyboard focus, search, dialog close/Escape, local asset delivery, both wallet links, and absence of service requests. Confirm the exact served source and HTTPS certificate chain separately from source publication.
