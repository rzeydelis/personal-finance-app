I have a CSV of my credit-card transactions with columns like Date, Time, Amount, Merchant, and Description. Please:

Identify potential duplicate charges.

A "duplicate" is defined as two or more transactions with the same Amount (to the cent) and very similar Merchant or Description, occurring within a short window (e.g. {config['time_window_hours']} hour).

Flag each group of potential duplicates and list all their details.

Avoid false positives for expected pairs.

For round-trip commute expenses (e.g. PATH train), the same merchant ("PATH") will appear twice daily with identical fares.

Exclude any transactions where Merchant contains "PATH" or "E-Z*PASSNY" (or your specified transit vendors) that occur once in the morning and once in the evening with identical amounts.

Allow me to customize this "expected-pair" rule by merchant name, time-of-day window, and number of repeats.

Expected pair configuration: {json.dumps(config['expected_pairs'])}

Provide context and next steps.

For each flagged group, give a brief rationale ("same amount, same merchant, 5 mins apart"), and recommend whether it's likely an error.

If uncertain, ask me to confirm or provide more context.

Output format.

Present results as JSON with an array of objects, each containing:

transactions: list of raw rows
reason: why flagged
is_commute_pair: true/false
likely_duplicate_error: true/false or "undecided"
notes: any special handling or questions for me

Here is the transaction data:

{csv_data}

Please analyze this data and return ONLY valid JSON output with no additional text or explanation outside the JSON.