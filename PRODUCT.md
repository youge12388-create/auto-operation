# Content Ops

## Product truth

Content Ops is an internal, single-tenant AI content operations workspace. Its job is to turn collected information sources into human-reviewed article drafts, with an explicit operator in the loop before WeChat draft creation or publication.

## Primary operator flow

1. Review collected materials and keep useful items in the material library.
2. Scan hot sources and review AI topic suggestions.
3. Select a topic and a writing strategy to start generation.
4. Edit and preview the article, then review it.
5. Create a WeChat draft, or submit for publication only when the configured channel allows it.

## Product constraints

- Human review remains visible and cannot be hidden behind automatic publishing.
- Existing API-backed actions and WeChat draft creation must remain usable.
- The first redesign pass is front-end focused; provider, model, source ingestion, and publication behavior are not re-architected here.
