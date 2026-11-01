# Website sources

The pages in the repo root (`index.html`, `contact.html`, `privacy.html`) and in the
language folders (`de/`, ...) are **generated**. Edit the sources here, then build:

```bash
python3 _src/build.py           # regenerate all pages
python3 _src/build.py --check   # list pages that are out of date (exit code 1 if any)
```

Python 3 only, no packages. Commit the generated files together with their sources.

## Layout

| Path | Purpose |
|---|---|
| `config.json` | Base URL, default language (served at the site root), language list (= switcher order), pages, App Store URL, legacy redirect folders (`gb`) |
| `templates/page.html` | Shared head, header, footer, language switcher, hreflang |
| `templates/redirect.html` | Stub for legacy URLs such as `/gb/` |
| `content/<lang>/lang.json` | Per language: own-language name, tagline, nav labels, copyright, App Store badge file and alt text, currency |
| `content/<lang>/<page>.html` | Per language and page: a metadata block, then the page body |

Assets: `images/screenshots/<lang>/` (four webp screenshots per language) and
`images/badges/` (App Store badge SVGs, one file per language).

## Page file format

```html
<!--
title: ...
og_title: ...
description: ...
og_description: ...
keywords: ...
-->
<h1>...</h1>
...body HTML, without header, footer or <main>...
```

Metadata values are plain text (write `&`, not `&amp;`). Tokens in the body, keep them as they are:
`{{root}}` (path to the site root), `{{lang}}` (language code), `{{app_store_badge}}` (App Store badge link).

## Adding a language

1. Copy `content/en/` to `content/<lang>/` and translate `lang.json` and the three pages
   (keep tokens and HTML structure; translate text, alt texts and metadata only).
2. Add the language code to `languages` in `config.json` (the code is also the folder name,
   e.g. `es`, `zh-Hans`).
3. Add the screenshots to `images/screenshots/<lang>/` and the badge to `images/badges/`.
4. Run the build. It warns about missing images.

Every other page picks up the new language in its switcher and hreflang list automatically.

## Changing the policy

Update the text in all languages and the "Last Updated" line in each `privacy.html`, then rebuild.
