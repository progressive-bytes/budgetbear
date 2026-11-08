# Website sources

The pages in the repo root (`index.html`, `contact.html`, `privacy.html`) and in the language
folders (`de/`, ...) are **generated**. Edit the sources here, then build:

```bash
python3 _src/build.py              # the whole build: validate, copy the badges, convert the screenshots, generate the pages
python3 _src/build.py --build-only # only validate and generate the pages (leave badges and screenshots alone)
python3 _src/build.py --validate   # validate the content only, write nothing
python3 _src/build.py --check      # show what a build would change, write nothing (-c)
python3 _src/build.py --verify     # the final check before uploading: is everything complete and correct? (read-only)
python3 _src/build.py --lang tr    # restrict the build to one language (repeatable)
python3 _src/build.py --force      # copy the badges and convert the screenshots again even if they are up to date
python3 _src/build.py --help       # all options
```

Python 3 only, no packages (converting screenshots needs `cwebp`, macOS: `brew install webp`). Commit the generated files together with their sources.
One build handles everything in the right order: the badges and screenshots are copied and converted first, because the pages link to the files that exist.
Only languages that have a content file are built, and all steps treat them the same way. A step whose source folder is not available
(for example on another machine) is skipped with a message; a missing file for an existing language is reported as a problem (exit code 1).
An invalid content file stops the build with the exact location of each problem.

## Layout

| Path | Purpose |
|---|---|
| `config.json` | Base URL, default language (served at the site root), languages, App Store locale table, pages, App Store URL, contact details, legacy redirect folders (`gb`) |
| `content/<lang>.json` | **All content of one language**: names, labels, metadata and the page blocks |
| `schema/content.schema.json` | The format of `content/<lang>.json` (JSON Schema). The contract for everything that writes content |
| `blocks.py` | The HTML of each block type |
| `templates/page.html` | Shared head, header, footer, language switcher, hreflang |
| `templates/redirect.html` | Stub for legacy URLs such as `/gb/` |
| `validate.py` | Schema validation and the cross-language structure check |
| `verify.py`, `verify.json` | The final check (`--verify`) and its settings |
| `badges.py`, `screenshots.py` | The badge and screenshot steps. `build.py` runs them; run them alone only for `--list` or to debug |
| `sitecfg.py` | Configuration helpers shared by the scripts |

## Languages (`config.json`)

`languages` lists every language the website is planned to have, in switcher order. An entry has:

- `code`: the language tag (`en`, `de`, `zh-Hans`). It is used for `<html lang>`, hreflang and the content file name `content/<code>.json`.
- `dir` (optional, default = `code`): the URL folder, which also holds the language's `images/` folder, **taken from the URL infix in the App Store
  metadata** (`.../budgetbear/<dir>/privacy`). It differs from the code where the existing URLs do, e.g. `zh-Hans` -> `zh`, `zh-Hant` -> `tw`.
  The default language lives at the site root, so its images are in the root `images/`.
- `source_locale`: the App Store metadata locale used as the reference for terminology and tone when this language is written.

`app_store_locales` maps every App Store locale to the website language that serves its URLs
(e.g. `pt-BR` and `pt-PT` -> `pt`; locales without a page of their own -> `en`).

A language becomes **active** when `content/<code>.json` exists. Switchers and hreflang lists only contain active
languages; the others are reported as "pending". The build rejects reserved or shared folder names.

Images: each language has its own `images/` folder next to its pages (`de/images/`, `es/images/`; for the default language the root `images/`) with its four screenshots and its App Store badge. The root `images/` also holds the shared assets (app icon, favicons). A badge that a language does not have of its own is taken from the root `images/` folder.
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

1. Make sure the language is in `languages` in `config.json` (with `dir` and `source_locale`) and that its App Store
   locales are in `app_store_locales`.
2. Copy `content/en.json` to `content/<code>.json` and translate it (keep the structure, the ids and
   the screenshot names; translate text, alt texts and metadata).
3. Check that `source_locale` points to the fastlane locale folder with the screenshots (or add an entry under `locales` in `screenshots.json`)
   and that the badge file named in the content file exists in the badge download.
4. Run `python3 _src/build.py`. It creates `<dir>/images/` with the badge and the screenshots and generates the pages.
   `--lang <code>` restricts it to that language.

Every other page gets the new language in its switcher and hreflang list automatically.

## Changing the policy

Update the text in all languages and the "Last Updated" line (the `subtitle` of the privacy `hero`), then rebuild.

## Before uploading: `python3 _src/build.py --verify`

Run this once at the end, after the build. It changes nothing and ends with `RESULT: OK` or a list of errors (exit code 1).
Errors mean the website is not ready to upload; warnings are worth a look. It checks:

- the pages of every language exist (`index`, `contact`, `privacy`) and are up to date with the sources; the legacy redirect folders are there;
  no page folder of a language that is not built is left over; every language in `config.json` has content (a language that an App Store locale links to must not be missing);
- every page: well formed, correct `<html lang>`, title and description, canonical URL, `og:url`, hreflang list (all languages and `x-default`) and structured data;
- the language switcher of every page lists every language, in order, with the right links;
- every link, image, stylesheet and icon on every page resolves to an existing file;
- every language shows **its own** badge and screenshots from its own `images/` folder; badge files are valid SVGs, screenshots are valid webp files
  of the configured width with a consistent aspect ratio; a language that shows the default language's badge is an error (unless listed under `allow_default_badge`);
- pages of other languages are not left in English (title and description);
- the App Store URLs (`support_url.txt`, `marketing_url.txt`, `privacy_url.txt`) of every locale lead to existing pages, and the URL files in the fastlane metadata match;
- warnings: unused files in a language's `images/` folder, files larger than `max_asset_kb`, screenshots that are byte-identical in two languages,
  and shown files that are not committed yet (a file only goes online after `git add` and commit; files ignored by git are an error).

`_src/verify.json`: `metadata_dir` (fastlane metadata folder, relative to the repo root or absolute; skipped with a warning if it does not exist),
`allow_default_badge` (language codes that may show the default badge because Apple has none), `max_asset_kb` (size limit for the warning).
`--verify --lang de` checks only that language's pages and leaves out the checks that concern all languages.

## Screenshots

The website uses four small webp screenshots per language, converted from the fastlane snapshot PNGs by `python3 _src/build.py`
(needs `cwebp`: `brew install webp`). The output goes to the language's own images folder (`images/` for the default language,
`<dir>/images/` for the others). `_src/screenshots.json` holds the settings:

- `source_dir`: the fastlane screenshots folder (relative to the website repo root, or absolute).
- `shots`: website image name -> file name in the fastlane locale folder. The file names are the same in every locale folder.
  Add or rename entries here when the pages use other screenshots.
- `width` and `quality`: size and webp quality of the output (the height follows the aspect ratio).
- `locales`: only needed where a language should use another fastlane locale folder than its `source_locale` in `config.json`
  (e.g. `"es": "es-MX"`).

Files that are already up to date are skipped (`--force` converts again). To copy the exact names into `shots`, list the PNG files of one
fastlane locale folder: `python3 _src/screenshots.py --list de-DE`.

## App Store badges

Apple's badge download is large (hundreds of MB) and stays **outside** the repository. Only the one SVG (about 10 KB) per
language that the website uses is committed, in the language's own images folder. `python3 _src/build.py` copies the badges named in
the content files (`badge_file`) from the download folder set in `_src/badges.json` (`source_dir`, relative to the website repo root or absolute).

To find the exact file name of a badge: `python3 _src/badges.py --list DE` lists the files in the download whose name contains "DE".
A language without its own badge uses the default language's badge from the root `images/` folder (keep its English `badge_alt`).
