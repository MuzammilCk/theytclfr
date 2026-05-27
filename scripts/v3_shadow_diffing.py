#!/usr/bin/env python3
"""V3 Shadow Diffing Engine.

Compares V2FinalOutput items against V3 FinalResponse items
by reading from the main production database and the shadow database.
"""

import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ytclfr.db.models.final_output import FinalOutputModel

def main():
    parser = argparse.ArgumentParser(description="Diff V2 vs V3 FinalOutputs")
    parser.add_argument("--main-db", required=True, help="Main DB connection string")
    parser.add_argument("--shadow-db", required=True, help="Shadow DB connection string")
    args = parser.parse_args()

    main_engine = create_engine(args.main_db)
    shadow_engine = create_engine(args.shadow_db)

    MainSession = sessionmaker(bind=main_engine)
    ShadowSession = sessionmaker(bind=shadow_engine)

    with MainSession() as main_session, ShadowSession() as shadow_session:
        # Get all V3 results from shadow DB
        shadow_outputs = shadow_session.query(FinalOutputModel).filter(
            FinalOutputModel.content_type.startswith("v3_")
        ).all()

        if not shadow_outputs:
            print("No V3 shadow outputs found in shadow database.")
            return

        total_compared = 0
        total_items_diff = 0
        better_in_v3 = 0
        worse_in_v3 = 0
        
        print(f"Found {len(shadow_outputs)} shadow V3 jobs. Comparing with V2...\n")

        for shadow_out in shadow_outputs:
            v3_job_id = shadow_out.job_id
            main_out = main_session.query(FinalOutputModel).filter(
                FinalOutputModel.job_id == v3_job_id
            ).first()

            if not main_out:
                print(f"[{v3_job_id}] Main V2 output not found. Skipping.")
                continue

            if not main_out.content_type.startswith("v2_"):
                continue

            total_compared += 1
            
            v2_json = main_out.output_json
            v3_json = shadow_out.output_json

            # Extract items
            v2_items = v2_json.get("items", [])
            v3_items = v3_json.get("items", [])
            
            v2_names = {i.get("name", "").lower() for i in v2_items}
            v3_names = {i.get("name", "").lower() for i in v3_items}

            added = v3_names - v2_names
            removed = v2_names - v3_names

            if added or removed:
                total_items_diff += 1
                print(f"\n--- Job {v3_job_id} ---")
                if added:
                    print(f"  [+] V3 Added: {', '.join(added)}")
                    better_in_v3 += 1
                if removed:
                    print(f"  [-] V3 Removed (Missed?): {', '.join(removed)}")
                    worse_in_v3 += 1

        print("\n=== SUMMARY ===")
        print(f"Total Jobs Compared: {total_compared}")
        print(f"Jobs with Item Differences: {total_items_diff}")
        print(f"Jobs where V3 found MORE items: {better_in_v3}")
        print(f"Jobs where V3 missed V2 items: {worse_in_v3}")

if __name__ == "__main__":
    main()
