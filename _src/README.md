# Website sources

The pages in the repo root (`index.html`, `contact.html`, `privacy.html`) and in the language
folders (`de/`, ...) are **generated**. Edit the sources here, then build:

```bash
python3 _src/build.py              # validate the content, then (re)generate all pages
python3 _src/build.py --validate   # validate the content only, write nothing
python3 _src/build.py --check      # validate, then list generated pages that are out of date (-c)
python3 _src/build.py --lang tr    # restrict validation and build to one language (repeatable)
python3 _src/build.py --help       # all options
```

Python 3 only, no packages. Commit the generated files together with their sources.
An invalid content file stops the build with the exact location of each problem.

## Layout

| Path | Purpose |
|---|---|
| `config.json` | Base URL, default language (served at the site root), language list (= switcher order), pages, App Store URL, contact details, legacy redirect folders (`gb`) |
| `content/<lang>.json` | **All content of one language**: names, labels, metadata and the page blocks |
| `schema/content.schema.json` | The format of `content/<lang>.json` (JSON Schema). The contract for everything that writes content |
| `blocks.py` | The HTML of each block type |
| `templates/page.html` | Shared head, header, footer, language switcher, hreflang |
| `templates/redirect.html` | Stub for legacy URLs such as `/gb/` |
| `validate.py` | Schema validation and the cross-language structure check |

Assets: `images/screenshots/<lang>/` (screenshots) and `images/badges/` (App Store badges, one SVG per language).

## Content file (`content/<lang>.json`)

Top level: `name` (language name in that language, shown in the switcher), `tagline`, `icon_alt`, `nav`
(`home`, `privacy`, `contact`), `copyright`, `badge_file`, `badge_alt`, `currency`, `contact`
(`phone_label`, `email_label`, `country`) and `pages` with `index`, `contact` and `privacy`.
Each page has `title`, `og_title`, `description`, `og_description`, `keywords` and a list of `blocks`.
The postal address, phone number and email are language independent and live in `config.json`.

### Block types

Every block has a stable `id` (identical in all languages) and a `type`:

| type | fields |
|---|---|
| `hero` | `heading`, optional `subtitle`, optional `screenshots` (1 or 2) |
| `section` | optional `heading`, optional `divider` (false = no line above), `content`: list of elements |
| `download` | `text` (App Store badge below it) |
| `feature` | `heading`, `intro`, optional `reverse`, `screenshot`, `items` (each with `title`, `text`) |
| `trust` | optional `variant` (`default`, `feature`, `last`), `heading`, optional `emphasis`, `paragraphs` |
| `final_cta` | (App Store badge only) |

Elements of a `section`: `{"type": "p", "text": ...}`, `{"type": "h3", "text": ...}`,
`{"type": "list", "items": [...]}` and `{"type": "contact_box"}` (address from `config.json`).
A screenshot is `{"name": "Projects", "alt": "...", "dark": true}`; `dark` is only set for dark-mode images.

### Text

Fields are plain text in the language itself, with the real characters (write `&`, not `&amp;`).
Fields that take **inline text** (paragraphs, list items, subtitles, intros, item texts) allow only:

- `**bold**`
- `[link text](https://example.com)`
- `{site_link}`: link to this language's start page (used in the privacy policy)

HTML is rejected by the validator.

### Structure is the same in every language

The default language (`en`) defines the structure. Every other language must have the same pages, the
same blocks with the same `id`s in the same order, the same block types and options, the same number of
paragraphs, list items and feature items, and the same screenshot names. Only the wording differs.
`--validate` reports every deviation.

## Adding a language

1. Copy `content/en.json` to `content/<lang>.json` and translate it (keep the structure, the ids and
   the screenshot names; translate text, alt texts and metadata). The code is also the folder name,
   e.g. `es` or `zh-Hans`.
2. Add the code to `languages` in `config.json`.
3. Put the screenshots into `images/screenshots/<lang>/` and the badge into `images/badges/`.
4. Run `python3 _src/build.py --lang <lang>` (validates and builds that language), later the full build.
   The build warns about missing images.

Every other page gets the new language in its switcher and hreflang list automatically.

## Changing the policy

Update the text in all languages and the "Last Updated" line (the `subtitle` of the privacy `hero`), then rebuild.
