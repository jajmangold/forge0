# Gitea Customization Guide

Everything you need to know about customizing Gitea: config files, environment variables, templates, themes, database settings, and more.

## Table of Contents

- [Key Paths](#key-paths)
- [app.ini - The Main Config File](#appini---the-main-config-file)
- [Environment Variables](#environment-variables)
- [Admin UI / Database Settings](#admin-ui--database-settings)
- [Custom Templates](#custom-templates)
- [Themes & CSS](#themes--css)
- [Custom Public Files](#custom-public-files)
- [Logo & Favicon](#logo--favicon)
- [Custom Gitignores, Labels, Licenses, Locales, Readmes](#custom-gitignores-labels-licenses-locales-readmes)
- [Mail Templates](#mail-templates)
- [Git Configuration](#git-configuration)
- [Useful app.ini Sections](#useful-appini-sections)

---

## Key Paths

Gitea uses a few important paths (check with `gitea help`):

| Variable | Default | Purpose |
|---|---|---|
| `AppWorkPath` | Directory of the gitea binary | Working directory |
| `CustomPath` | `{AppWorkPath}/custom` | Root for all custom overrides |
| `CustomConf` | `{CustomPath}/conf/app.ini` | Main config file |
| `StaticRootPath` | `{AppWorkPath}` | Templates & static files base |

Override with:
- `GITEA_CUSTOM` env var (sets `CustomPath`)
- `--custom-path` flag
- `--config` flag (sets `CustomConf`)
- `GITEA_WORK_DIR` env var (sets `AppWorkPath`)

---

## app.ini - The Main Config File

Location: `$GITEA_CUSTOM/conf/app.ini` (or `/etc/gitea/conf/app.ini` for distro installs).

INI format with `[section]` headers. Changes require a **full restart**.

### Quick Reference of Important Sections

```ini
[DEFAULT]
APP_NAME = Gitea: Git with a cup of tea    ; Page title
RUN_USER = git                              ; OS user Gitea runs as
RUN_MODE = prod                             ; dev or prod

[server]
DOMAIN = localhost
ROOT_URL = %(PROTOCOL)s://%(DOMAIN)s:%(HTTP_PORT)s/
HTTP_PORT = 3000
PROTOCOL = http                             ; http, https, fcgi, http+unix
SSH_DOMAIN = %(DOMAIN)s
DISABLE_SSH = false
START_SSH_SERVER = false
LFS_START_SERVER = false
OFFLINE_MODE = true
LANDING_PAGE = home                         ; home, explore, organizations, login, or custom URL

[database]
DB_TYPE = sqlite3                           ; mysql, postgres, mssql, sqlite3
HOST = 127.0.0.1:3306
NAME = gitea
USER = root
PASSWD =
PATH = data/gitea.db                        ; SQLite3 only
SSL_MODE = disable                          ; TLS mode for postgres/mysql

[repository]
ROOT = %(APP_DATA_PATH)s/gitea-repositories
DEFAULT_BRANCH = main
FORCE_PRIVATE = false
MAX_CREATION_LIMIT = -1                     ; -1 = unlimited

[service]
DISABLE_REGISTRATION = false
REQUIRE_SIGNIN_VIEW = false
DEFAULT_ENABLE_TIMETRACKING = true

[mailer]
ENABLED = false
SMTP_ADDR =
SMTP_PORT =
FROM =

[i18n]
LANGS = en-US
NAMES = English
```

### Tips

- Values with `#` or `;` must be quoted with backticks or double quotes
- Use `%(variable)s` syntax to reference other values within the same file
- Run `gitea help` to see all current defaults
- Full example: `app.example.ini` in the Gitea source repo

---

## Environment Variables

Set before starting Gitea. Format: `GITEA__<section>__<key>` (double underscores for section/key separators).

### Overriding app.ini Values

```bash
# Database config via env vars
GITEA__database__DB_TYPE=postgres
GITEA__database__HOST=127.0.0.1:5432
GITEA__database__NAME=gitea
GITEA__database__USER=gitea
GITEA__database__PASSWD=secret

# Server config
GITEA__server__DOMAIN=gitea.example.com
GITEA__server__ROOT_URL=https://gitea.example.com
```

### Loading Secrets from Files

Append `__FILE` to load the value from a file (great for Docker secrets):

```bash
GITEA__database__PASSWD__FILE=/run/secrets/db_password
```

### Key Environment Variables

| Variable | Purpose |
|---|---|
| `GITEA_WORK_DIR` | Override the working directory |
| `GITEA_CUSTOM` | Override the custom directory path |
| `USER` / `USERNAME` | System user Gitea runs as |
| `HOME` | User home directory |

### Go Runtime Variables

| Variable | Purpose |
|---|---|
| `GOMEMLIMIT` | Go memory limit |
| `GOGC` | GC tuning |
| `GOMAXPROCS` | Max OS threads for Go |

### Docker Note

The official Docker images automatically run `gitea config edit-ini --in-place --apply-env` on startup to write env vars into `app.ini`.

---

## Admin UI / Database Settings

Some settings are stored in the database and managed via the **Site Administration** web UI (not `app.ini`):

- Navigate to `{ROOT_URL}/admin` when logged in as an admin
- These are often things like:
  - **Application settings** (site name, description, etc.)
  - **User settings** (default user visibility, etc.)
  - **Repository settings** (global repo defaults)
  - **Service settings** (registration, email, etc.)

Database-stored settings take precedence over `app.ini` for overlapping keys. If you change something in the Admin UI and it doesn't seem to take effect, check if it's also set in `app.ini`.

---

## Custom Templates

All pages use Go templates. Override any template by placing a copy in `$GITEA_CUSTOM/templates/` matching the source path.

### Finding Templates

```bash
# Extract embedded templates
gitea embedded extract templates

# Or browse the source:
# https://github.com/go-gitea/gitea/tree/main/templates
```

### Special Template Hooks

Place these in `$GITEA_CUSTOM/templates/custom/`:

| File | Injects into |
|---|---|
| `header.tmpl` | End of `<head>` (add custom CSS) |
| `body_outer_pre.tmpl` | After `<body>` start |
| `body_inner_pre.tmpl` | Before navbar, inside main container |
| `body_inner_post.tmpl` | Before end of main container |
| `body_outer_post.tmpl` | Before `<footer>` |
| `footer.tmpl` | End of `<body>` (add custom JS) |
| `extra_links.tmpl` | Top navbar links |
| `extra_links_footer.tmpl` | Footer links |
| `extra_tabs.tmpl` | Repository view tabs |

### Example: Adding Custom CSS

Create `$GITEA_CUSTOM/templates/custom/header.tmpl`:

```html
<link rel="stylesheet" href="{{AppSubUrl}}/assets/css/my-style.css" />
```

### Example: Adding Custom JS

Create `$GITEA_CUSTOM/templates/custom/footer.tmpl`:

```html
<script src="{{AppSubUrl}}/assets/js/my-script.js"></script>
```

### Debugging Templates

Temporarily set `RUN_MODE = dev` in `app.ini` to see template errors. Add `{{ $ | DumpVar }}` to dump available variables on a page.

---

## Themes & CSS

Built-in themes: `gitea-light`, `gitea-dark`, `gitea-auto`.

### Creating a Custom Theme

1. Create `$GITEA_CUSTOM/public/assets/css/theme-my-theme.css`:

```css
gitea-theme-meta-info {
  --theme-display-name: "My Theme";
}

:root {
  --is-dark-theme: true;  /* set for dark themes */
  --color-primary: #ff6600;
  /* override any CSS variables */
}
```

2. Register it in `app.ini`:

```ini
[ui]
DEFAULT_THEME = my-theme           ; set as default
THEMES = gitea-auto,gitea-light,gitea-dark,my-theme  ; available choices
```

If `THEMES` is empty, all themes (including custom ones) are available.

### Custom Fonts

Override via CSS variables in your theme:

```css
:root {
  --fonts-proportional: "Inter", sans-serif !important;
  --fonts-monospace: "JetBrains Mono", monospace !important;
  --fonts-emoji: "Noto Color Emoji", sans-serif !important;
}
```

---

## Custom Public Files

Serve static files from `$GITEA_CUSTOM/public/`:

| Path | URL |
|---|---|
| `public/robots.txt` | `/robots.txt` |
| `public/.well-known/*` | `/.well-known/*` |
| `public/assets/*` | `/assets/*` |

Example: `$GITEA_CUSTOM/public/assets/img/logo.png` is accessible at `/assets/img/logo.png`.

---

## Logo & Favicon

Replace these files in `$GITEA_CUSTOM/public/assets/img/`:

| File | Purpose |
|---|---|
| `logo.svg` | Site icon, app icon |
| `logo.png` | Open Graph image |
| `avatar_default.png` | Default avatar |
| `apple-touch-icon.png` | iOS bookmark icon |
| `favicon.svg` | Favicon (SVG) |
| `favicon.png` | Favicon fallback |

To generate all sizes from a single source: clone the Gitea repo, replace `assets/logo.svg`, run `make generate-images`.

---

## Custom Gitignores, Labels, Licenses, Locales, Readmes

All go under `$GITEA_CUSTOM/options/`:

### Gitignores

Add files to `$GITEA_CUSTOM/options/gitignore/` (no extension, e.g. `MyProject`).

### Labels (YAML format, Gitea 1.19+)

Add to `$GITEA_CUSTOM/options/label/`:

```yaml
labels:
  - name: "bug"
    color: "d73a4a"
    description: "Something isn't working"
  - name: "priority:high"
    exclusive: true
    color: "b60205"
    description: "High priority"
```

### Licenses

Add license text to `$GITEA_CUSTOM/options/license/` (no extension).

### Locales

Override translations in `$GITEA_CUSTOM/options/locale/`. Add new locales by also updating `app.ini`:

```ini
[i18n]
LANGS = en-US,de-DE,fr-FR
NAMES = English,Deutsch,Français
```

### Readmes

Add markdown templates (no `.md` extension) to `$GITEA_CUSTOM/options/readme/`. Supports variables: `{Name}`, `{Description}`, `{CloneURL.SSH}`, `{CloneURL.HTTPS}`, `{OwnerName}`.

---

## Mail Templates

Override email templates by placing files in `$GITEA_CUSTOM/templates/mail/` matching the source structure. Find defaults in the Gitea source `templates/mail/` directory.

---

## Git Configuration

Customize git behavior via `app.ini` (Gitea 1.20+):

```ini
[git.config]
; Enable signed pushes
receive.certNonceSeed = <random-secret-string>
receive.advertisePushOptions = true

; Custom git config entries
protocol.version = 2
```

Note: Gitea does not read `/etc/gitconfig` — set everything via `app.ini`.

---

## Useful app.ini Sections

### UI Customization

```ini
[ui]
EXPLORE_PAGING_NUM = 20
ISSUE_PAGING_NUM = 20
DEFAULT_THEME = gitea-auto
SHOW_USER_EMAIL = true
DEFAULT_SHOW_FULL_NAME = false
REACTIONS = +1,-1,laugh,confused,heart,hooray,eyes
CUSTOM_EMOJIS = gitea,codeberg,gitlab,git,github,gogs
```

### Pull Requests

```ini
[repository.pull-request]
DEFAULT_MERGE_STYLE = merge          ; merge, rebase, squash, fast-forward-only
DEFAULT_DELETE_BRANCH_AFTER_MERGE = false
WORK_IN_PROGRESS_PREFIXES = WIP:,[WIP]
CLOSE_KEYWORDS = close,closes,closed,fix,fixes,fixed,resolve,resolves,resolved
```

### CORS

```ini
[cors]
ENABLED = false
ALLOW_DOMAIN = *
METHODS = GET,HEAD,POST,PUT,PATCH,DELETE,OPTIONS
```

### Markdown

```ini
[markdown]
ENABLE_MATH = true
CUSTOM_URL_SCHEMES = ftp,git,svn
```

### Upload Limits

```ini
[repository.upload]
FILE_MAX_SIZE = 50          ; MB per file
MAX_FILES = 5
ALLOWED_TYPES =             ; empty = allow all

[attachment]
FILE_MAX_SIZE = 2048        ; MB for release attachments
```

### Logging

```ini
[log]
MODE = console,file
LEVEL = Info
ROOT_PATH = /var/log/gitea
```

---

## Quick Reference: Where to Put What

| Want to... | Where |
|---|---|
| Change a setting | `app.ini` or Admin UI |
| Override a template | `$GITEA_CUSTOM/templates/` |
| Add custom CSS/JS | `$GITEA_CUSTOM/public/assets/` |
| Add a custom theme | `$GITEA_CUSTOM/public/assets/css/theme-*.css` |
| Change the logo | `$GITEA_CUSTOM/public/assets/img/` |
| Add gitignore templates | `$GITEA_CUSTOM/options/gitignore/` |
| Add issue labels | `$GITEA_CUSTOM/options/label/` |
| Override translations | `$GITEA_CUSTOM/options/locale/` |
| Add license templates | `$GITEA_CUSTOM/options/license/` |
| Customize emails | `$GITEA_CUSTOM/templates/mail/` |
| Add navbar/footer links | `$GITEA_CUSTOM/templates/custom/extra_links*.tmpl` |
| Inject JS/CSS globally | `$GITEA_CUSTOM/templates/custom/header.tmpl` or `footer.tmpl` |
| Serve static files | `$GITEA_CUSTOM/public/assets/` |

---

*Based on Gitea 1.27 documentation. See [docs.gitea.com](https://docs.gitea.com) for the latest.*
