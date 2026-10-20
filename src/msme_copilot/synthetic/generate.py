import argparse
import json
from pathlib import Path
from typing import cast

from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.merchant_generator import generate_world
from msme_copilot.synthetic.persistence import persist_merchants, persist_source_world, write_artifacts, write_source_artifacts
from msme_copilot.synthetic.source_validation import validate_source_world
from msme_copilot.synthetic.sources import generate_source_world
from msme_copilot.synthetic.slice_02c import generate_lending_world, lending_checksum
from msme_copilot.synthetic.slice_02c_persistence import persist_lending_world
from msme_copilot.synthetic.validation import audit_world, statistical_sanity, validate_world


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Slice 02A canonical MSME world")
    parser.add_argument("--seed", type=int, default=314159)
    parser.add_argument("--merchants", type=int, default=6000)
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--output", default="data/synthetic")
    parser.add_argument("--persist", action="store_true", help="persist canonical merchants to PostgreSQL")
    parser.add_argument("--sources", action="store_true", help="also generate Slice 02B observable sources")
    parser.add_argument("--persist-sources", action="store_true", help="persist generated 02B sources to PostgreSQL")
    parser.add_argument("--lending", action="store_true", help="also generate Slice 02C lending/evaluation rows")
    args = parser.parse_args()
    config = GeneratorConfig(seed=args.seed, number_of_merchants=args.merchants, number_of_months=args.months, artifact_path=Path(args.output))
    world = generate_world(config)
    report = validate_world(world, config)
    report["statistical_sanity"] = statistical_sanity(world)
    report["audit"] = audit_world(world)
    write_artifacts(world, config.artifact_path)
    if args.persist:
        persist_merchants(world)
        report["postgres_merchants_persisted"] = len(world.merchants)
    if args.sources or args.persist_sources:
        source_world = generate_source_world(world)
        report["source_audit"] = validate_source_world(world, source_world)
        write_source_artifacts(source_world, config.artifact_path)
        if args.persist_sources:
            persist_source_world(world, source_world)
            report["postgres_sources_persisted"] = cast(dict[str, object], report["source_audit"])["row_counts"]
    if args.lending:
        source_world = generate_source_world(world)
        lending_world = generate_lending_world(world, source_world)
        report["lending_checksum"] = lending_checksum(lending_world)
        report["lending_counts"] = {table: len(rows) for table, rows in lending_world.table_rows().items()}
        if args.persist_sources or args.persist:
            persist_lending_world(world, lending_world)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
