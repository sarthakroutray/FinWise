from extract import BankStatementExtractor, ParseContext


def test_partial_dates_use_statement_period_year() -> None:
    extractor = BankStatementExtractor()
    context = ParseContext(
        source_file="statement.pdf",
        period_start="2025-10-03",
        period_end="2025-11-09",
    )

    assert extractor._parse_date("10/03", prefer_dayfirst=False, context=context) == "2025-10-03"
    assert extractor._parse_date("Nov 9", context=context, previous_date="2025-10-31") == "2025-11-09"


def test_suffix_parser_ignores_reference_number_before_amount_zone() -> None:
    extractor = BankStatementExtractor()

    description, amount, currency, tx_type, balance = extractor._parse_suffix_fields(
        "CHECK 1234 21.00 100.00",
        previous_balance=None,
    )

    assert description == "CHECK 1234"
    assert amount == -21.0
    assert balance == 100.0
    assert currency is None
    assert tx_type == "debit"


def test_suffix_parser_repairs_split_decimal_tokens() -> None:
    extractor = BankStatementExtractor()

    description, amount, currency, tx_type, balance = extractor._parse_suffix_fields(
        extractor._normalize_split_decimals("CHECK 1234 9 98 807.08"),
        previous_balance=None,
    )

    assert description == "CHECK 1234"
    assert amount == -9.98
    assert balance == 807.08
    assert currency is None
    assert tx_type == "debit"


def test_text_line_parser_skips_section_noise_and_keeps_balances() -> None:
    extractor = BankStatementExtractor()
    context = ParseContext(
        source_file="statement.pdf",
        period_start="2025-10-03",
        period_end="2025-11-09",
    )

    rows, carry = extractor._parse_text_lines(
        [
            "Account # 12345678 Activity for Relationship Checking Account",
            "10/05 CHECK 1234 21.00 100.00",
            "Check Images for Relationship Checking Account",
            "10/06 PREAUTHORIZED CREDIT 763.01 863.01",
        ],
        context,
        None,
    )

    assert carry is None
    assert len(rows) == 2

    assert rows[0]["date"] == "2025-10-05"
    assert rows[0]["description"] == "CHECK 1234"
    assert rows[0]["amount"] == -21.0
    assert rows[0]["balance_after"] == 100.0

    assert rows[1]["date"] == "2025-10-06"
    assert rows[1]["description"] == "PREAUTHORIZED CREDIT"
    assert rows[1]["amount"] == 763.01
    assert rows[1]["balance_after"] == 863.01
