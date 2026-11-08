"""
data_prep.py

Shared data-loading and cleaning functions for the Data Analyst Job Postings
project. Every analysis notebook (02_market_landscape, 03_skills_demand,
04_pay_analysis, 05_geo_animation) should import from this module rather than
re-implementing the cleaning steps already worked out in
01_eda_data_analyst_jobs.ipynb.

Usage:

    from data_prep import load_and_clean
    df = load_and_clean("../raw/gsearch_jobs.csv")
"""

import pandas as pd
import numpy as np
import ast
import re


# --- Column name constants -------------------------------------------------
# Matches the raw scrape schema used throughout 01_eda_data_analyst_jobs.ipynb.
# Update these in one place if the source file's column names ever change.
COL_TITLE       = "title"
COL_COMPANY     = "company_name"
COL_LOCATION    = "location"
COL_VIA         = "via"                  # e.g. "via LinkedIn" — has a "via " prefix
COL_DESCRIPTION = "description"
COL_EXTENSIONS  = "extensions"           # string-list: time posted, salary text, benefits, schedule type
COL_JOB_ID      = "job_id"
COL_POSTED_AT   = "posted_at"            # relative string, e.g. "15 hours ago"
COL_SCHEDULE    = "schedule_type"
COL_WFH         = "work_from_home"       # only True or NaN — no explicit False
COL_SALARY_TEXT = "salary"               # raw text, e.g. "101K-143K a year"
COL_SEARCH_TERM = "search_term"
COL_DATE_TIME   = "date_time"            # scrape timestamp
COL_SEARCH_LOC  = "search_location"
COL_COMMUTE     = "commute_time"
COL_SALARY_PAY  = "salary_pay"
COL_SALARY_RATE = "salary_rate"
COL_SALARY_AVG  = "salary_avg"
COL_SALARY_MIN  = "salary_min"
COL_SALARY_MAX  = "salary_max"
COL_SALARY_HOUR = "salary_hourly"
COL_SALARY_YEAR = "salary_yearly"
COL_SALARY_STD  = "salary_standardized"
COL_SKILLS      = "description_tokens"   # string-list of skills, e.g. "['sql', 'python']"

EXPECTED_COLUMNS = [
    COL_TITLE, COL_COMPANY, COL_LOCATION, COL_VIA, COL_DESCRIPTION,
    COL_EXTENSIONS, COL_JOB_ID, COL_POSTED_AT, COL_SCHEDULE, COL_WFH,
    COL_SALARY_TEXT, COL_SEARCH_TERM, COL_DATE_TIME, COL_SEARCH_LOC,
    COL_COMMUTE, COL_SALARY_PAY, COL_SALARY_RATE, COL_SALARY_AVG,
    COL_SALARY_MIN, COL_SALARY_MAX, COL_SALARY_HOUR, COL_SALARY_YEAR,
    COL_SALARY_STD, COL_SKILLS,
]

# Regex helpers used by split_extensions() below — module-level so they're
# compiled once rather than on every function call.
TIME_AGO_RE = re.compile(r"^\d+\+?\s+(minute|hour|day|week|month)s?\s+ago$", re.IGNORECASE)
SALARY_TEXT_RE = re.compile(r"(a year|an hour|a month|a week)$", re.IGNORECASE)

# Used by extract_state() below to confirm a two-letter match is really a
# US state (and not, say, a coincidental two-letter suffix).
US_STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

# --- Title categorization: role bucket --------------------------------------
# Derived from the word-frequency pass in 01_eda_data_analyst_jobs.ipynb
# (Step 9), not assumed up front. Candidate role-word counts (of 61,953
# postings whose title contains the word):
#   analyst/analytics/analysis   48,783 / 5,600 / 1,731  (dominant — 84.6% of
#                                                          titles once combined)
#   scientist                     3,075 (5.0%)
#   engineer                      2,114 (3.4%)
#   specialist                    1,341 (2.2%)
#   developer/consultant/associate/director/architect/governance/quality — all
#   under ~700 each, no single one large enough to deserve its own bucket.
#
# Loosely follows the Google Data Analyst Professional Certificate's 3-path
# framework (Data Analyst / Data Scientist / Data Specialist), with one
# deliberate deviation: Engineer gets kept as its own bucket rather than
# folded into Specialist, since "engineer" alone (2,114) outnumbers the
# literal word "specialist" (1,341) — collapsing it in would hide a role
# that's practically distinct from governance/quality/BI-admin type work.
#
# Checked in order below, first match wins, since a title can contain more
# than one role word (e.g. "Analytics Engineer" contains both "analytics"
# and "engineer"). Scientist and Engineer are checked before Analyst, so an
# "Analytics Engineer" / "Data Scientist/Analyst" style title lands in the
# more specific bucket rather than the catch-all-sized Analyst one. This is
# a real judgment call on ~1,000 titles (1.6% of postings) that mention both
# "engineer" and analyst/analytics/analysis — flip the order below if you'd
# rather Analyst win those ties.
ROLE_RULES = [
    ("Data Scientist", "scientist"),
    ("Data Engineer", "engineer"),
]
# These three all map to the same "Data Analyst" bucket — checked together,
# not in the ordered list above, since none of them should out-rank another.
ROLE_ANALYST_WORDS = ("analyst", "analytics", "analysis")
ROLE_DEFAULT = "Data Specialist/Other"  # specialist, developer, consultant,
                                         # associate, architect, governance,
                                         # quality, or no role word at all

# --- Title categorization: seniority bucket ---------------------------------
# Separate dimension from role — "how senior", not "what kind of role".
# Word list and roman-numeral regex both come straight from the Step 9
# frequency pass; counts there (of 61,953 postings):
#   senior/sr   7,654 / 2,629   lead   1,998   principal   636   staff   258
#   junior  665   entry  731   intern  876
# Manager/Director (1,581 / 329 contains-count) were folded in here rather
# than treated as their own role bucket: a title like "Data Analyst Manager"
# describes a seniority tier layered on an Analyst role, not a different
# kind of work.
#
# Checked in order below, first match wins (e.g. "Senior Manager" -> Manager,
# the higher tier, not Senior). A standalone roman numeral (Data Analyst II,
# III, ...) is tracked separately in title_level_numeral rather than mapped
# onto this scale — there's no reliable way to know from the data alone
# whether a given company's "II" means mid-level or something else, so it's
# kept as a raw, un-interpreted signal instead of a guess.
SENIORITY_RULES = [
    ("Director", "director"),
    ("Manager", "manager"),
    ("Principal", "principal"),
    ("Staff", "staff"),
    ("Lead", "lead"),
    ("Senior", "senior|sr"),
    ("Junior", "junior"),
    ("Entry-level", "entry"),
    ("Intern", "intern"),
]
SENIORITY_DEFAULT = "Not specified"

# Standalone roman-numeral level, e.g. "Data Analyst II" — matched with
# negative lookaround so it doesn't fire on roman-numeral-shaped substrings
# inside other words. Same regex as the Step 9 check in 01_eda.
ROMAN_NUMERAL_RE = re.compile(r"(?<![A-Za-z0-9])(?:I|II|III|IV|V)(?![A-Za-z0-9])")


# --- Loading -----------------------------------------------------------------

def load_raw(csv_path):
    """
    Read the raw CSV into a dataframe.

    Uses low_memory=False, since a few columns mix types across the many
    blank/padding rows in the raw file and otherwise trigger a DtypeWarning.
    Also checks that the expected columns (the COL_* constants above) are
    actually present in the loaded file, and warns if any are missing.

    Parameters
    ----------
    csv_path : str
        Path to the raw gsearch_jobs.csv file.

    Returns
    -------
    pd.DataFrame
        The raw, unmodified dataframe exactly as loaded from the CSV.
    """
    df = pd.read_csv(csv_path, low_memory=False)

    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        print(f"Warning: expected columns not found in {csv_path}: {missing_cols}")

    return df


# --- Structural cleanup -------------------------------------------------------

def drop_junk_columns(df):
    """
    Drop the leftover index-artifact columns ("Unnamed: 0", "index") if
    present. These carry no information beyond row position — a byproduct
    of the CSV being saved with a pandas index more than once.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with the junk columns removed (if they existed).
    """
    junk_index_cols = [c for c in ["Unnamed: 0", "index"] if c in df.columns]
    if junk_index_cols:
        return df.drop(columns=junk_index_cols)
    return df.copy()


def filter_real_postings(df):
    """
    Drop fully-blank padding rows (rows with no title at all) and return
    only the rows that look like real job postings.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        Subset of df where COL_TITLE is not null.
    """
    return df[df[COL_TITLE].notna()].copy()


# --- Whitespace handling -------------------------------------------------------

def report_whitespace(df):
    """
    Check every text column for leading/trailing whitespace and report how
    many values are affected per column, without modifying anything.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    dict
        Mapping of {column_name: affected_value_count}, for columns that
        have at least one affected value.
    """
    string_cols = df.select_dtypes(include="object").columns

    whitespace_report = {}
    for col in string_cols:
        series = df[col]
        try:
            has_whitespace = series.notna() & (series != series.str.strip())
        except AttributeError:
            # A few "object" columns (e.g. work_from_home) actually hold
            # booleans rather than text, so .str doesn't apply — skip those.
            continue
        count = int(has_whitespace.sum())
        if count > 0:
            whitespace_report[col] = count

    return whitespace_report


def strip_whitespace(df):
    """
    Strip leading/trailing whitespace from every text column. Skips columns
    that hold booleans/mixed types rather than text (e.g. work_from_home),
    where .str.strip() doesn't apply.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with whitespace stripped from all text columns.
    """
    df = df.copy()
    string_cols = df.select_dtypes(include="object").columns

    for col in string_cols:
        try:
            df[col] = df[col].str.strip()
        except AttributeError:
            continue

    return df


# --- Skills parsing -------------------------------------------------------

def parse_list_string(raw):
    """
    Safely convert a string that looks like a Python list (e.g.
    "['sql', 'python']") into an actual list. Returns an empty list for
    missing or malformed values instead of raising.

    Parameters
    ----------
    raw : str or NaN
        A single cell value from a string-encoded list column.

    Returns
    -------
    list
    """
    if pd.isna(raw):
        return []
    try:
        parsed = ast.literal_eval(raw)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


def add_skills_list(df):
    """
    Apply parse_list_string() to COL_SKILLS (description_tokens) and add
    the result as a new "skills_list" column.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with a new "skills_list" column (each cell an actual
        list of skill strings, e.g. ['sql', 'python']).
    """
    df = df.copy()
    df["skills_list"] = df[COL_SKILLS].apply(parse_list_string)
    return df


# --- Extensions parsing -------------------------------------------------

def split_extensions(raw):
    """
    Split one row's `extensions` string-list into three categories, by
    pattern-matching each item:
      - time tokens   ("15 hours ago" style — redundant with posted_at)
      - salary tokens ("101K-143K a year" style — redundant with the
                        salary_* columns)
      - flag tokens   (everything else: benefits, schedule type,
                        "No degree mentioned", etc.)

    Parameters
    ----------
    raw : str or NaN
        A single cell value from the extensions column.

    Returns
    -------
    pd.Series
        Series with keys "ext_time", "ext_salary_text", "ext_flags", each
        holding a list of the matching items.
    """
    items = parse_list_string(raw)
    time_tokens, salary_tokens, flag_tokens = [], [], []
    for item in items:
        if TIME_AGO_RE.match(item):
            time_tokens.append(item)
        elif SALARY_TEXT_RE.search(item):
            salary_tokens.append(item)
        else:
            flag_tokens.append(item)
    return pd.Series({
        "ext_time": time_tokens,
        "ext_salary_text": salary_tokens,
        "ext_flags": flag_tokens,
    })


def add_extension_flags(df):
    """
    Apply split_extensions() across COL_EXTENSIONS, join the resulting
    ext_time / ext_salary_text / ext_flags columns onto df, and derive two
    boolean convenience columns from ext_flags:
      - flag_health_insurance   (True if "Health insurance" appears)
      - flag_no_degree_mentioned (True if "No degree mentioned" appears)

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with the new extension-derived columns added.
    """
    df = df.copy()
    df = df.join(df[COL_EXTENSIONS].apply(split_extensions))
    df["flag_health_insurance"] = df["ext_flags"].apply(lambda flags: "Health insurance" in flags)
    df["flag_no_degree_mentioned"] = df["ext_flags"].apply(lambda flags: "No degree mentioned" in flags)
    return df


# --- Source cleanup -------------------------------------------------------

def clean_via(df):
    """
    Strip the "via " prefix from COL_VIA (e.g. "via LinkedIn" -> "LinkedIn")
    and store the result in a new "via_clean" column.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with a new "via_clean" column.
    """
    df = df.copy()
    df["via_clean"] = df[COL_VIA].str.replace(r"^via\s+", "", regex=True)
    return df


# --- Date reconstruction -------------------------------------------------

def parse_relative_hours(text):
    """
    Convert a relative time string like "15 hours ago" or "2 days ago"
    into a number of hours.

    Parameters
    ----------
    text : str or NaN
        A single cell value from the posted_at column.

    Returns
    -------
    float
        Number of hours represented by the string, or NaN if it doesn't
        match the expected "<number> <unit> ago" pattern.
    """
    if pd.isna(text):
        return np.nan
    match = re.match(r"(\d+)\+?\s+(minute|hour|day|week|month)s?\s+ago", str(text), re.IGNORECASE)
    if not match:
        return np.nan
    amount, unit = int(match.group(1)), match.group(2).lower()
    hours_per_unit = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 24 * 7, "month": 24 * 30}
    return amount * hours_per_unit[unit]


def add_posted_date(df):
    """
    Reconstruct an actual calendar date per posting by combining
    COL_DATE_TIME (the scrape timestamp) with the parsed "hours ago" offset
    from parse_relative_hours():

        posted_date = date_time - hours_since_posted

    Adds both "hours_since_posted" and "posted_date" as new columns.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with "hours_since_posted" and "posted_date" added.
    """
    df = df.copy()
    df["hours_since_posted"] = df[COL_POSTED_AT].apply(parse_relative_hours)
    date_time_parsed = pd.to_datetime(df[COL_DATE_TIME], errors="coerce")
    df["posted_date"] = date_time_parsed - pd.to_timedelta(df["hours_since_posted"], unit="h")
    return df


# --- Location typing (for the geo/map analysis) -------------------------

def extract_state(location):
    """
    Pull a two-letter US state abbreviation out of a "City, ST" style
    location string. Returns None for values that don't match that pattern
    (e.g. "Anywhere", "United States").

    Parameters
    ----------
    location : str or NaN
        A single cell value from the location column.

    Returns
    -------
    str or None
        The two-letter state code, or None if not found.
    """
    if pd.isna(location):
        return None
    match = re.search(r",\s*([A-Za-z]{2})\s*$", str(location).strip())
    if not match:
        return None
    code = match.group(1).upper()
    return code if code in US_STATE_ABBREVIATIONS else None



def add_location_type(df):
    """
    Categorize every row into one of three location types, based on the
    location text and the work_from_home flag:
      - "Remote"                 location == "Anywhere", or work_from_home
      - "Nationwide/Unspecified" location == "United States", no city given
      - "Specific location"      a parseable "City, ST" (see extract_state())
      - "Unknown"                anything else that doesn't match the above

    Adds a "state" column (from extract_state()) and a "location_type"
    column.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with "state" and "location_type" columns added.
    """
    df = df.copy()
    df["state"] = df[COL_LOCATION].apply(extract_state)

    location_stripped = df[COL_LOCATION].astype(str).str.strip()
    is_remote = (location_stripped == "Anywhere") | (df[COL_WFH] == True)  # noqa: E712
    is_nationwide = (location_stripped == "United States") & ~is_remote
    is_specific = df["state"].notna() & ~is_remote & ~is_nationwide

    df["location_type"] = np.select(
        [is_remote, is_nationwide, is_specific],
        ["Remote", "Nationwide/Unspecified", "Specific location"],
        default="Unknown",
    )
    return df


# --- Title categorization (role / seniority) -----------------------------

def categorize_title_role(title):
    """
    Bucket a single title into a role category: "Data Scientist",
    "Data Engineer", "Data Analyst", or "Data Specialist/Other" (the
    catch-all for specialist/developer/consultant/associate/architect/
    governance/quality titles, and anything with none of the above words).
    See the ROLE_RULES comment above for how the bucket list and the
    check order were decided.

    Parameters
    ----------
    title : str or NaN

    Returns
    -------
    str or None
        One of the four role bucket labels, or None if title is missing.
    """
    if pd.isna(title):
        return None
    title_lower = title.lower()
    for label, word in ROLE_RULES:
        if word in title_lower:
            return label
    if any(word in title_lower for word in ROLE_ANALYST_WORDS):
        return "Data Analyst"
    return ROLE_DEFAULT


def categorize_title_seniority(title):
    """
    Bucket a single title into a seniority tier: Director, Manager,
    Principal, Staff, Lead, Senior, Junior, Entry-level, Intern, or
    "Not specified" if none of those words appear. See the
    SENIORITY_RULES comment above for the check order and why
    Manager/Director are treated as seniority rather than role.

    Parameters
    ----------
    title : str or NaN

    Returns
    -------
    str or None
        One of the seniority tier labels, or None if title is missing.
    """
    if pd.isna(title):
        return None
    title_lower = title.lower()
    for label, pattern in SENIORITY_RULES:
        if re.search(rf"\b(?:{pattern})\b", title_lower):
            return label
    return SENIORITY_DEFAULT


def extract_title_level_numeral(title):
    """
    Pull a standalone roman-numeral level (I, II, III, IV, V) out of a
    title, e.g. "Data Analyst II" -> "II". Kept separate from
    categorize_title_seniority() rather than mapped onto that scale, since
    there's no reliable way to know from the data alone what a given
    company's numeral actually means.

    Parameters
    ----------
    title : str or NaN

    Returns
    -------
    str or None
        The roman numeral found, or None if title is missing or has none.
    """
    if pd.isna(title):
        return None
    match = ROMAN_NUMERAL_RE.search(title)
    return match.group(0) if match else None


def add_title_category(df):
    """
    Apply categorize_title_role(), categorize_title_seniority(), and
    extract_title_level_numeral() to COL_TITLE, adding three new columns:
    "title_role", "title_seniority", "title_level_numeral".

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        A copy of df with the three title-category columns added.
    """
    df = df.copy()
    df["title_role"] = df[COL_TITLE].apply(categorize_title_role)
    df["title_seniority"] = df[COL_TITLE].apply(categorize_title_seniority)
    df["title_level_numeral"] = df[COL_TITLE].apply(extract_title_level_numeral)
    return df


# --- Additional helper function(s) -------------------------

def top_n_values(df, column, n=10, dropna=True, ascending=False):
    """
    Return the n most (or least) frequent values in a text column, along
    with each value's count and share of total rows.

    Parameters
    ----------
    df : pd.DataFrame
    column : str
        Name of the column to summarize.
    n : int
        How many values to return.
    dropna : bool
        If False, includes missing values as their own category.
    ascending : bool
        False (default) returns the most frequent values.
        True returns the least frequent values instead.

    Returns
    -------
    pd.DataFrame
        Indexed by the distinct values, with "count" and "pct_of_rows" columns.
    """
    counts = df[column].value_counts(dropna=dropna, ascending=ascending)
    pct = (counts / len(df) * 100).round(1)
    return pd.DataFrame({"count": counts, "pct_of_rows": pct}).head(n)


# --- Orchestrator -------------------------------------------------------

def load_and_clean(csv_path):
    """
    Run the full cleaning pipeline in order and return one ready-to-use
    dataframe:

        load_raw -> drop_junk_columns -> filter_real_postings
        -> strip_whitespace -> add_skills_list -> add_extension_flags
        -> clean_via -> add_posted_date -> add_location_type
        -> add_title_category

    This is the single function every analysis notebook should call.

    Parameters
    ----------
    csv_path : str
        Path to the raw gsearch_jobs.csv file.

    Returns
    -------
    pd.DataFrame
        Fully cleaned dataframe, ready for analysis.
    """
    df = load_raw(csv_path)
    df = drop_junk_columns(df)
    df = filter_real_postings(df)
    df = strip_whitespace(df)
    df = add_skills_list(df)
    df = add_extension_flags(df)
    df = clean_via(df)
    df = add_posted_date(df)
    df = add_location_type(df)
    df = add_title_category(df)
    return df
