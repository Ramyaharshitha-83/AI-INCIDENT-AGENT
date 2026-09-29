from app.services.repository import (
    get_repository_tree,
    get_repository_file,
)


# ============================================================
# LIMITS
# ============================================================

MAX_FILES_TO_ANALYZE = 8
MAX_FILE_CONTENT_LENGTH = 8_000


# ============================================================
# FILE TYPES
# ============================================================

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".cs",
    ".cpp",
    ".c",
    ".h",
}

CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".conf",
    ".xml",
    ".properties",
}

INFRASTRUCTURE_NAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "procfile",
    "nginx.conf",
    "vercel.json",
    "netlify.toml",
    "render.yaml",
    "fly.toml",
}

IMPORTANT_FILES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "cargo.toml",
}


# ============================================================
# HELPERS
# ============================================================

def get_extension(path: str):
    filename = path.lower().split("/")[-1]

    if "." not in filename:
        return ""

    return "." + filename.rsplit(".", 1)[1]


def normalize_path(path: str):
    return path.lower().replace("\\", "/")


# ============================================================
# ARCHITECTURE DETECTION
# ============================================================

def detect_architecture(files):

    frontend = False
    backend = False
    database = False
    api = False
    deployment = False

    frameworks = set()
    languages = set()

    paths = [
        normalize_path(file["path"])
        for file in files
    ]

    for path in paths:

        filename = path.split("/")[-1]
        extension = get_extension(path)

        # ----------------------------------------------------
        # Languages
        # ----------------------------------------------------

        if extension == ".py":
            languages.add("Python")
            backend = True

        elif extension in {".js", ".jsx"}:
            languages.add("JavaScript")

        elif extension in {".ts", ".tsx"}:
            languages.add("TypeScript")

        elif extension == ".java":
            languages.add("Java")
            backend = True

        elif extension == ".kt":
            languages.add("Kotlin")
            backend = True

        elif extension == ".go":
            languages.add("Go")
            backend = True

        elif extension == ".rs":
            languages.add("Rust")
            backend = True

        elif extension == ".php":
            languages.add("PHP")
            backend = True

        elif extension == ".rb":
            languages.add("Ruby")
            backend = True

        elif extension == ".cs":
            languages.add("C#")
            backend = True

        # ----------------------------------------------------
        # Frontend indicators
        # ----------------------------------------------------

        if extension in {".jsx", ".tsx"}:
            frontend = True

        if any(
            marker in path
            for marker in [
                "/components/",
                "/pages/",
                "/frontend/",
                "/client/",
                "/src/",
            ]
        ):
            if extension in {
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
            }:
                frontend = True

        # ----------------------------------------------------
        # Backend / API indicators
        # ----------------------------------------------------

        if any(
            marker in path
            for marker in [
                "/api/",
                "/routes/",
                "/controllers/",
                "/services/",
                "/backend/",
                "/server/",
            ]
        ):
            backend = True
            api = True

        # ----------------------------------------------------
        # Database indicators
        # ----------------------------------------------------

        if any(
            keyword in path
            for keyword in [
                "database",
                "db/",
                "models/",
                "migration",
                "migrations/",
                "schema",
            ]
        ):
            database = True

        # ----------------------------------------------------
        # Deployment indicators
        # ----------------------------------------------------

        if (
            filename in INFRASTRUCTURE_NAMES
            or "docker" in filename
            or "deploy" in path
            or "deployment" in path
        ):
            deployment = True

        # ----------------------------------------------------
        # Framework indicators
        # ----------------------------------------------------

        if filename == "package.json":
            frameworks.add("Node.js ecosystem")

        if filename == "requirements.txt":
            frameworks.add("Python ecosystem")

        if filename == "pyproject.toml":
            frameworks.add("Python ecosystem")

        if filename == "pom.xml":
            frameworks.add("Maven")

        if filename == "build.gradle":
            frameworks.add("Gradle")

        if filename == "go.mod":
            frameworks.add("Go modules")

    return {
        "frontendDetected": frontend,
        "backendDetected": backend,
        "databaseDetected": database,
        "apiDetected": api,
        "deploymentDetected": deployment,
        "frameworks": sorted(frameworks),
        "languages": sorted(languages),
    }


# ============================================================
# FILE SCORING
# ============================================================

def score_file(
    file,
    service_name,
    architecture,
    incident,
):

    path = normalize_path(
        file["path"]
    )

    filename = path.split("/")[-1]

    score = 0

    # --------------------------------------------------------
    # Important project files
    # --------------------------------------------------------

    if filename in IMPORTANT_FILES:
        score += 10

    # --------------------------------------------------------
    # Source/config relevance
    # --------------------------------------------------------

    extension = get_extension(path)

    if extension in SOURCE_EXTENSIONS:
        score += 4

    elif extension in CONFIG_EXTENSIONS:
        score += 3

    # --------------------------------------------------------
    # Service-name relevance
    # --------------------------------------------------------

    if service_name:

        service = service_name.lower()

        if service in path:
            score += 12

    # --------------------------------------------------------
    # API relevance
    # --------------------------------------------------------

    if architecture["apiDetected"]:

        if any(
            keyword in path
            for keyword in [
                "/api/",
                "/routes/",
                "/controllers/",
                "/services/",
                "router",
            ]
        ):
            score += 8

    # --------------------------------------------------------
    # Database relevance
    #
    # Only score database files when the repository actually
    # contains database indicators.
    # --------------------------------------------------------

    if architecture["databaseDetected"]:

        if any(
            keyword in path
            for keyword in [
                "database",
                "db/",
                "model",
                "migration",
                "schema",
            ]
        ):
            score += 8

    # --------------------------------------------------------
    # Incident signal relevance
    # --------------------------------------------------------

    if incident.errorRate > 0:

        if any(
            keyword in path
            for keyword in [
                "error",
                "exception",
                "middleware",
                "handler",
                "logging",
            ]
        ):
            score += 5

    if incident.latencyMs > 0:

        if any(
            keyword in path
            for keyword in [
                "request",
                "http",
                "api",
                "route",
                "controller",
                "service",
            ]
        ):
            score += 4

    # --------------------------------------------------------
    # Deployment relevance
    # --------------------------------------------------------

    if architecture["deploymentDetected"]:

        if (
            filename in INFRASTRUCTURE_NAMES
            or "docker" in filename
            or "deploy" in path
            or "deployment" in path
        ):
            score += 7

    return score


# ============================================================
# GET RELEVANT REPOSITORY CONTEXT
# ============================================================

def get_relevant_repository_context(
    repository_url: str,
    github_token: str,
    service_name: str,
    incident,
):

    # --------------------------------------------------------
    # 1. Get repository structure
    # --------------------------------------------------------

    repository = get_repository_tree(
        repository_url=repository_url,
        github_token=github_token,
    )

    files = repository.get(
        "files",
        []
    )

    if not files:

        return {
            "repository": {
                "owner": repository.get("owner"),
                "name": repository.get("repository"),
                "defaultBranch": repository.get(
                    "default_branch"
                ),
            },
            "architecture": {},
            "selectedFiles": [],
            "investigationConstraints": [
                "Repository contains no accessible files.",
                "Repository source cannot currently explain the incident.",
            ],
        }

    # --------------------------------------------------------
    # 2. Detect architecture
    # --------------------------------------------------------

    architecture = detect_architecture(
        files
    )

    # --------------------------------------------------------
    # 3. Score files
    # --------------------------------------------------------

    scored_files = []

    for file in files:

        score = score_file(
            file=file,
            service_name=service_name,
            architecture=architecture,
            incident=incident,
        )

        scored_files.append({
            "path": file["path"],
            "score": score,
            "size": file.get("size"),
        })

    # Highest relevance first
    scored_files.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    # --------------------------------------------------------
    # 4. Select limited number of files
    # --------------------------------------------------------

    selected = scored_files[
        :MAX_FILES_TO_ANALYZE
    ]

    # --------------------------------------------------------
    # 5. Fetch actual source code
    # --------------------------------------------------------

    selected_files = []

    for selected_file in selected:

        path = selected_file["path"]

        try:

            file_data = get_repository_file(
                repository_url=repository_url,
                github_token=github_token,
                file_path=path,
                branch=repository.get(
                    "default_branch"
                ),
            )

            content = file_data.get(
                "content",
                ""
            )

            if len(content) > MAX_FILE_CONTENT_LENGTH:

                content = (
                    content[
                        :MAX_FILE_CONTENT_LENGTH
                    ]
                    + "\n\n"
                    + "[FILE CONTENT TRUNCATED]"
                )

            selected_files.append({
                "path": path,
                "score": selected_file["score"],
                "content": content,
            })

        except Exception as e:

            selected_files.append({
                "path": path,
                "score": selected_file["score"],
                "content": "",
                "error": str(e),
            })

    # --------------------------------------------------------
    # 6. Investigation constraints
    # --------------------------------------------------------

    constraints = [
        (
            "Telemetry values are symptoms and do not prove "
            "that a repository component is responsible."
        ),
        (
            "Do not diagnose a database problem unless "
            "repository evidence or explicit external-system "
            "evidence supports a database dependency."
        ),
        (
            "Do not identify an affected file based only "
            "on its filename."
        ),
        (
            "Affected files must contain actual code or "
            "configuration evidence relevant to the incident."
        ),
        (
            "If repository evidence cannot explain the "
            "incident, report that external evidence is required."
        ),
        (
            "Clearly distinguish confirmed evidence from "
            "hypotheses."
        ),
    ]

    # --------------------------------------------------------
    # 7. Return focused repository context
    # --------------------------------------------------------

    return {
        "repository": {
            "owner": repository.get("owner"),
            "name": repository.get("repository"),
            "defaultBranch": repository.get(
                "default_branch"
            ),
            "language": repository.get(
                "language"
            ),
            "description": repository.get(
                "description"
            ),
            "fileCount": repository.get(
                "file_count"
            ),
        },
        "architecture": architecture,
        "investigationConstraints": constraints,
        "selectedFiles": selected_files,
    }