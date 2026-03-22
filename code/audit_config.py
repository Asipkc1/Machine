from urllib.parse import urljoin

BASE_URL = "https://beta-noibo.kydai.vn/"
LOGIN_URL = urljoin(BASE_URL, "/login")
OUTPUT_FILE_NAME = "audit_viet_hoa_beta_noibo_with_login"
MAX_PAGES = 20

AUDIT_ACCOUNTS = [
    {"username": "demo1", "password": "123456"},
    {"username": "demo2", "password": "123456"},
]

TAG_SELECTOR = ",".join(
    [
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "button",
        "label",
        "p",
        "span",
        "li",
        "th",
        "td",
        "option",
        "input",
        "textarea",
    ]
)

ENGLISH_HINTS = {
    "accessibility",
    "blind",
    "cancel",
    "chat",
    "create",
    "dashboard",
    "delete",
    "edit",
    "enable",
    "filter",
    "game",
    "games",
    "home",
    "learn",
    "login",
    "logout",
    "mode",
    "next",
    "offline",
    "online",
    "player",
    "players",
    "previous",
    "rank",
    "save",
    "search",
    "settings",
    "submit",
    "video",
}

VIETNAMESE_CHARS = (
    "a-zA-Z0-9_"
    "A-Za-z0-9_"
    "ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠ"
    "àáâãèéêìíòóôõùúăđĩũơ"
    "Ưăạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọ"
    "ỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
)
