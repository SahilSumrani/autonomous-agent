# Technology Detection

## Observable Signatures
The technology detector inspects DOM artifacts, script URLs, meta tags, and headers to identify:

- **CMS & Website Builders**: WordPress, Shopify, WooCommerce, Magento, Webflow, Wix, Squarespace
- **Frontend Frameworks**: React, Next.js, Vue, Nuxt, Angular, Svelte
- **Backend Stacks**: Node.js, PHP, Laravel, Django, Ruby on Rails
- **Analytics & Tracking**: Google Analytics (GA4/UA), Google Tag Manager, Meta Pixel, Hotjar, Microsoft Clarity
- **CDN & Infrastructure**: Cloudflare, Vercel, Netlify, AWS (CloudFront/S3)

## Non-Hallucination Policy
Technologies are reported only when verified matching regex patterns are satisfied with confidence >= 0.85. If evidence is ambiguous, the stack remains unassigned rather than guessed.
