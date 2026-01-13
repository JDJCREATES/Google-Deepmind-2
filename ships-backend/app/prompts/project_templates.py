"""
Project Templates for Planner Prompt Injection

Contains accurate conventions for all modern frameworks based on
official documentation and industry best practices.

Each template includes:
- stack: Primary tech stack recommendation
- alt_stacks: Alternative options
- scaffold_cmd: Command to initialize project
- structure: Recommended folder structure
- conventions: Naming and code style rules
- deps: Key dependencies to install
"""

# =============================================================================
# FRONTEND FRAMEWORKS
# =============================================================================

FRONTEND_TEMPLATES = {
    # React with Vite (default modern React 2025)
    "react-vite": {
        "stack": "Vite 6 + React 19 + TypeScript 5.x + TailwindCSS 4",
        "alt_stacks": ["Next.js 15", "Remix", "Astro"],
        "scaffold_cmd": "npx -y create-vite@latest . --template react-ts && npm install",
        "structure": """src/
├── components/
│   ├── ui/              # Reusable UI components (Button, Input, Card)
│   └── [feature]/       # Feature-specific components
├── hooks/               # Custom React hooks (useAuth, useFetch)
├── lib/                 # Utilities, helpers, constants
├── types/               # TypeScript interfaces
├── stores/              # Zustand stores (global state)
├── api/                 # API client functions
└── assets/              # Static assets (images, fonts)""",
        "conventions": """- Files: PascalCase for components (UserProfile.tsx), camelCase for hooks (useAuth.ts)
- Components: PascalCase export matches filename (UserProfile.tsx exports UserProfile)
- Hooks: camelCase with use prefix (useAuth.ts) - EXTRACT COMPLEX LOGIC HERE
- DRY Principle: ALWAYS map over arrays for repetitive elements.
- Styling: Tailwind utility classes. Use `clsx` or `tailwind-merge` for conditionals.
- State: Zustand v5 for global, useState for local. Avoid prop drilling.
- Async: TanStack Query v5 for data fetching. ALWAYS handle loading/error states.
- Memoization: Use React.memo, useMemo sparingly - profile first.
- TypeScript: strict mode, explicit types for props and return values.""",
        "deps": "npm install zustand @tanstack/react-query tailwindcss postcss autoprefixer clsx",
    },
    
    # Next.js 15 App Router (2025)
    "nextjs": {
        "stack": "Next.js 15 App Router + React 19 + TypeScript 5.x + TailwindCSS 4",
        "alt_stacks": ["Vite + React", "Remix", "Astro"],
        "scaffold_cmd": "npx -y create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias '@/*' --turbopack --yes",
        "structure": """src/
├── app/
│   ├── (routes)/        # Route groups (doesn't affect URL)
│   ├── api/             # API routes (route.ts)
│   ├── actions/         # Server Actions
│   ├── layout.tsx       # Root layout
│   └── page.tsx         # Home page
├── components/
│   ├── ui/              # Shadcn/UI components
│   └── [feature]/       # Feature components
├── lib/                 # Utilities, db client, cn() helper
├── types/               # TypeScript types
└── hooks/               # Custom hooks (client-side only)
public/                  # Static assets""",
        "conventions": """- Files: kebab-case for routes, PascalCase for components
- Pages: page.tsx (default export), Layouts: layout.tsx
- Server Components: Default (no 'use client'). Fetch data here.
- Client Components: 'use client' only for interactivity (forms, state, effects).
- Server Actions: Use for mutations (form submissions, data updates).
- Data Fetching: async/await in Server Components. Cache with revalidateTag().
- Styling: Tailwind CSS. Use cn() helper for class merging.
- Route Groups: Use (name) folders to organize without affecting URLs.""",
        "deps": "npm install zod next-safe-action @t3-oss/env-nextjs",
    },
    
    # Vue 3 Composition API (2025)
    "vue": {
        "stack": "Vue 3.5+ + Vite 6 + TypeScript 5.x + Pinia + TailwindCSS 4",
        "alt_stacks": ["Nuxt 3", "Quasar"],
        "scaffold_cmd": "npx -y create-vue@latest . --typescript --pinia --router --eslint --prettier",
        "structure": """src/
├── assets/              # Static assets, global CSS
├── components/
│   ├── base/            # Base components (BaseButton, BaseCard)
│   └── [feature]/       # Feature components
├── composables/         # Reusable logic (useAuth, useNotifications)
├── layouts/             # Layout wrappers
├── router/              # Vue Router config
├── stores/              # Pinia stores (useXxxStore)
├── types/               # TypeScript interfaces
├── views/               # Route-level page components
└── api/                 # API service layer""",
        "conventions": """- Files: kebab-case (user-profile.vue)
- Components: PascalCase, multi-word names required (UserProfile)
- Base Components: Prefix with Base or App (BaseButton)
- Composables: useXxx naming (useAuth), store in composables/
- Stores: Pinia with useXxxStore naming, Composition API style
- State Access: Use storeToRefs() for reactive destructuring
- Composition API: <script setup lang="ts"> ALWAYS
- Reactivity: ref() for primitives, reactive() for objects
- Actions: Keep mutations in store actions, not components""",
        "deps": "npm install pinia @vueuse/core tailwindcss postcss autoprefixer",
    },
    
    # Nuxt 3
    "nuxt": {
        "stack": "Nuxt 3 + TypeScript + Pinia + TailwindCSS",
        "alt_stacks": ["Vue 3 + Vite", "Astro"],
        "scaffold_cmd": "npx -y nuxi@latest init . && npm install",
        "structure": """
├── assets/              # Unprocessed assets
├── components/          # Auto-imported components
├── composables/         # Auto-imported composables
├── layouts/             # Nuxt layouts
├── middleware/          # Route middleware
├── pages/               # File-based routing
├── plugins/             # Nuxt plugins
├── public/              # Static files
├── server/
│   ├── api/             # API routes
│   └── middleware/      # Server middleware
├── stores/              # Pinia stores
└── types/               # TypeScript types""",
        "conventions": """- Files: kebab-case
- Components: Auto-imported, PascalCase usage
- Pages: File-based routing ([id].vue for dynamic)
- Composables: Auto-imported from composables/
- Server API: ~/server/api/[name].ts
- State: Pinia with useXxxStore
- Data: useFetch, useAsyncData (auto SSR)""",
        "deps": "npm install @pinia/nuxt @nuxtjs/tailwindcss",
    },
    
    # Angular 19 (Standalone Components + Signals)
    "angular": {
        "stack": "Angular 19 + TypeScript 5.x + TailwindCSS 4 + Signals",
        "alt_stacks": ["React", "Vue"],
        "scaffold_cmd": "npx -y @angular/cli@latest new . --standalone --style=scss --routing --skip-git",
        "structure": """src/app/
├── core/                # Singletons: services, guards, interceptors
│   ├── services/
│   ├── guards/
│   └── interceptors/
├── shared/              # Reusable: components, directives, pipes
│   ├── components/
│   ├── directives/
│   └── pipes/
├── features/            # Feature folders (standalone components)
│   └── [feature]/
│       ├── components/
│       ├── pages/
│       └── services/
├── layouts/             # Layout components
└── models/              # TypeScript interfaces""",
        "conventions": """- Files: kebab-case with type suffix (user.service.ts, user-list.component.ts)
- Classes: PascalCase (UserService, UserListComponent)
- Standalone: All components standalone by default (Angular 19)
- Signals: Use signal() for state, computed() for derived, effect() for side effects
- DI: Use inject() function instead of constructor injection
- Services: Singleton in root (providedIn: 'root')
- Change Detection: OnPush by default, signals auto-update
- RxJS: Use async pipe or toSignal() for observables
- Lazy Loading: loadComponent() for routes""",
        "deps": "npm install @angular/cdk tailwindcss",
    },
    
    # Svelte 5 / SvelteKit 2 (Runes)
    "svelte": {
        "stack": "SvelteKit 2 + Svelte 5 + TypeScript 5.x + TailwindCSS 4",
        "alt_stacks": ["Astro", "Vite + Svelte"],
        "scaffold_cmd": "npx -y sv create . && npm install",
        "structure": """src/
├── lib/
│   ├── components/      # Reusable components
│   ├── stores/          # Shared state (using runes)
│   └── utils/           # Utilities ($lib alias)
├── routes/              # File-based routing
│   ├── +page.svelte     # Page component
│   ├── +page.ts         # Universal load function
│   ├── +page.server.ts  # Server-only load
│   ├── +layout.svelte   # Layout
│   └── api/             # API endpoints (+server.ts)
├── params/              # Param matchers
└── app.d.ts             # Type declarations
static/                  # Static assets""",
        "conventions": """- Files: kebab-case (+page.svelte, user-profile.svelte)
- Components: PascalCase import and usage
- Svelte 5 Runes: $state for reactive state, $derived for computed
- Side Effects: $effect() for reactions to state changes
- Props: let { value } = $props() (new syntax)
- Two-way Binding: $bindable() for bindable props
- Load Functions: +page.ts (universal), +page.server.ts (server-only)
- API Routes: +server.ts with GET/POST/PUT/DELETE exports
- TypeScript: Native support, no preprocessor needed""",
        "deps": "npm install @sveltejs/adapter-auto tailwindcss",
    },
    
    # Astro 5 (Content Layer API)
    "astro": {
        "stack": "Astro 5 + TypeScript + TailwindCSS 4 + React/Vue/Svelte islands",
        "alt_stacks": ["Next.js", "Nuxt", "SvelteKit"],
        "scaffold_cmd": "npx -y create-astro@latest . --template minimal --typescript strict",
        "structure": """src/
├── components/          # .astro and framework components (islands)
├── content/             # Content collections (MDX, Markdown, JSON)
├── content.config.ts    # Content Layer config with Zod schemas
├── layouts/             # Layout components
├── pages/               # File-based routing (.astro, .md)
├── styles/              # Global styles
└── utils/               # Utilities
public/                  # Static assets""",
        "conventions": """- Files: kebab-case for pages, PascalCase for components
- Components: .astro (static), .tsx/.vue/.svelte (islands)
- Hydration: client:load, client:idle, client:visible directives
- Content Layer: Use glob/file loaders, Zod schemas for validation
- Collections: Define in src/content.config.ts, query with getCollection()
- Routing: src/pages/ file-based, dynamic routes with [param].astro
- Zero JS: Ship zero JS by default, add islands only for interactivity
- SEO: Use <svelte:head> or Astro.props for meta tags""",
        "deps": "npm install @astrojs/tailwind @astrojs/react astro-seo",
    },
    
    # Solid.js
    "solid": {
        "stack": "SolidJS + Vite + TypeScript + TailwindCSS",
        "alt_stacks": ["React", "Svelte"],
        "scaffold_cmd": "npx -y degit solidjs/templates/ts . && npm install",
        "structure": """src/
├── components/          # Reusable components
├── hooks/               # Custom primitives
├── lib/                 # Utilities
├── pages/               # Route pages
├── stores/              # createStore, context
└── types/               # TypeScript types""",
        "conventions": """- Components: PascalCase, function components
- Signals: createSignal() for reactive state
- Stores: createStore() for nested objects
- Effects: createEffect() for side effects
- No VDOM: Direct DOM updates
- Props: Destructure carefully (breaks reactivity)""",
        "deps": "npm install solid-js tailwindcss",
    },
}

# =============================================================================
# BACKEND FRAMEWORKS
# =============================================================================

BACKEND_TEMPLATES = {
    # FastAPI (Python 2025)
    "fastapi": {
        "stack": "Python 3.12+ + FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic",
        "alt_stacks": ["Django", "Litestar", "Flask"],
        "scaffold_cmd": "pip install fastapi uvicorn sqlalchemy pydantic pydantic-settings alembic python-dotenv",
        "structure": """app/
├── api/
│   ├── v1/              # API version
│   │   ├── routes/      # Route handlers (user.py, auth.py)
│   │   └── deps.py      # Shared dependencies
├── core/
│   ├── config.py        # Settings (pydantic-settings BaseSettings)
│   ├── security.py      # Auth, JWT, password hashing
│   └── database.py      # Async DB session, engine
├── models/              # SQLAlchemy 2.x models (Mapped, mapped_column)
├── schemas/             # Pydantic v2 schemas (model_validator, field_validator)
├── services/            # Business logic layer (keep routes thin)
├── repositories/        # Data access layer (optional, for complex queries)
└── utils/               # Helpers
alembic/                 # Migrations
pyproject.toml           # Modern dependency management
main.py                  # FastAPI app entry""",
        "conventions": """- Files: snake_case (user_service.py)
- Classes: PascalCase (UserService, UserCreate)
- Functions: snake_case, async def for all endpoints
- Pydantic v2: Use model_validator, field_validator, ConfigDict
- Schemas: Create/Update/Response suffixes (UserCreate, UserResponse)
- Dependencies: Annotated[T, Depends()] for type-safe injection
- Services: Keep routes thin, business logic in services/
- Async: Use async/await consistently, avoid blocking I/O
- Validation: Pydantic for all I/O, never trust raw input""",
        "deps": "pip install fastapi uvicorn[standard] sqlalchemy[asyncio] alembic pydantic-settings python-jose[cryptography] passlib[bcrypt]",
    },
    
    # Django + DRF
    "django": {
        "stack": "Django 5+ + Django REST Framework + PostgreSQL",
        "alt_stacks": ["FastAPI", "Flask"],
        "scaffold_cmd": "pip install django djangorestframework && django-admin startproject core .",
        "structure": """core/                    # Django project
├── settings/
│   ├── base.py
│   ├── development.py
│   └── production.py
├── urls.py
└── wsgi.py
apps/                    # Django apps
├── [app_name]/
│   ├── models.py
│   ├── views.py
│   ├── serializers.py
│   ├── urls.py
│   ├── admin.py
│   └── tests/
├── users/
└── common/              # Shared utilities
templates/               # HTML templates
static/                  # Static files""",
        "conventions": """- Apps: snake_case, short names (users, orders)
- Models: PascalCase, singular (User, Order)
- Views: PascalCase suffix (UserViewSet, UserListView)
- Serializers: PascalCase suffix (UserSerializer)
- URLs: snake_case patterns
- Settings: Split by environment
- Migrations: Auto-generated, never edit manually
- Managers: Custom model managers for complex queries""",
        "deps": "pip install django djangorestframework django-cors-headers django-filter psycopg2-binary drf-spectacular",
    },
    
    # Flask
    "flask": {
        "stack": "Flask + Flask-SQLAlchemy + Marshmallow + Flask-Migrate",
        "alt_stacks": ["FastAPI", "Django"],
        "scaffold_cmd": "pip install flask flask-sqlalchemy flask-marshmallow flask-migrate python-dotenv",
        "structure": """app/
├── __init__.py          # App factory
├── models/              # SQLAlchemy models
├── routes/              # Blueprint routes
│   └── [feature].py
├── schemas/             # Marshmallow schemas
├── services/            # Business logic
└── utils/               # Helpers
config.py                # Configuration
run.py                   # Entry point
migrations/              # Flask-Migrate""",
        "conventions": """- Files: snake_case
- Classes: PascalCase
- Blueprints: One per feature area
- App Factory: create_app() pattern
- Config: Class-based (Config, DevelopmentConfig)
- Extensions: Initialize in create_app()
- Schemas: Marshmallow for serialization""",
        "deps": "pip install flask flask-sqlalchemy flask-marshmallow flask-migrate flask-cors python-dotenv",
    },
    
    # Express.js (Node)
    "express": {
        "stack": "Express.js + TypeScript + Prisma + Zod",
        "alt_stacks": ["NestJS", "Fastify", "Hono"],
        "scaffold_cmd": "npm init -y && npm install express typescript ts-node @types/express @types/node prisma zod",
        "structure": """src/
├── controllers/         # Route handlers
├── middleware/          # Express middleware
├── models/              # Type definitions
├── routes/              # Route definitions
├── services/            # Business logic
├── utils/               # Helpers
├── config/              # Configuration
├── app.ts               # Express app setup
└── server.ts            # Entry point
prisma/
└── schema.prisma        # Database schema""",
        "conventions": """- Files: kebab-case (user-controller.ts)
- Classes/Types: PascalCase
- Functions: camelCase
- Middleware: Named functions
- Routes: RESTful, plural nouns (/users, /users/:id)
- Error Handling: Centralized error middleware
- Validation: Zod schemas
- Async: async/await with try-catch""",
        "deps": "npm install express cors helmet dotenv zod prisma @prisma/client",
    },
    
    # NestJS
    "nestjs": {
        "stack": "NestJS + TypeScript + Prisma + class-validator",
        "alt_stacks": ["Express", "Fastify", "Hono"],
        "scaffold_cmd": "npx -y @nestjs/cli@latest new . --skip-git --package-manager npm",
        "structure": """src/
├── common/              # Shared: guards, pipes, filters, decorators
│   ├── guards/
│   ├── pipes/
│   ├── filters/
│   └── decorators/
├── config/              # Configuration
├── modules/
│   └── [feature]/       # Feature modules
│       ├── [feature].module.ts
│       ├── [feature].controller.ts
│       ├── [feature].service.ts
│       ├── dto/
│       │   ├── create-[feature].dto.ts
│       │   └── update-[feature].dto.ts
│       └── entities/
│           └── [feature].entity.ts
├── app.module.ts        # Root module
└── main.ts              # Entry point
prisma/
└── schema.prisma""",
        "conventions": """- Folders: kebab-case (user-module)
- Files: kebab-case with type suffix (user.controller.ts, create-user.dto.ts)
- Classes: PascalCase (UserService, CreateUserDto)
- Modules: Feature-based encapsulation
- Controllers: Thin, delegate to services
- Services: Business logic, @Injectable()
- DTOs: class-validator decorators
- Entities: Database models
- Dependency Injection: Constructor injection""",
        "deps": "npm install @nestjs/config @prisma/client class-validator class-transformer",
    },
    
    # Go Gin
    "go-gin": {
        "stack": "Go + Gin + GORM + Wire (DI)",
        "alt_stacks": ["Go Fiber", "Go Chi", "Go Echo"],
        "scaffold_cmd": "go mod init app && go get github.com/gin-gonic/gin gorm.io/gorm",
        "structure": """cmd/
└── server/
    └── main.go          # Entry point
internal/
├── handler/             # HTTP handlers
├── service/             # Business logic
├── repository/          # Data access
├── model/               # Domain models
├── middleware/          # HTTP middleware
├── config/              # Configuration
└── pkg/                 # Shared utilities
api/
└── v1/                  # OpenAPI spec""",
        "conventions": """- Packages: Short, lowercase, no underscores
- Files: snake_case (user_handler.go)
- Exported: PascalCase (GetUser)
- Unexported: camelCase (getUser)
- Interfaces: Define where used, not implemented
- Errors: Return error as last value
- Context: Pass context.Context first
- DI: Wire or manual injection""",
        "deps": "go get github.com/gin-gonic/gin gorm.io/gorm gorm.io/driver/postgres",
    },
    
    # Rust Actix-web
    "rust-actix": {
        "stack": "Rust + Actix-web + SQLx + Tokio",
        "alt_stacks": ["Axum", "Rocket"],
        "scaffold_cmd": "cargo new . && cargo add actix-web sqlx tokio serde",
        "structure": """src/
├── main.rs              # Entry point
├── config.rs            # Configuration
├── routes/              # Route handlers
│   ├── mod.rs
│   └── [feature].rs
├── models/              # Database models
├── services/            # Business logic
├── db/                  # Database connection
└── error.rs             # Error handling
migrations/              # SQLx migrations""",
        "conventions": """- Files: snake_case
- Modules: snake_case (mod user)
- Types: PascalCase (User, UserService)
- Functions: snake_case
- Constants: SCREAMING_SNAKE_CASE
- Errors: Custom error types with thiserror
- Async: Tokio runtime, async/await
- Serialization: Serde derive macros""",
        "deps": "cargo add actix-web actix-rt sqlx tokio serde serde_json thiserror dotenv",
    },
}

# =============================================================================
# CLI FRAMEWORKS
# =============================================================================

CLI_TEMPLATES = {
    # Python Click
    "python-cli": {
        "stack": "Python + Click + Rich + Typer",
        "alt_stacks": ["Rust Clap", "Go Cobra"],
        "scaffold_cmd": "pip install click rich typer",
        "structure": """src/
├── cli.py               # Main CLI entry
├── commands/            # Subcommands
│   ├── __init__.py
│   └── [command].py
├── utils/               # Helpers
└── config.py            # Configuration
pyproject.toml           # Project config with entry point""",
        "conventions": """- Files: snake_case
- Commands: snake_case (my_command)
- Groups: Click groups for subcommands
- Options: --kebab-case flags
- Output: Rich for styled output
- Entry Point: [tool.poetry.scripts] or [project.scripts]""",
        "deps": "pip install click rich typer",
    },
    
    # Rust Clap
    "rust-cli": {
        "stack": "Rust + Clap + color-eyre + indicatif",
        "alt_stacks": ["Go Cobra", "Python Click"],
        "scaffold_cmd": "cargo new . && cargo add clap --features derive && cargo add color-eyre",
        "structure": """src/
├── main.rs              # Entry point
├── cli.rs               # Clap derive structs
├── commands/
│   ├── mod.rs
│   └── [command].rs
└── utils.rs             # Helpers
Cargo.toml""",
        "conventions": """- Derive macro: #[derive(Parser)] for CLI
- Subcommands: #[derive(Subcommand)] enum
- Args: #[arg(short, long)]
- Errors: color-eyre for nice errors
- Progress: indicatif for progress bars""",
        "deps": "cargo add clap --features derive && cargo add color-eyre indicatif",
    },
    
    # Go Cobra
    "go-cli": {
        "stack": "Go + Cobra + Viper + Charm",
        "alt_stacks": ["Rust Clap", "Python Click"],
        "scaffold_cmd": "go mod init app && go get github.com/spf13/cobra github.com/spf13/viper",
        "structure": """cmd/
├── root.go              # Root command
└── [command].go         # Subcommands
internal/
├── config/
└── utils/
main.go                  # Entry point""",
        "conventions": """- Commands: Cobra command structs
- Config: Viper for config files
- Flags: PersistentFlags for global
- Output: Charm for styled TUI""",
        "deps": "go get github.com/spf13/cobra github.com/spf13/viper github.com/charmbracelet/lipgloss",
    },
}

# =============================================================================
# DESKTOP / MOBILE
# =============================================================================

DESKTOP_MOBILE_TEMPLATES = {
    # Electron
    "electron": {
        "stack": "Electron + React + TypeScript + electron-vite",
        "alt_stacks": ["Tauri", "Neutralino"],
        "scaffold_cmd": "npx -y create-electron-vite@latest . --template react-ts",
        "structure": """src/
├── main/                # Main process
│   └── index.ts
├── preload/             # Preload scripts
│   └── index.ts
├── renderer/            # React UI
│   ├── components/
│   ├── hooks/
│   ├── stores/
│   └── App.tsx
└── shared/              # Shared types
electron.vite.config.ts""",
        "conventions": """- Processes: Main (Node), Preload (bridge), Renderer (Chrome)
- IPC: contextBridge.exposeInMainWorld()
- Security: contextIsolation: true, nodeIntegration: false
- Windows: BrowserWindow management in main
- State: Zustand in renderer""",
        "deps": "npm install electron-vite zustand",
    },
    
    # Tauri
    "tauri": {
        "stack": "Tauri 2.0 + React + TypeScript + Rust backend",
        "alt_stacks": ["Electron", "Wails"],
        "scaffold_cmd": "npx -y create-tauri-app@latest . --template react-ts",
        "structure": """src/                     # React frontend
├── components/
├── hooks/
├── lib/
└── App.tsx
src-tauri/               # Rust backend
├── src/
│   ├── main.rs
│   ├── lib.rs
│   └── commands.rs      # IPC commands
├── Cargo.toml
├── tauri.conf.json
└── capabilities/        # Permissions""",
        "conventions": """- Frontend: Standard React conventions
- Commands: #[tauri::command] macro
- IPC: invoke('command_name', payload)
- Permissions: Capability-based security
- State: Managed state with tauri::State""",
        "deps": "npm install @tauri-apps/api && cd src-tauri && cargo build",
    },
    
    # React Native / Expo
    "expo": {
        "stack": "Expo SDK 50+ + React Native + TypeScript + Expo Router",
        "alt_stacks": ["React Native CLI", "Flutter"],
        "scaffold_cmd": "npx -y create-expo-app@latest . --template blank-typescript",
        "structure": """app/                     # Expo Router
├── (tabs)/              # Tab navigation
│   ├── _layout.tsx
│   ├── index.tsx
│   └── profile.tsx
├── (auth)/              # Auth flow
├── _layout.tsx          # Root layout
└── +not-found.tsx       # 404
src/
├── components/
├── hooks/
├── lib/
├── stores/
└── types/""",
        "conventions": """- Navigation: File-based with Expo Router
- Layouts: _layout.tsx for shared UI
- Groups: (groupName) folder syntax
- Styling: StyleSheet.create or NativeWind
- Storage: AsyncStorage for persistence
- State: Zustand with persist middleware""",
        "deps": "npx expo install expo-router zustand @react-native-async-storage/async-storage",
    },
    
    # Flutter
    "flutter": {
        "stack": "Flutter + Dart + Riverpod + GoRouter",
        "alt_stacks": ["React Native", "Expo"],
        "scaffold_cmd": "flutter create . --org com.example",
        "structure": """lib/
├── main.dart            # Entry point
├── app/
│   ├── router.dart      # GoRouter config
│   └── theme.dart       # ThemeData
├── features/
│   └── [feature]/
│       ├── data/        # Repositories, data sources
│       ├── domain/      # Entities, use cases
│       └── presentation/ # Widgets, providers
├── shared/
│   ├── widgets/         # Reusable widgets
│   └── utils/           # Helpers
└── providers/           # Riverpod providers""",
        "conventions": """- Files: snake_case (user_profile.dart)
- Classes: PascalCase (UserProfile)
- Variables: camelCase
- Constants: lowerCamelCase or SCREAMING_SNAKE
- Widgets: Stateless by default
- State: Riverpod providers
- Architecture: Feature-first with clean arch layers""",
        "deps": "flutter pub add flutter_riverpod go_router freezed_annotation json_annotation",
    },
}

# =============================================================================
# COMBINED TEMPLATES
# =============================================================================

PROJECT_TEMPLATES = {
    **FRONTEND_TEMPLATES,
    **BACKEND_TEMPLATES,
    **CLI_TEMPLATES,
    **DESKTOP_MOBILE_TEMPLATES,
    
    # Aliases for common requests
    "web_app": FRONTEND_TEMPLATES["react-vite"],
    "api": BACKEND_TEMPLATES["fastapi"],
    "cli": CLI_TEMPLATES["python-cli"],
    "desktop": DESKTOP_MOBILE_TEMPLATES["electron"],
    "mobile": DESKTOP_MOBILE_TEMPLATES["expo"],
    
    # Generic fallback
    "generic": {
        "stack": "Determine based on user requirements and intent",
        "alt_stacks": ["Analyze context for best fit"],
        "scaffold_cmd": "# Determined based on detected tech stack",
        "structure": """# Structure determined by project type
# Common patterns:
# - src/ or app/ for source code
# - lib/ or utils/ for utilities
# - tests/ for test files
# - docs/ for documentation""",
        "conventions": """# Determine conventions by primary language:
# JavaScript/TypeScript: camelCase vars, PascalCase components, kebab-case files
# Python: snake_case functions/vars, PascalCase classes
# Rust: snake_case functions, PascalCase types
# Go: camelCase unexported, PascalCase exported""",
        "deps": "# Dependencies determined by tech stack",
    },
}

# Default template
DEFAULT_TEMPLATE = PROJECT_TEMPLATES["generic"]


def get_template(project_type: str) -> dict:
    """Get template for project type, with fallback to generic."""
    return PROJECT_TEMPLATES.get(project_type.lower(), DEFAULT_TEMPLATE)


def list_available_templates() -> list:
    """List all available template names."""
    return sorted(PROJECT_TEMPLATES.keys())
