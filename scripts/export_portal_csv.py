#!/usr/bin/env python3
"""Convert Morpheus cell-level logger output to the workshop portal schema."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


DEFAULT_CELL_DIAMETER = math.sqrt(4.0 * 100.0 / math.pi)


def normalise(name: str) -> str:
    return "".join(character for character in name.lower() if character.isalnum())


def find_column(fieldnames: list[str], wanted: str) -> str:
    aliases = {
        "time": {"time"},
        "cellid": {"cellid", "id"},
        "celltype": {"celltype", "type"},
        "x": {"cellcenterx", "x"},
        "y": {"cellcentery", "y"},
    }
    for fieldname in fieldnames:
        if normalise(fieldname) in aliases[wanted]:
            return fieldname
    raise ValueError(f"Could not find {wanted!r} in logger columns: {', '.join(fieldnames)}")


def cell_type(value: str) -> str:
    try:
        numeric_value = int(float(value))
    except ValueError:
        return value
    if numeric_value == 0:
        return "A"
    if numeric_value == 1:
        return "B"
    return value


def encode_cell_type(value: str, output_format: str) -> str:
    label = cell_type(value)
    if output_format == "numeric":
        return {"A": "0", "B": "1"}.get(label, label)
    return label


def read_logger(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("Morpheus logger did not contain a header row")
        return reader.fieldnames, list(reader)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logger", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--sim-id", required=True)
    parser.add_argument("--cell-diameter", type=float, default=DEFAULT_CELL_DIAMETER)
    parser.add_argument("--cell-type-format", choices=("numeric", "labels"), default="numeric")
    return parser.parse_args()


def convert(
    logger: Path,
    output: Path,
    sim_id: str,
    cell_diameter: float,
    cell_type_format: str = "numeric",
) -> tuple[int, int]:
    if cell_diameter <= 0:
        raise ValueError("--cell-diameter must be positive")

    fieldnames, rows = read_logger(logger)
    columns = {name: find_column(fieldnames, name) for name in ("time", "cellid", "celltype", "x", "y")}
    if not rows:
        raise ValueError("Morpheus logger did not contain cell rows")

    output.parent.mkdir(parents=True, exist_ok=True)
    times: set[str] = set()
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("simID", "time", "cellID", "cellType", "x", "y"))
        for row in rows:
            time = row[columns["time"]]
            times.add(time)
            writer.writerow(
                (
                    sim_id,
                    time,
                    row[columns["cellid"]],
                    encode_cell_type(row[columns["celltype"]], cell_type_format),
                    f"{float(row[columns['x']]) / cell_diameter:.10g}",
                    f"{float(row[columns['y']]) / cell_diameter:.10g}",
                )
            )

    if len(times) != 101:
        raise ValueError(f"Expected 101 sampled times, found {len(times)}")
    return len(rows), len(times)


def main() -> None:
    args = parse_arguments()
    row_count, time_count = convert(args.logger, args.output, args.sim_id, args.cell_diameter, args.cell_type_format)
    print(f"Wrote {row_count} rows across {time_count} time points to {args.output}")


if __name__ == "__main__":
    main()
