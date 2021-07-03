import os
from typing import Optional
from datetime import datetime, timedelta

import pandas as pd
from notion_client import Client
from notion.block import TodoBlock
from notion.client import NotionClient

from settings import API_TOKEN, TOKEN, TAR_DB_ID, TAR_PAGE_ID_LIST


def extract_todo(notion):
    ret: list = []

    def inner(block_id) -> list:
        res = notion.blocks.children.list(block_id=block_id)
        for res_dict in res["results"]:
            if res_dict["has_children"]:
                inner(res_dict["id"])
            elif res_dict["type"] == "to_do" and res_dict["to_do"]["checked"]:
                if res_dict["to_do"]["text"]:
                    ret.append({
                        "block_id": res_dict["id"],
                        "name": res_dict["to_do"]["text"][0]["plain_text"],
                    })
        return ret
    return inner


def get_record_by_dict(df, target) -> Optional[dict]:
    for rec in df.to_dict(orient="records"):
        if rec["Name"] == target:
            return rec


def main():
    # Init
    notion = Client(auth=os.environ.get("NOTION_TOKEN", API_TOKEN))
    client = NotionClient(token_v2=TOKEN)

    # Extract blocks with True checkboxes
    res = []
    for page_id in TAR_PAGE_ID_LIST:
        blocks = extract_todo(notion)(page_id)
        res.extend(blocks)

    # Update
    df = pd.read_csv("routines.tsv", sep="\t")
    yesterday = datetime.today() - timedelta(days=1)
    for block_dict in res:
        # Update the DB
        routine_name: str = block_dict["name"]
        record: dict = get_record_by_dict(df, routine_name)
        msg: str = f"The routine name({routine_name}) was not found in routines.tsv."
        if record is None:
            print(msg)
            continue
        notion.pages.create(
            **{
                "parent": {"database_id": TAR_DB_ID},
                "properties": {
                    "Category": {"rich_text": [{"text": {"content": record["Category"]}}]},
                    "Type": {"select": {"name":  record["Type"]}},
                    "RoutineName": {"title": [{"text": {"content": routine_name}}]},
                    "Date": {"date": {"start": f"{yesterday:%Y-%m-%d}"}}
                }
            }
        )

        # Reset the Checkbox to False
        block_id: str = block_dict["block_id"]
        td = TodoBlock(client=client, id=block_id)
        td.checked = False


if __name__ == "__main__":
    main()
