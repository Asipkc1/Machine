from pathlib import Path

from audit_config import AUDIT_ACCOUNTS, OUTPUT_FILE_NAME
from report_export import save_report_excel
from selenium_audit import run_scope_audit

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def run_localization_audit() -> list[dict[str, str]]:
    """Run Selenium localization audit for anonymous and logged-in scopes."""
    all_rows: list[dict[str, str]] = []
    all_rows.extend(run_scope_audit(scope="anonymous"))

    for account in AUDIT_ACCOUNTS:
        user = account["username"]
        all_rows.extend(
            run_scope_audit(
                scope=user,
                username=user,
                password=account["password"],
            )
        )

    deduped: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in all_rows:
        key = (row["scope"], row["page_url"], row["text"], row["source"])
        deduped[key] = row

    return sorted(
        deduped.values(),
        key=lambda item: (item["scope"], item["page_url"], item["text"]),
    )


if __name__ == "__main__":
    print("Bat dau audit Viet hoa bang Selenium...")
    findings = run_localization_audit()
    report_path = save_report_excel(
        rows=findings,
        output_dir=OUTPUT_DIR,
        filename=OUTPUT_FILE_NAME,
    )
    print(f"Tong chuoi nghi chua Viet hoa: {len(findings)}")
    print(f"File Excel: {report_path}")
