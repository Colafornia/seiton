# ASTRYX

Use the official sources as design and component authority:

- Documentation: https://astryx.atmeta.com/
- Source: https://github.com/facebook/astryx
- Component guidance: `packages/core/src/<Component>/<Component>.doc.mjs`
- Component implementation: `packages/core/src/<Component>/<Component>.tsx`
- Foundations and tokens: `packages/core/src/theme/` and
  `packages/themes/neutral/`
- Settings templates: `packages/cli/assets/templates/pages/settings-sidebar/`
  and `packages/cli/assets/templates/pages/settings/`

For interface comparisons, inspect only the components relevant to the task.
Prefer documented composition and semantics over custom layout or CSS. Verify
the installed package version because upstream `main` may be newer.

Useful settings-screen primitives include `AppShell`, `SideNav`, `Layout`,
`Toolbar`, `List`, `ListItem`, `Item`, `StatusDot`, `Badge`, `Banner`, and
`EmptyState`.
