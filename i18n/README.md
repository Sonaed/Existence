# Localization framework

Qt applications use `.ts` catalogs compiled to `.qm` at release time. JavaScript
surfaces use message catalogs keyed by stable IDs, never translated text as a
storage key. English is the source locale; French is the first maintained
translation. Dates, numbers, paths, and file formats remain locale-neutral in
persistent data.
